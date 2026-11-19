"""Execute validated SELECT statements inside read-only MySQL transactions."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from config.settings import Settings, get_settings
from database.connection import connect_readonly
from database.sql_validator import validate_readonly_sql


def _json_safe(value: Any) -> Any:
    """Convert common MySQL values to JSON-compatible representations."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def execute_readonly_sql(query: str, settings: Settings | None = None) -> dict[str, Any]:
    """Validate and execute one SELECT, enforcing read-only transaction and row cap."""
    active = settings or get_settings()
    safe_query = validate_readonly_sql(query)
    connection = connect_readonly(active)
    cursor = None
    transaction_started = False
    try:
        # Start the read-only transaction before issuing any SQL so no statement
        # can run outside the transaction's access mode.
        connection.start_transaction(readonly=True)
        transaction_started = True
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SET SESSION MAX_EXECUTION_TIME = %s",
            (int(active.sql_query_timeout_seconds * 1000),),
        )
        cursor.execute(safe_query)
        rows = [
            {str(key): _json_safe(value) for key, value in row.items()}
            for row in cursor.fetchmany(active.sql_max_rows + 1)
        ]
        truncated = len(rows) > active.sql_max_rows
        rows = rows[: active.sql_max_rows]
        return {
            "columns": list(cursor.column_names),
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
    finally:
        if transaction_started:
            connection.rollback()
        if cursor is not None:
            cursor.close()
        connection.close()
