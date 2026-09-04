from collections.abc import Iterator
from functools import lru_cache

from fastembed import SparseTextEmbedding, TextEmbedding

from assistant.knowledge_base.store import DENSE_MODEL, SPARSE_MODEL
from assistant.logging import logger

# Small enough that embedding stays responsive on a low-core machine.
BATCH = 32


@lru_cache(maxsize=1)
def _dense() -> TextEmbedding:
    logger.info("Loading %s", DENSE_MODEL)
    return TextEmbedding(DENSE_MODEL)


@lru_cache(maxsize=1)
def _sparse() -> SparseTextEmbedding:
    logger.info("Loading %s", SPARSE_MODEL)
    return SparseTextEmbedding(SPARSE_MODEL)


def dense(texts: list[str]) -> Iterator[list[float]]:
    for vector in _dense().embed(texts, batch_size=BATCH):
        yield vector.tolist()


def sparse(texts: list[str]) -> Iterator[tuple[list[int], list[float]]]:
    for vector in _sparse().embed(texts, batch_size=BATCH):
        yield vector.indices.tolist(), vector.values.tolist()
