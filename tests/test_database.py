"""Database tool unit tests and read-only dedicated-database integration checks."""

import os

import pytest

from config.settings import Settings
from database import query_executor, schema_manager
from database.sql_validator import SQLValidationError
from services import health_service


def test_readonly_executor_sets_safety_limits_and_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    executed = []

    class Cursor:
        column_names = ("id",)

        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchmany(self, count):
            return [{"id": 7}, {"id": 8}][:count]

        def close(self):
            return None

    class Connection:
        closed = False
        rolled_back = False

        def cursor(self, dictionary=False):
            assert dictionary is True
            return Cursor()

        def start_transaction(self, readonly=False):
            assert readonly is True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(query_executor, "connect_readonly", lambda settings: connection)
    result = query_executor.execute_readonly_sql(
        "SELECT id FROM customers", Settings(sql_max_rows=1, sql_query_timeout_seconds=3)
    )
    assert result == {"columns": ["id"], "rows": [{"id": 7}], "row_count": 1, "truncated": True}
    assert executed == [("SET SESSION MAX_EXECUTION_TIME = %s", (3000,)), ("SELECT id FROM customers", None)]
    assert connection.rolled_back and connection.closed


def test_invalid_sql_never_opens_a_database_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def should_not_connect(settings):
        raise AssertionError("connection must not be opened for invalid SQL")

    monkeypatch.setattr(query_executor, "connect_readonly", should_not_connect)
    with pytest.raises(SQLValidationError):
        query_executor.execute_readonly_sql("DELETE FROM customers")


def test_schema_helpers_use_parameterized_database_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    class Cursor:
        def __init__(self, dictionary=False):
            self.dictionary = dictionary
            self.query = ""
            self.params = ()

        def execute(self, query, params=()):
            self.query, self.params = query, params

        def fetchall(self):
            if self.dictionary:
                return [{"TABLE_NAME": "customers", "COLUMN_NAME": "id", "COLUMN_TYPE": "int", "IS_NULLABLE": "NO", "COLUMN_KEY": "PRI", "COLUMN_DEFAULT": None, "EXTRA": ""}]
            return [("customers",)]

    class Connection:
        def cursor(self, dictionary=False):
            return Cursor(dictionary)

        def close(self):
            return None

    monkeypatch.setattr(schema_manager, "connect_readonly", lambda settings: Connection())
    assert schema_manager.list_tables(Settings(mysql_database="querymate_test")) == ["customers"]
    schema = schema_manager.get_database_schema(Settings(mysql_database="querymate_test"))
    assert schema["customers"][0]["column_name"] == "id"
    assert schema_manager.describe_table("customers", Settings(mysql_database="querymate_test"))[0]["column_type"] == "int"


def test_database_health_check(monkeypatch: pytest.MonkeyPatch) -> None:
    class Cursor:
        def execute(self, query):
            assert query == "SELECT 1"

        def fetchone(self):
            return (1,)

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            return None

    monkeypatch.setattr(health_service, "connect_readonly", lambda settings: Connection())
    assert health_service.check_database(Settings()) == (True, "Connected")


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("QUERYMATE_RUN_INTEGRATION") != "1" or not os.getenv("QUERYMATE_TEST_MYSQL_DATABASE"),
    reason="set QUERYMATE_RUN_INTEGRATION=1 and QUERYMATE_TEST_MYSQL_DATABASE to a dedicated test database",
)
def test_mysql_readonly_integration() -> None:
    database_name = os.environ["QUERYMATE_TEST_MYSQL_DATABASE"]
    if not database_name.startswith("querymate_test"):
        pytest.fail("Refusing integration tests unless the database name starts with querymate_test")
    settings = Settings(mysql_database=database_name)
    connection = query_executor.connect_readonly(settings)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
    finally:
        connection.close()
    assert schema_manager.list_tables(settings)
    assert schema_manager.get_database_schema(settings)
    assert query_executor.execute_readonly_sql("SELECT 1 AS test_value", settings)["rows"] == [{"test_value": 1}]
    # No writes or schema changes are executed by this integration test.
