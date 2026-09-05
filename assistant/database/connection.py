import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from assistant.config import settings

# How often SQLite pauses to ask whether it should keep going. Low enough that
# a runaway query is stopped promptly, high enough not to slow ordinary ones.
PROGRESS_INSTRUCTIONS = 10_000


@contextmanager
def read_only() -> Iterator[sqlite3.Connection]:
    """A connection that cannot write, guaranteed by the driver.

    `mode=ro` is the OS-level guarantee and `query_only` is the second wall, so
    the assistant cannot modify hospital data even if every check above it is
    bypassed.
    """
    connection = sqlite3.connect(f"file:{settings.HOSPITAL_DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.set_progress_handler(_deadline(), PROGRESS_INSTRUCTIONS)

    try:
        connection.execute("PRAGMA query_only = ON")
        yield connection
    finally:
        connection.close()


def fetch(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with read_only() as connection:
        rows = connection.execute(sql, params or {}).fetchall()

    return [dict(row) for row in rows]


def _deadline() -> Callable[[], int]:
    """Abort a query that outstays its welcome.

    `sqlite3.connect(timeout=...)` bounds how long a call waits for a lock, not
    how long a query runs, so a query that joins its way to a huge result would
    otherwise hold the request open indefinitely. Returning true from the
    progress handler interrupts it.
    """
    expires_at = time.monotonic() + settings.SQL_TIMEOUT_SECONDS

    def expired() -> int:
        return int(time.monotonic() > expires_at)

    return expired
