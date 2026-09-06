from pathlib import Path

import pytest

from assistant.config import settings
from assistant.memory import store


@pytest.fixture(autouse=True)
def conversations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A conversation database the tests own, created on first use."""
    target = tmp_path / "conversations.db"
    monkeypatch.setattr(settings, "CONVERSATIONS_DB", target)

    return target


def test_a_turn_survives_the_process_that_wrote_it(conversations: Path):
    """Memory is persistent, not in process. A restart must not forget."""
    store.remember("c1", "Who are your cardiologists?", "Dr Priyadarshan.", "sql")

    assert conversations.exists()
    assert [message.content for message in store.history("c1")] == [
        "Who are your cardiologists?",
        "Dr Priyadarshan.",
    ]


def test_history_comes_back_oldest_first():
    """The rewrite reads it as a conversation, so the order is the meaning."""
    store.remember("c1", "first question", "first answer")
    store.remember("c1", "second question", "second answer")

    assert [message.content for message in store.history("c1")] == [
        "first question",
        "first answer",
        "second question",
        "second answer",
    ]


def test_one_conversation_cannot_read_another():
    """Two browsers share a process, so a leak here would put one patient's
    question into another patient's answer."""
    store.remember("c1", "my question", "my answer")
    store.remember("c2", "their question", "their answer")

    assert [message.content for message in store.history("c2")] == [
        "their question",
        "their answer",
    ]


def test_only_the_recent_window_is_returned():
    """Bounded, so a long conversation cannot eat the minute's token budget."""
    for turn in range(10):
        store.remember("c1", f"question {turn}", f"answer {turn}")

    recent = store.history("c1")

    assert len(recent) == settings.VERBATIM_TURNS
    assert recent[-1].content == "answer 9"


def test_an_unknown_conversation_is_empty_rather_than_an_error():
    assert store.history("never-seen") == []
