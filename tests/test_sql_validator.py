"""Safety tests for read-only SQL validation."""

import pytest

from database.sql_validator import SQLValidationError, validate_readonly_sql


def test_accepts_select() -> None:
    assert validate_readonly_sql("SELECT id FROM customers") == "SELECT id FROM customers"


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO customers(id) VALUES (1)",
        "UPDATE customers SET id = 2",
        "DELETE FROM customers",
        "DROP TABLE customers",
        "SELECT 1; DELETE FROM customers",
        "SELECT * INTO OUTFILE 'x' FROM customers",
        "SELECT * FROM customers FOR UPDATE",
        "SELECT SLEEP(10)",
        "SELECT LOAD_FILE('/etc/passwd')",
        "SELECT BENCHMARK(1000000, MD5('x'))",
    ],
)
def test_rejects_non_readonly_or_multiple_statements(query: str) -> None:
    with pytest.raises(SQLValidationError):
        validate_readonly_sql(query)
