from pathlib import Path

import yaml

from assistant.config import ROOT, settings
from assistant.knowledge_base import search

QUESTIONS = ROOT / "evals" / "retrieval.yml"


def score() -> float:
    """How often the page that holds the answer reaches the answer prompt.

    Routing accuracy says the question went to the vector store. It says
    nothing about whether the store came back with the right page, which is
    the half of retrieval a patient actually feels.
    """
    print("\n== retrieval ==\n")
    cases = yaml.safe_load(Path(QUESTIONS).read_text())
    ranks = [_rank(case["question"], case["sources"]) for case in cases]

    hits = [rank for rank in ranks if rank]
    reciprocal = sum(1 / rank for rank in hits) / len(ranks)

    for case, rank in zip(cases, ranks, strict=True):
        place = f"rank {rank}" if rank else "MISS    "
        print(f"  {place}  {case['question']}")

    print(
        f"\nhit@{settings.RETRIEVE_TOP_K}: {len(hits)}/{len(ranks)}"
        f" = {len(hits) / len(ranks):.1%}   mean reciprocal rank: {reciprocal:.2f}"
    )

    return len(hits) / len(ranks)


def _rank(question: str, sources: list[str]) -> int:
    """Where the first acceptable page lands, or 0 if it never does."""
    for position, passage in enumerate(search.search(question), start=1):
        if any(source in passage["url"] for source in sources):
            return position

    return 0
