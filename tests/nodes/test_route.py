import pytest

from assistant.nodes.route import _json, _parse
from assistant.state import Route

REPLY = '{"route": "sql", "question": "What is the fee?", "reason": "price"}'


def test_a_clean_reply_is_read():
    decision = _parse(REPLY, question="original")

    assert decision.route is Route.SQL
    assert decision.question == "What is the fee?"


def test_json_wrapped_in_prose_is_still_read():
    decision = _parse(f"Here you go:\n```json\n{REPLY}\n```", question="original")

    assert decision.route is Route.SQL


def test_an_unusable_reply_falls_back_to_searching_both_sources():
    decision = _parse("I could not decide.", question="original")

    assert decision.route is Route.BOTH
    assert decision.question == "original"


def test_an_unknown_route_falls_back_rather_than_raising():
    decision = _parse('{"route": "elsewhere", "question": "x"}', question="original")

    assert decision.route is Route.BOTH


def test_text_without_any_object_is_refused():
    with pytest.raises(ValueError):
        _json("no object here")
