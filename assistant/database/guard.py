import sqlglot
from sqlglot import expressions as exp
from sqlglot.expressions.core import Expression

from assistant.config import settings
from assistant.database.schema import ALLOWED_TABLES
from assistant.exceptions import UnsafeQueryError

# Anything that changes data or reaches outside the five tables. Checked
# structurally against the parse tree, never by matching strings: a denylist of
# keywords falls to comments, casing, and CTE-wrapped DML.
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Pragma,
    exp.Command,
    exp.Into,
)


def guard(sql: str) -> str:
    """Validate generated SQL and return it with a bounded LIMIT.

    Raises UnsafeQueryError before anything reaches the database. This runs in
    front of a connection that is already read-only, so it is the second wall,
    not the only one.
    """
    statements = _parse(sql)

    if len(statements) != 1:
        raise UnsafeQueryError("Only a single statement is allowed.")

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise UnsafeQueryError("Only SELECT statements are allowed.")

    _reject_forbidden_nodes(tree)
    _reject_unknown_tables(tree)

    return _clamp_limit(tree).sql(dialect="sqlite")


def _parse(sql: str) -> list[Expression]:
    try:
        parsed = sqlglot.parse(sql, read="sqlite")
    except sqlglot.ParseError as error:
        raise UnsafeQueryError(f"Could not parse the query: {error}") from error

    statements = [s for s in parsed if isinstance(s, Expression)]
    if not statements:
        raise UnsafeQueryError("The query was empty.")
    return statements


def _reject_forbidden_nodes(tree: Expression) -> None:
    # Walking the whole tree matters: `WITH d AS (DELETE ... RETURNING *)
    # SELECT * FROM d` has Select at the root and still deletes.
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeQueryError(
                f"{type(node).__name__.upper()} is not allowed in a query."
            )


def _reject_unknown_tables(tree: Expression) -> None:
    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    referenced = {table.name for table in tree.find_all(exp.Table)}
    unknown = referenced - ALLOWED_TABLES - cte_names

    if unknown:
        raise UnsafeQueryError(f"Unknown table(s): {', '.join(sorted(unknown))}.")


def _clamp_limit(tree: exp.Select) -> exp.Select:
    limit = tree.args.get("limit")

    if limit is None:
        return tree.limit(settings.MAX_SQL_ROWS)

    requested = limit.expression
    if (
        isinstance(requested, exp.Literal)
        and int(requested.name) > settings.MAX_SQL_ROWS
    ):
        return tree.limit(settings.MAX_SQL_ROWS)

    return tree
