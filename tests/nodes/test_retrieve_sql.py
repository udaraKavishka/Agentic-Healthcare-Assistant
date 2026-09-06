import pytest

from assistant.nodes import retrieve_sql

pytestmark = pytest.mark.usefixtures("hospital_db")


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


async def test_an_absent_speciality_comes_back_with_the_ones_that_exist(
    monkeypatch: pytest.MonkeyPatch,
):
    """ "We do not have that" alone leaves the patient where they started.

    The next question is always "then what do you have", and the answer is one
    query away, so it travels with the abstention rather than after it.
    """

    async def eye_surgeon(_: str) -> list[tuple[str, dict]]:
        return [("find_doctors", {"specialty": "eye surgeon"})]

    monkeypatch.setattr(retrieve_sql, "chosen", eye_surgeon)
    passages = await retrieve_sql.retrieve("are there any eye surgeons?")
    evidence = "\n".join(passage.content for passage in passages)

    assert "Cardiology" in evidence
    assert "Ophthalmology" not in evidence


async def test_a_question_that_named_no_speciality_gets_no_list(
    monkeypatch: pytest.MonkeyPatch,
):
    """The list answers "which speciality", so an unfiltered miss must not get it."""

    async def any_doctor(_: str) -> list[tuple[str, dict]]:
        return [("find_doctors", {"max_fee": 1})]

    monkeypatch.setattr(retrieve_sql, "chosen", any_doctor)

    assert await retrieve_sql.retrieve("any doctor under one rupee?") == []
