import statistics
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter

import yaml

from assistant.config import ROOT
from assistant.nodes import faq
from assistant.nodes.route import route
from assistant.schemas import ChatMessage
from assistant.state import Route

QUESTIONS = ROOT / "evals" / "questions.yml"


async def score() -> float:
    print("\n== routing ==\n")
    cases = yaml.safe_load(Path(QUESTIONS).read_text())

    confusion: Counter[tuple[str, str]] = Counter()
    misses: list[tuple[str, str, str]] = []
    followups: list[tuple[dict, list[str]]] = []
    latencies: dict[str, list[float]] = defaultdict(list)

    for case in cases:
        actual, seconds, rewritten = await _decide(case)
        expected = case["route"]

        confusion[(expected, actual)] += 1
        latencies[expected].append(seconds)

        if expected != actual:
            misses.append((case["question"], expected, actual))

        if case.get("history"):
            followups.append((case, _unresolved(case, rewritten)))

    correct = sum(
        count for (expected, actual), count in confusion.items() if expected == actual
    )
    _report(confusion, misses, correct, len(cases))
    _timings(latencies)
    _memory(followups)

    return correct / len(cases)


async def _decide(case: dict) -> tuple[str, float, str]:
    """The decision the pipeline would make, and what it cost.

    The FAQ gate runs first here for the same reason it does in the pipeline:
    measuring the router on a question the router never sees would report a
    latency no patient experiences.

    A case may carry the turns before it. Without them a follow-up like "what
    does he charge?" is unroutable, so history is what makes multi-turn cases
    measurable rather than a demonstration.
    """
    question = case["question"]
    started = perf_counter()

    if faq.lookup(question) is not None:
        return Route.FAQ.value, perf_counter() - started, question

    decision = await route(question, history=_history(case))

    return decision.route.value, perf_counter() - started, decision.question


def _history(case: dict) -> list[ChatMessage]:
    return [ChatMessage(**turn) for turn in case.get("history", [])]


def _unresolved(case: dict, rewritten: str) -> list[str]:
    """What the rewrite was supposed to pull out of the conversation and did not.

    Routing a follow-up correctly is half of memory. The other half is that the
    question standing on its own names what the pronoun referred to.
    """
    return [
        wanted
        for wanted in case.get("resolves", [])
        if wanted.lower() not in rewritten.lower()
    ]


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


def _memory(followups: list[tuple[dict, list[str]]]) -> None:
    """Whether a follow-up was understood, not merely routed."""
    if not followups:
        return

    print("\n multi-turn: does the follow-up resolve against the conversation\n")

    for case, missing in followups:
        mark = "ok  " if not missing else "FAIL"
        print(f"  {mark}  {case['question']}")

        if missing:
            print(f"          did not resolve: {missing}")

    resolved = sum(1 for _, missing in followups if not missing)
    print(f"\n follow-ups resolved: {resolved}/{len(followups)}")
