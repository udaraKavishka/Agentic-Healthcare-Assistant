import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from assistant.config import settings
from assistant.schemas import ChatMessage

SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    route TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS turns_by_conversation ON turns (conversation_id, id);
"""


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    """Conversations live in their own database, separate from hospital data.

    Writing them beside the hospital tables would mean opening that file for
    writing, and being unable to write it is the point.
    """
    settings.CONVERSATIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.CONVERSATIONS_DB)
    connection.row_factory = sqlite3.Row

    try:
        connection.executescript(SCHEMA)
        yield connection
        connection.commit()
    finally:
        connection.close()


def history(conversation_id: str, limit: int | None = None) -> list[ChatMessage]:
    limit = limit or settings.VERBATIM_TURNS

    with _connection() as connection:
        rows = connection.execute(
            "SELECT role, content FROM turns WHERE conversation_id = ?"
            " ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()

    return [
        ChatMessage(role=row["role"], content=row["content"]) for row in reversed(rows)
    ]


def remember(
    conversation_id: str, question: str, answer: str, route: str | None = None
) -> None:
    with _connection() as connection:
        connection.executemany(
            "INSERT INTO turns (conversation_id, role, content, route)"
            " VALUES (?, ?, ?, ?)",
            [
                (conversation_id, "user", question, route),
                (conversation_id, "assistant", answer, route),
            ],
        )
