import asyncio
from collections import Counter
from pathlib import Path

import yaml

from assistant.config import ROOT, settings
from assistant.nodes.route import route
from assistant.state import Route

QUESTIONS = ROOT / "evals" / "questions.yml"
# The whole set does not fit in one minute of free-tier budget, and a batch
# run can afford to wait where a waiting patient cannot.
BATCH_WAIT_SECONDS = 90.0


async def routing() -> float:
    settings.MAX_LIMIT_WAIT_SECONDS = BATCH_WAIT_SECONDS
    cases = yaml.safe_load(Path(QUESTIONS).read_text())
    confusion: Counter[tuple[str, str]] = Counter()
    misses: list[tuple[str, str, str]] = []

    for case in cases:
        decision = await route(case["question"], history=[])
        expected, actual = case["route"], decision.route.value
        confusion[(expected, actual)] += 1

        if expected != actual:
            misses.append((case["question"], expected, actual))

    correct = sum(
        count for (expected, actual), count in confusion.items() if expected == actual
    )
    _report(confusion, misses, correct, len(cases))

    return correct / len(cases)


def _report(
    confusion: Counter[tuple[str, str]],
    misses: list[tuple[str, str, str]],
    correct: int,
    total: int,
) -> None:
    labels = [route.value for route in Route]
    header = "expected \\ actual".ljust(20) + "".join(
        label.ljust(9) for label in labels
    )
    print(header)

    for expected in labels:
        row = "".join(str(confusion[(expected, actual)]).ljust(9) for actual in labels)
        print(expected.ljust(20) + row)

    print(f"\nrouting accuracy: {correct}/{total} = {correct / total:.1%}")

    for question, expected, actual in misses:
        print(f"  expected {expected:7s} got {actual:7s}  {question}")


def run() -> float:
    return asyncio.run(routing())
