from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from assistant.config import settings
from assistant.knowledge_base import embed
from assistant.logging import logger


@dataclass(frozen=True)
class Entry:
    """One curated answer and every phrasing that should reach it.

    A single wording cannot be matched loosely enough to catch "thanks" without
    also catching a question about the hospital, so each entry carries the ways
    people actually ask it and the bar stays high.
    """

    question: str
    answer: str
    asked_as: tuple[str, ...] = ()
    source: str = ""

    @property
    def phrasings(self) -> tuple[str, ...]:
        return (self.question, *self.asked_as)


@dataclass(frozen=True)
class Answer:
    """A reply that needed no model, and the page it came from if it had one."""

    text: str
    citation: str = ""


def lookup(question: str) -> Answer | None:
    """Answer a common enquiry outright, before any model is called.

    Greetings and questions about the assistant itself carry no hospital fact to
    retrieve, so routing and answering them costs two model calls for a reply
    that never varies. Matching them locally spends one embedding instead.
    """
    entries, catalogue = _catalogue()

    if not entries:
        return None

    asked = _vector(question)
    scores = catalogue @ asked
    best = int(scores.argmax())

    if scores[best] < settings.FAQ_THRESHOLD:
        return None

    entry = entries[best]
    logger.info("Answered from the FAQ (%.2f): %s", scores[best], entry.question)

    return Answer(text=entry.answer.strip(), citation=entry.source)


@lru_cache(maxsize=1)
def _catalogue() -> tuple[tuple[Entry, ...], np.ndarray]:
    """Curated entries first, then whatever the website's own FAQs added.

    Both files are read the same way, so a harvested answer is matched by the
    same threshold as a hand-written one and the curated wording wins a tie.
    """
    rows: list[Entry] = []
    vectors: list[np.ndarray] = []

    for entry in _entries():
        # One row per phrasing, every row pointing at the same answer.
        for phrasing in entry.phrasings:
            rows.append(entry)
            vectors.append(_vector(phrasing))

    if not rows:
        return (), np.zeros((0, 0))

    return tuple(rows), np.vstack(vectors)


def _entries() -> list[Entry]:
    return [
        Entry(
            question=item["question"],
            answer=item["answer"],
            asked_as=tuple(item.get("asked_as", ())),
            source=item.get("source", ""),
        )
        for path in (settings.FAQ_PATH, settings.HARVESTED_FAQ_PATH)
        for item in _items(path)
    ]


def _items(path: Path) -> list[dict]:
    if not path.exists():
        logger.warning("No FAQ at %s", path)
        return []

    return yaml.safe_load(path.read_text()) or []


def _vector(text: str) -> np.ndarray:
    # Cosine similarity is a dot product only once the vectors are unit length,
    # which the model does not promise.
    vector = np.array(next(embed.dense([text])), dtype=np.float32)

    return vector / np.linalg.norm(vector)
