import json

from pydantic import ValidationError

from assistant.config import settings
from assistant.llm import client
from assistant.logging import logger
from assistant.prompts import prompt
from assistant.schemas import ChatMessage
from assistant.state import Route, RouteDecision

# The reply is a small JSON object; the rest of the reservation would be
# headroom taken from the minute's budget and never spent.
MAX_OUTPUT = 400
# Enough turns to resolve a pronoun without spending the minute's token budget
# on conversation history.
HISTORY_TURNS = 6


async def route(question: str, history: list[ChatMessage]) -> RouteDecision:
    messages = [
        {"role": "system", "content": prompt("router")},
        *_recent(history),
        {"role": "user", "content": question},
    ]

    raw = await client.complete(
        messages, model=settings.ROUTER_MODEL, max_output=MAX_OUTPUT
    )
    decision = _parse(raw, question)
    logger.info("Routed to %s: %s", decision.route, decision.question)

    return decision


def _recent(history: list[ChatMessage]) -> list[dict[str, str]]:
    return [
        {"role": message.role, "content": message.content}
        for message in history[-HISTORY_TURNS:]
    ]


def _parse(raw: str, question: str) -> RouteDecision:
    """Fall back to searching both sources rather than failing the turn.

    A malformed routing reply is recoverable: running both retrievals costs
    more than the right one, but it still answers the patient.
    """
    try:
        return RouteDecision.model_validate_json(_json(raw))
    except (ValidationError, ValueError):
        logger.warning("Router returned unusable JSON: %r", raw[:200])
        return RouteDecision(route=Route.BOTH, question=question, reason="unparsed")


def _json(raw: str) -> str:
    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object in the reply.")

    return json.dumps(json.loads(raw[start : end + 1]))
