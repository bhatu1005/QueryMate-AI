"""Strict SQL validation for MySQL read-only queries."""

import sqlglot
from sqlglot import exp


class SQLValidationError(ValueError):
    """Raised when SQL is outside the permitted read-only subset."""


def validate_readonly_sql(query: str) -> str:
    """Validate a single SELECT statement and return normalized SQL text."""
    if not isinstance(query, str) or not query.strip():
        raise SQLValidationError("Query must be a non-empty string.")
    try:
        statements = sqlglot.parse(query, read="mysql")
    except sqlglot.errors.ParseError as exc:
        raise SQLValidationError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1 or statements[0] is None:
        raise SQLValidationError("Exactly one SQL statement is allowed.")
    expression = statements[0]
    if not isinstance(expression, exp.Select):
        raise SQLValidationError("Only SELECT queries are allowed.")
    forbidden = tuple(
        kind
        for kind in (
            getattr(exp, "Insert", None), getattr(exp, "Update", None), getattr(exp, "Delete", None),
            getattr(exp, "Drop", None), getattr(exp, "Alter", None), getattr(exp, "Create", None),
            getattr(exp, "TruncateTable", None), getattr(exp, "Command", None),
            getattr(exp, "Transaction", None), getattr(exp, "Commit", None),
            getattr(exp, "Rollback", None), getattr(exp, "Merge", None),
        )
        if kind is not None
    )
    if any(expression.find(kind) is not None for kind in forbidden):
        raise SQLValidationError("Query contains a prohibited operation.")
    # MySQL SELECT INTO writes output to a file or variable and is not allowed.
    if expression.args.get("into") is not None:
        raise SQLValidationError("SELECT INTO is not allowed.")
    if expression.args.get("locks"):
        raise SQLValidationError("Locking SELECT clauses are not allowed.")
    unsafe_functions = {"SLEEP", "BENCHMARK", "LOAD_FILE", "GET_LOCK", "RELEASE_LOCK", "RELEASE_ALL_LOCKS"}
    for function in expression.find_all(exp.Func):
        function_name = str(
            function.name if isinstance(function, exp.Anonymous) else function.sql_name()
        ).upper()
        if function_name in unsafe_functions:
            raise SQLValidationError(f"Function {function_name} is not allowed in read-only queries.")
    return expression.sql(dialect="mysql")
