import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from assistant.exceptions import UpstreamBusyError
from assistant.logging import logger
from assistant.memory import store
from assistant.nodes import faq, retrieve_sql, retrieve_vector, route, synthesize
from assistant.prompts import prompt
from assistant.schemas import ChatMessage
from assistant.state import Passage, Route, RouteDecision


@dataclass
class Event:
    """One thing worth showing the user while the answer is being built."""

    kind: str
    value: str
    detail: str = ""


@dataclass(frozen=True)
class Source:
    """A place answers come from: what to call it, and how to ask it."""

    name: str
    doing: str
    retrieve: Callable[[str], Awaitable[list[Passage]]]


async def _from_vector(question: str) -> list[Passage]:
    # Retrieval is CPU-bound ONNX work, so it runs off the event loop.
    return await asyncio.to_thread(retrieve_vector.retrieve, question)


SQL = Source("sql", "Querying the hospital database", retrieve_sql.retrieve)
VECTOR = Source("vector", "Searching hospital information", _from_vector)

# The one place a route says which sources it consults. Adding a third source
# is a line here, not a branch in three functions.
CONSULTS: dict[Route, tuple[Source, ...]] = {
    Route.SQL: (SQL,),
    Route.VECTOR: (VECTOR,),
    Route.BOTH: (SQL, VECTOR),
    Route.FAQ: (),
    Route.REFUSE: (),
}


async def run(conversation_id: str, question: str) -> AsyncIterator[Event]:
    """One turn, read top to bottom: remember, route, retrieve, answer, record.

    Two tools and one decision do not need an agent loop. A loop would re-inject
    the whole context to re-derive a choice already made, at roughly five times
    the tokens, on a budget of eight thousand a minute.
    """
    history = store.history(conversation_id)
    spoken: list[str] = []
    taken = ""
    failed = False

    async for event in _events(question, history):
        if event.kind == "token":
            spoken.append(event.value)
        if event.kind == "route":
            taken = event.value
        failed = failed or event.kind == "error"
        yield event

    # A model that spends its whole budget reasoning returns nothing at all, and
    # an empty reply reads as a broken assistant rather than a busy one. An
    # upstream failure has already said something more useful, so it stands.
    if not failed and not "".join(spoken).strip():
        logger.warning("The %s route produced no answer", taken)
        nothing_said = prompt("nothing_said").strip()
        spoken = [nothing_said]
        yield Event(kind="token", value=nothing_said)

    store.remember(conversation_id, question, "".join(spoken), taken)
    yield Event(kind="done", value="")


async def _events(question: str, history: list[ChatMessage]) -> AsyncIterator[Event]:
    """Answer the question, by the cheapest route that can."""
    cached = faq.lookup(question)

    if cached is not None:
        yield Event(kind="route", value=Route.FAQ.value, detail="Answered from the FAQ")
        yield Event(kind="token", value=cached)
        return

    try:
        decision = await route.route(question, history)
    except UpstreamBusyError as error:
        yield Event(kind="error", value=str(error))
        return

    yield Event(kind="route", value=decision.route.value, detail=decision.reason)

    async for event in _turn(decision, history):
        yield event


async def _turn(
    decision: RouteDecision, history: list[ChatMessage]
) -> AsyncIterator[Event]:
    """Everything between routing and recording, so the turn ends in one place."""
    if decision.route is Route.REFUSE:
        yield Event(kind="token", value=prompt("refusal").strip())
        return

    sources = CONSULTS[decision.route]

    for source in sources:
        yield Event(kind="tool", value=source.name, detail=source.doing)

    passages = await _gather(sources, decision.question)

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


async def _gather(sources: tuple[Source, ...], question: str) -> list[Passage]:
    """Ask every source at once: they share nothing, so waiting is pure latency."""
    found = await asyncio.gather(*(source.retrieve(question) for source in sources))

    return [passage for passages in found for passage in passages]


def _citations(passages: list[Passage]) -> list[str]:
    """Sources as data rather than as text the model was asked to produce.

    Asked for inline citations, the model invents marker numbers; these come
    from the passages that were actually retrieved.
    """
    return sorted({passage.citation for passage in passages if passage.citation})
