import re
from collections.abc import AsyncIterator

from assistant.config import settings
from assistant.llm import client
from assistant.prompts import prompt
from assistant.schemas import ChatMessage
from assistant.state import Passage

MAX_OUTPUT = 900
# Reasoning is billed against the same cap, so a small-talk budget sized for
# the reply alone leaves nothing to say it with and the answer arrives empty.
SMALL_TALK_OUTPUT = 700
# gpt-oss emits its own citation markers whatever the prompt says, and the
# numbers in them are invented. Sources are shown from the retrieved passages
# instead, so any marker that survives is stripped.
CITATION_MARKER = re.compile(r"【[^】]*】|\[\d+\]")
NO_EVIDENCE = (
    "I don't have that in my sources. Please call Nawaloka Hospitals on"
    " 0115 577 111 and they can help."
)


async def answer(
    question: str, passages: list[Passage], history: list[ChatMessage]
) -> AsyncIterator[str]:
    """Compose the answer over retrieved evidence, or abstain.

    The gate is deliberate: with nothing retrieved, a model asked to answer a
    hospital question will answer it from training data, which is exactly the
    failure a grounded assistant exists to prevent.
    """
    if not passages:
        yield NO_EVIDENCE
        return

    messages = [
        {"role": "system", "content": prompt("answer", evidence=_evidence(passages))},
        *_recent(history),
        {"role": "user", "content": question},
    ]

    async for token in client.stream(
        messages, model=settings.ANSWER_MODEL, max_output=MAX_OUTPUT
    ):
        yield CITATION_MARKER.sub("", token)


async def small_talk(question: str) -> AsyncIterator[str]:
    messages = [
        {"role": "system", "content": prompt("faq")},
        {"role": "user", "content": question},
    ]

    async for token in client.stream(
        messages, model=settings.ROUTER_MODEL, max_output=SMALL_TALK_OUTPUT
    ):
        yield token


def _evidence(passages: list[Passage]) -> str:
    return "\n\n".join(
        f"[{number}] ({passage.citation})\n{passage.content}"
        for number, passage in enumerate(passages, start=1)
    )


def _recent(history: list[ChatMessage]) -> list[dict[str, str]]:
    return [
        {"role": message.role, "content": message.content}
        for message in history[-settings.VERBATIM_TURNS :]
    ]
