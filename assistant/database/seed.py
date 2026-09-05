import re
import sqlite3
from pathlib import Path

from assistant.config import settings
from assistant.logging import logger

# data.sql is MySQL: `INT PRIMARY KEY AUTO_INCREMENT` parses in neither SQLite
# nor Postgres. The provided file is an input and stays untouched, so the
# dialect is shimmed here at load time instead.
MYSQL_FIXUPS = (
    (
        re.compile(r"\bINT\s+PRIMARY\s+KEY\s+AUTO_INCREMENT\b", re.IGNORECASE),
        "INTEGER PRIMARY KEY",
    ),
    (re.compile(r"\bAUTO_INCREMENT\b", re.IGNORECASE), ""),
)


def to_sqlite(sql: str) -> str:
    for pattern, replacement in MYSQL_FIXUPS:
        sql = pattern.sub(replacement, sql)
    return sql


def seed(source: Path | None = None, target: Path | None = None) -> Path:
    source = source or settings.SOURCE_SQL
    target = target or settings.HOSPITAL_DB
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)

    connection = sqlite3.connect(target)
    try:
        connection.executescript(to_sqlite(source.read_text()))
        connection.commit()
    finally:
        connection.close()

    logger.info("Seeded %s from %s", target, source)
    return target
