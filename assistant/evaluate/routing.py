import statistics
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter

import yaml

from assistant.config import ROOT
from assistant.nodes import faq
from assistant.nodes.route import route
from assistant.state import Route

QUESTIONS = ROOT / "evals" / "questions.yml"


async def score() -> float:
    print("\n== routing ==\n")
    cases = yaml.safe_load(Path(QUESTIONS).read_text())

    confusion: Counter[tuple[str, str]] = Counter()
    misses: list[tuple[str, str, str]] = []
    latencies: dict[str, list[float]] = defaultdict(list)

    for case in cases:
        actual, seconds = await _decide(case["question"])
        expected = case["route"]

        confusion[(expected, actual)] += 1
        latencies[expected].append(seconds)

        if expected != actual:
            misses.append((case["question"], expected, actual))

    correct = sum(
        count for (expected, actual), count in confusion.items() if expected == actual
    )
    _report(confusion, misses, correct, len(cases))
    _timings(latencies)

    return correct / len(cases)


async def _decide(question: str) -> tuple[str, float]:
    """The decision the pipeline would make, and what it cost.

    The FAQ gate runs first here for the same reason it does in the pipeline:
    measuring the router on a question the router never sees would report a
    latency no patient experiences.
    """
    started = perf_counter()

    if faq.lookup(question) is not None:
        return Route.FAQ.value, perf_counter() - started

    decision = await route(question, history=[])

    return decision.route.value, perf_counter() - started


def _report(
    confusion: Counter[tuple[str, str]],
    misses: list[tuple[str, str, str]],
    correct: int,
    total: int,
) -> None:
    labels = [chosen.value for chosen in Route]
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


def _timings(latencies: dict[str, list[float]]) -> None:
    """How long the routing decision took, by the route it should reach.

    The FAQ row is the one worth reading: it answers without reaching a model
    at all, so it is measured in milliseconds where the rest are in seconds.
    """
    print("\nrouting decision, median per route")

    for chosen in Route:
        seconds = latencies.get(chosen.value)

        if not seconds:
            continue

        median = statistics.median(seconds) * 1000
        print(f"  {chosen.value:8s} {len(seconds):2d} cases  {median:7.0f} ms")
