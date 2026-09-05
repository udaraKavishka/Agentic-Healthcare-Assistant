import asyncio

from assistant.config import settings
from assistant.evaluate import retrieval, routing, sql

# The whole set does not fit in one minute of free-tier budget, and a batch run
# can afford to wait where a waiting patient cannot.
BATCH_WAIT_SECONDS = 90.0


def run() -> None:
    """Score the three things that can be wrong independently of each other.

    Routing can be right while retrieval returns the wrong page, and both can
    be right while a query filters on the wrong argument. One number would
    hide which of the three broke.
    """
    settings.MAX_LIMIT_WAIT_SECONDS = BATCH_WAIT_SECONDS
    asyncio.run(_all())


async def _all() -> None:
    scores = {
        "routing": await routing.score(),
        "retrieval": retrieval.score(),
        "sql execution": await sql.score(),
    }

    _summary(scores)


def _summary(scores: dict[str, float]) -> None:
    """The three scores together, after the detail that explains them.

    Read alone each one is easy to misread as the system's accuracy; read
    side by side they say which stage to look at.
    """
    print("\n== summary ==\n")

    for name, score in scores.items():
        print(f"  {name:<16} {score:>6.1%}  {_bar(score)}")

    print()


def _bar(score: float) -> str:
    filled = round(score * 20)

    return "#" * filled + "." * (20 - filled)
