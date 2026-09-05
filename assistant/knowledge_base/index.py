import uuid
from collections.abc import Iterator

from qdrant_client import QdrantClient, models

from assistant.config import settings
from assistant.knowledge_base import embed, faq_sections
from assistant.knowledge_base.chunk import Chunk, chunk_page
from assistant.knowledge_base.corpus import pages
from assistant.knowledge_base.store import (
    COLLECTION,
    DENSE,
    DENSE_MODEL,
    SPARSE,
    client,
    ensure_collection,
)
from assistant.logging import logger

UPSERT_BATCH = 32
NAMESPACE = uuid.UUID("6f9c1e1a-58d8-4f0e-9d1b-2f0f9a6f1e2c")


def load_corpus() -> list[Chunk]:
    chunks: list[Chunk] = []
    documents = pages()

    for page in documents:
        chunks.extend(chunk_page(page.body, url=page.url, title=page.title))

    logger.info("Read %d chunks from %d documents", len(chunks), len(documents))
    return chunks


def build() -> int:
    chunks = load_corpus()
    if not chunks:
        logger.warning("No corpus found in %s — run scrape first", settings.SCRAPED_DIR)
        return 0

    ensure_collection()
    connection = client()

    wanted = {_point_id(chunk, text): (chunk, text) for chunk, text in _texts(chunks)}
    stored = _stored_ids(connection)
    missing = sorted(wanted.keys() - stored)
    stale = sorted(stored - wanted.keys())

    logger.info(
        "Reusing %d vectors, embedding %d changed chunks",
        len(wanted) - len(missing),
        len(missing),
    )

    _embed_into(connection, [wanted[point_id] for point_id in missing], missing)

    if stale:
        connection.delete(
            COLLECTION, points_selector=models.PointIdsList(points=list(stale))
        )
        logger.info("Removed %d chunks no longer in the corpus", len(stale))

    logger.info("Indexed %d chunks into %s", len(wanted), settings.QDRANT_PATH)
    faq_sections.harvest()

    return len(wanted)


def _texts(chunks: list[Chunk]) -> Iterator[tuple[Chunk, str]]:
    for chunk in chunks:
        yield chunk, _contextualised(chunk)


def _point_id(chunk: Chunk, text: str) -> str:
    """A chunk's identity is what it holds, so an unchanged chunk keeps its id.

    The URL is part of it so that a line repeated across pages stays two points
    and each keeps its own citation, and the model name is part of it so that
    changing models invalidates every vector rather than silently mixing two
    embedding spaces.
    """
    return str(uuid.uuid5(NAMESPACE, f"{DENSE_MODEL}\n{chunk.url}\n{text}"))


def _stored_ids(connection: QdrantClient) -> set[str]:
    stored: set[str] = set()
    offset = None

    while True:
        records, offset = connection.scroll(
            COLLECTION,
            limit=UPSERT_BATCH,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        stored.update(str(record.id) for record in records)

        if offset is None:
            return stored


def _embed_into(
    connection: QdrantClient, pending: list[tuple[Chunk, str]], ids: list[str]
) -> None:
    if not pending:
        return

    texts = [text for _, text in pending]
    vectors = zip(embed.dense(texts), embed.sparse(texts), strict=True)
    batch: list[models.PointStruct] = []

    for position, (dense_vector, sparse_vector) in enumerate(vectors):
        chunk, text = pending[position]
        batch.append(_point(ids[position], chunk, text, dense_vector, sparse_vector))

        if len(batch) == UPSERT_BATCH:
            _upsert(connection, batch, position + 1, len(pending))
            batch = []

    if batch:
        _upsert(connection, batch, len(pending), len(pending))


def _upsert(
    connection: QdrantClient, batch: list[models.PointStruct], done: int, total: int
) -> None:
    connection.upsert(COLLECTION, points=batch)
    logger.info("Embedded %d of %d", done, total)


def _point(
    point_id: str,
    chunk: Chunk,
    text: str,
    dense_vector: list[float],
    sparse_vector: tuple[list[int], list[float]],
) -> models.PointStruct:
    indices, values = sparse_vector

    return models.PointStruct(
        id=point_id,
        vector={
            DENSE: dense_vector,
            SPARSE: models.SparseVector(indices=indices, values=values),
        },
        payload={
            "text": text,
            "url": chunk.url,
            "title": chunk.title,
            "heading": chunk.heading,
        },
    )


def _contextualised(chunk: Chunk) -> str:
    """Prefix the chunk with where it came from, before it is embedded.

    A fragment loses its subject when a page is split: "book an appointment"
    says nothing about which centre it belongs to. Contextual retrieval built
    from the page's own structure rather than a generated sentence per chunk.
    """
    source = " — ".join(part for part in (chunk.title, chunk.heading) if part)
    if not source:
        return chunk.text

    return f"{source}\n\n{chunk.text}"
