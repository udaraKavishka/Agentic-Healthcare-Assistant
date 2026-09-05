import pytest

from assistant.nodes import retrieve_sql


async def test_a_question_no_query_matches_retrieves_nothing(
    monkeypatch: pytest.MonkeyPatch,
):
    """An unmatched question must abstain, not fall back to the doctor list.

    Non-empty passages satisfy the answer model's evidence gate, so a fallback
    row set would have it answer an imaging question from consultant records.
    """

    async def nothing(_: str) -> list[tuple[str, dict]]:
        return []

    monkeypatch.setattr(retrieve_sql, "chosen", nothing)

    assert await retrieve_sql.retrieve("how much is an MRI scan?") == []
