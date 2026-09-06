from collections import Counter

from qdrant_client import models

from assistant.config import settings
from assistant.knowledge_base import embed
from assistant.knowledge_base.store import COLLECTION, DENSE, SPARSE, client
from assistant.logging import logger

# Fused candidates are cheap; only the reranked few reach the answer prompt.
CANDIDATES = 20
# How many chunks of one page may reach it, so a single strong page cannot take
# the whole prompt from the pages that answer the rest of the question.
PER_PAGE = 2


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
    kept = _diverse(ranked, limit)
    logger.info("Retrieved %d passages, keeping %d", len(hits), len(kept))

    return [_passage(hit) for hit in kept]


def _diverse(
    ranked: list[tuple[float, models.ScoredPoint]], limit: int
) -> list[models.ScoredPoint]:
    """Cap how much of the answer prompt any one page may fill.

    A page that matches well matches in several of its chunks, and the reranker
    scores each on its own. Asked "what imaging scans can I get?", four chunks
    of one MRI article took the whole prompt and the page that lists every scan
    never appeared. Best chunks first, at most two per page, then fill any
    remaining room from what was passed over.
    """
    kept: list[models.ScoredPoint] = []
    spare: list[models.ScoredPoint] = []
    seen: Counter[str] = Counter()

    for _, hit in ranked:
        url = (hit.payload or {}).get("url", "")

        if seen[url] < PER_PAGE:
            seen[url] += 1
            kept.append(hit)
        else:
            spare.append(hit)

        if len(kept) == limit:
            return kept

    return (kept + spare)[:limit]


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
