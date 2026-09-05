import sqlite3
from pathlib import Path

from assistant.config import settings
from assistant.database.seed import seed, to_sqlite


def test_mysql_autoincrement_becomes_a_sqlite_primary_key():
    ddl = "CREATE TABLE t (id INT PRIMARY KEY AUTO_INCREMENT, name TEXT);"

    assert to_sqlite(ddl) == "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT);"


def test_the_provided_file_loads(tmp_path: Path):
    target = seed(source=settings.SOURCE_SQL, target=tmp_path / "hospital.db")
    connection = sqlite3.connect(target)

    counts = {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in (
            "specialties",
            "doctors",
            "channeling_sessions",
            "lab_tests",
            "health_packages",
        )
    }
    connection.close()

    assert counts == {
        "specialties": 10,
        "doctors": 11,
        "channeling_sessions": 15,
        "lab_tests": 17,
        "health_packages": 11,
    }


def test_seeding_twice_does_not_duplicate_rows(tmp_path: Path):
    target = tmp_path / "hospital.db"
    seed(source=settings.SOURCE_SQL, target=target)
    seed(source=settings.SOURCE_SQL, target=target)

    connection = sqlite3.connect(target)
    doctors = connection.execute("SELECT count(*) FROM doctors").fetchone()[0]
    connection.close()

    assert doctors == 11
