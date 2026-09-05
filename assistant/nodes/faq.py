from dataclasses import dataclass
from functools import lru_cache

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

    @property
    def phrasings(self) -> tuple[str, ...]:
        return (self.question, *self.asked_as)


def lookup(question: str) -> str | None:
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

    logger.info(
        "Answered from the FAQ (%.2f): %s", scores[best], entries[best].question
    )
    return entries[best].answer.strip()


@lru_cache(maxsize=1)
def _catalogue() -> tuple[tuple[Entry, ...], np.ndarray]:
    if not settings.FAQ_PATH.exists():
        logger.warning("No FAQ at %s", settings.FAQ_PATH)
        return (), np.zeros((0, 0))

    rows: list[Entry] = []
    vectors: list[np.ndarray] = []

    for item in yaml.safe_load(settings.FAQ_PATH.read_text()):
        entry = Entry(
            question=item["question"],
            answer=item["answer"],
            asked_as=tuple(item.get("asked_as", ())),
        )
        # One row per phrasing, every row pointing at the same answer.
        for phrasing in entry.phrasings:
            rows.append(entry)
            vectors.append(_vector(phrasing))

    return tuple(rows), np.vstack(vectors)


def _vector(text: str) -> np.ndarray:
    # Cosine similarity is a dot product only once the vectors are unit length,
    # which the model does not promise.
    vector = np.array(next(embed.dense([text])), dtype=np.float32)

    return vector / np.linalg.norm(vector)
