import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from assistant.exceptions import UpstreamBusyError
from assistant.logging import logger
from assistant.memory import store
from assistant.nodes import retrieve_sql, retrieve_vector, route, synthesize
from assistant.prompts import prompt
from assistant.schemas import ChatMessage
from assistant.state import Passage, Route, RouteDecision


@dataclass
class Event:
    """One thing worth showing the user while the answer is being built."""

    kind: str
    value: str
    detail: str = ""


NOTHING_SAID = (
    "Sorry, I did not catch that. Could you put it another way? I can help with"
    " doctors and fees, channeling times, lab tests and health packages."
)

# What each route reports it is doing, and therefore which sources it consults.
TOOLS = {
    Route.SQL: [("sql", "Querying the hospital database")],
    Route.VECTOR: [("vector", "Searching hospital information")],
    Route.BOTH: [
        ("sql", "Querying the hospital database"),
        ("vector", "Searching hospital information"),
    ],
}


async def run(conversation_id: str, question: str) -> AsyncIterator[Event]:
    """One turn, read top to bottom: remember, route, retrieve, answer, record.

    Two tools and one decision do not need an agent loop. A loop would re-inject
    the whole context to re-derive a choice already made, at roughly five times
    the tokens, on a budget of eight thousand a minute.
    """
    history = store.history(conversation_id)

    try:
        decision = await route.route(question, history)
    except UpstreamBusyError as error:
        yield Event(kind="error", value=str(error))
        return

    yield Event(kind="route", value=decision.route.value, detail=decision.reason)

    spoken: list[str] = []
    failed = False

    async for event in _turn(decision, history):
        if event.kind == "token":
            spoken.append(event.value)
        failed = failed or event.kind == "error"
        yield event

    # A model that spends its whole budget reasoning returns nothing at all, and
    # an empty reply reads as a broken assistant rather than a busy one. An
    # upstream failure has already said something more useful, so it stands.
    if not failed and not "".join(spoken).strip():
        logger.warning("The %s route produced no answer", decision.route.value)
        spoken = [NOTHING_SAID]
        yield Event(kind="token", value=NOTHING_SAID)

    store.remember(conversation_id, question, "".join(spoken), decision.route.value)
    yield Event(kind="done", value="")


async def _turn(
    decision: RouteDecision, history: list[ChatMessage]
) -> AsyncIterator[Event]:
    """Everything between routing and recording, so the turn ends in one place."""
    if decision.route is Route.REFUSE:
        yield Event(kind="token", value=prompt("refusal").strip())
        return

    passages = await _retrieve(decision.route, decision.question)

    for name, doing in TOOLS.get(decision.route, []):
        yield Event(kind="tool", value=name, detail=doing)

    for citation in _citations(passages):
        yield Event(kind="source", value=citation)

    async for event in _speak(decision, passages, history):
        yield event


async def _speak(
    decision: RouteDecision, passages: list[Passage], history: list[ChatMessage]
) -> AsyncIterator[Event]:
    tokens = (
        synthesize.small_talk(decision.question)
        if decision.route is Route.FAQ
        else synthesize.answer(decision.question, passages, history)
    )

    try:
        async for token in tokens:
            yield Event(kind="token", value=token)
    except UpstreamBusyError as error:
        logger.warning("Answer interrupted: %s", error)
        yield Event(kind="error", value=str(error))


async def _retrieve(chosen: Route, question: str) -> list[Passage]:
    if chosen is Route.FAQ:
        return []

    if chosen is Route.SQL:
        return await retrieve_sql.retrieve(question)

    if chosen is Route.VECTOR:
        return await asyncio.to_thread(retrieve_vector.retrieve, question)

    # Both sources, concurrently: they share nothing, so waiting for one before
    # starting the other only adds latency.
    from_sql, from_vector = await asyncio.gather(
        retrieve_sql.retrieve(question),
        asyncio.to_thread(retrieve_vector.retrieve, question),
    )

    return from_sql + from_vector


def _citations(passages: list[Passage]) -> list[str]:
    """Sources as data rather than as text the model was asked to produce.

    Asked for inline citations, the model invents marker numbers; these come
    from the passages that were actually retrieved.
    """
    return sorted({passage.citation for passage in passages if passage.citation})
