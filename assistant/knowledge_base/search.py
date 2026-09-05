from qdrant_client import models

from assistant.config import settings
from assistant.knowledge_base import embed
from assistant.knowledge_base.store import COLLECTION, DENSE, SPARSE, client
from assistant.logging import logger

# Fused candidates are cheap; only the reranked few reach the answer prompt.
CANDIDATES = 20


def search(question: str, limit: int | None = None) -> list[dict[str, str]]:
    """Hybrid retrieval: dense and BM25 fused by Qdrant, then reranked.

    Dense search alone misses exact tokens — a consultant's name, a test code —
    which is much of what patients type. BM25 alone misses paraphrase. Fusing
    both and reranking the survivors covers each one's blind spot.
    """
    limit = limit or settings.RETRIEVE_TOP_K
    hits = _fused(question)

    if not hits:
        return []

    passages = [hit.payload["text"] for hit in hits if hit.payload]
    ranked = sorted(
        zip(embed.rerank(question, passages), hits), key=_score, reverse=True
    )
    logger.info("Retrieved %d passages, keeping %d", len(hits), min(limit, len(ranked)))

    return [_passage(hit) for _, hit in ranked[:limit]]


def _fused(question: str) -> list[models.ScoredPoint]:
    dense_vector = next(embed.dense([question]))
    indices, values = next(embed.sparse([question]))

    response = client().query_points(
        COLLECTION,
        prefetch=[
            models.Prefetch(query=dense_vector, using=DENSE, limit=CANDIDATES),
            models.Prefetch(
                query=models.SparseVector(indices=indices, values=values),
                using=SPARSE,
                limit=CANDIDATES,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=CANDIDATES,
        with_payload=True,
    )

    return response.points


def _score(pair: tuple[float, models.ScoredPoint]) -> float:
    score, _ = pair
    return score


def _passage(hit: models.ScoredPoint) -> dict[str, str]:
    payload = hit.payload or {}

    return {
        "text": payload.get("text", ""),
        "url": payload.get("url", ""),
        "title": payload.get("title", ""),
    }
