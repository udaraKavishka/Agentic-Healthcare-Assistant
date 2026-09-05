import pytest

from assistant import pipeline
from assistant.exceptions import UpstreamBusyError
from assistant.nodes import faq, route


async def test_an_unexpected_failure_is_answered_not_dropped(
    monkeypatch: pytest.MonkeyPatch,
):
    """The response is already streaming, so an exception cannot reach the server.

    Letting it propagate aborts the connection mid-answer: the patient sees a
    transport error and the turn is never recorded.
    """
    recorded: list[tuple[str, str, str]] = []

    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("the vector store went away")

    monkeypatch.setattr(faq, "lookup", lambda _: None)
    monkeypatch.setattr(route, "route", boom)
    monkeypatch.setattr(pipeline.store, "history", lambda _: [])
    monkeypatch.setattr(
        pipeline.store,
        "remember",
        lambda conversation, question, answer, taken: recorded.append(
            (conversation, answer, taken)
        ),
    )

    events = [event async for event in pipeline.run("c1", "who works on Sunday?")]
    kinds = [event.kind for event in events]

    assert kinds[-1] == "done"
    assert "error" in kinds
    assert recorded and recorded[0][1].startswith("Something went wrong")


async def test_a_shed_turn_says_the_assistant_is_busy(monkeypatch: pytest.MonkeyPatch):
    """Any stage can hit the rate limit, and the reason must survive to the user.

    Retrieval calls the model to pick a query, so a limit reached there is not
    a fault: replacing it with a generic apology loses the wait time.
    """
    recorded: list[str] = []

    def busy(*_: object, **__: object) -> None:
        raise UpstreamBusyError("The assistant is busy. Try again in 9 seconds.")

    monkeypatch.setattr(faq, "lookup", lambda _: None)
    monkeypatch.setattr(route, "route", busy)
    monkeypatch.setattr(pipeline.store, "history", lambda _: [])
    monkeypatch.setattr(
        pipeline.store,
        "remember",
        lambda conversation, question, answer, taken: recorded.append(answer),
    )

    events = [
        event async for event in pipeline.run("c2", "who are your cardiologists?")
    ]
    errors = [event.value for event in events if event.kind == "error"]

    assert errors == ["The assistant is busy. Try again in 9 seconds."]
    assert recorded == errors
