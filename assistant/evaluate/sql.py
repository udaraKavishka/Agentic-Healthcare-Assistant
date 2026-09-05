from pathlib import Path

import yaml

from assistant.config import ROOT
from assistant.nodes import retrieve_sql
from assistant.tools.definitions import BY_NAME

QUESTIONS = ROOT / "evals" / "sql.yml"


async def score() -> float:
    """Whether the database route returns the rows the question asked for.

    A query can be routed correctly, call the right template, and still answer
    wrongly because an argument was lifted from the sentence instead of naming
    the row. Only the rows that come back show that.
    """
    print("\n== sql execution ==\n")
    cases = yaml.safe_load(Path(QUESTIONS).read_text())
    faults = [await _fault(case) for case in cases]
    passed = faults.count("")

    for case, fault in zip(cases, faults, strict=True):
        print(f"  {'ok  ' if not fault else 'FAIL'}  {case['question']}")

        if fault:
            print(f"          {fault}")

    print(
        f"\nsql execution accuracy: {passed}/{len(cases)} = {passed / len(cases):.1%}"
    )

    return passed / len(cases)


async def _fault(case: dict) -> str:
    """What went wrong with this case, or an empty string if nothing did."""
    calls = await retrieve_sql.chosen(case["question"])
    names = [name for name, _ in calls]

    if case["tool"] not in names:
        return f"called {names or 'nothing'}, expected {case['tool']}"

    rows = _rows(calls)
    missing = [want for want in case["expect"] if want.lower() not in rows]
    leaked = [avoid for avoid in case.get("absent", []) if avoid.lower() in rows]

    if missing:
        return f"missing from the rows: {missing}"

    if leaked:
        return f"returned rows it should have filtered out: {leaked}"

    return ""


def _rows(calls: list[tuple[str, dict]]) -> str:
    """Every row every chosen query returned, as one lowercased haystack."""
    found = []

    for name, arguments in calls:
        tool = BY_NAME.get(name)

        if tool is None:
            continue

        found += tool.run(**arguments)

    return "\n".join(str(value) for row in found for value in row.values()).lower()
