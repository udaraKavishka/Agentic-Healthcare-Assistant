import pytest

from assistant.config import settings
from assistant.database.guard import guard
from assistant.exceptions import UnsafeQueryError


def test_a_plain_select_is_allowed():
    assert "doctors" in guard("SELECT name FROM doctors")


def test_a_join_across_allowed_tables_is_allowed():
    sql = guard(
        "SELECT d.name, s.name FROM doctors d JOIN specialties s ON s.id = d.specialty_id"
    )

    assert "JOIN" in sql.upper()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM doctors",
        "UPDATE doctors SET consultation_fee = 0",
        "INSERT INTO doctors (name) VALUES ('x')",
        "DROP TABLE doctors",
        "ALTER TABLE doctors ADD COLUMN x INT",
        "CREATE TABLE evil (id INT)",
    ],
)
def test_statements_that_write_are_refused(sql: str):
    with pytest.raises(UnsafeQueryError):
        guard(sql)


def test_a_write_hidden_in_a_cte_is_refused():
    """A Select sits at the root, so only walking the whole tree catches this."""
    with pytest.raises(UnsafeQueryError):
        guard("WITH gone AS (DELETE FROM doctors RETURNING *) SELECT * FROM gone")


def test_a_second_statement_is_refused():
    with pytest.raises(UnsafeQueryError):
        guard("SELECT 1; DROP TABLE doctors")


def test_tables_outside_the_schema_are_refused():
    with pytest.raises(UnsafeQueryError):
        guard("SELECT * FROM sqlite_master")


def test_attaching_another_database_is_refused():
    with pytest.raises(UnsafeQueryError):
        guard("ATTACH DATABASE '/tmp/evil.db' AS evil")


def test_pragma_is_refused():
    with pytest.raises(UnsafeQueryError):
        guard("PRAGMA table_info(doctors)")


def test_unparseable_input_is_refused():
    with pytest.raises(UnsafeQueryError):
        guard("SELECT FROM WHERE )(")


def test_an_empty_query_is_refused():
    with pytest.raises(UnsafeQueryError):
        guard("   ")


def test_a_query_without_a_limit_gets_one():
    assert f"LIMIT {settings.MAX_SQL_ROWS}" in guard("SELECT name FROM doctors").upper()


def test_an_oversized_limit_is_clamped():
    sql = guard("SELECT name FROM doctors LIMIT 5000").upper()

    assert f"LIMIT {settings.MAX_SQL_ROWS}" in sql
    assert "5000" not in sql


def test_a_modest_limit_is_left_alone():
    assert "LIMIT 3" in guard("SELECT name FROM doctors LIMIT 3").upper()


def test_a_cte_name_is_not_mistaken_for_an_unknown_table():
    sql = guard(
        "WITH cheap AS (SELECT * FROM doctors WHERE consultation_fee < 3000)"
        " SELECT name FROM cheap"
    )

    assert "cheap" in sql
