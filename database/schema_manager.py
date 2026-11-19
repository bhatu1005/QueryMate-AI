"""Read database table and column metadata from MySQL information_schema."""

from typing import Any

from config.settings import Settings, get_settings
from database.connection import connect_readonly


def list_tables(settings: Settings | None = None) -> list[str]:
    """Return base table names in the configured database."""
    active = settings or get_settings()
    connection = connect_readonly(active)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME",
            (active.mysql_database,),
        )
        return [str(row[0]) for row in cursor.fetchall()]
    finally:
        connection.close()


def get_database_schema(settings: Settings | None = None) -> dict[str, list[dict[str, Any]]]:
    """Return table and column metadata for the configured schema."""
    active = settings or get_settings()
    connection = connect_readonly(active)
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, "
            "COLUMN_DEFAULT, EXTRA FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION",
            (active.mysql_database,),
        )
        result: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            table = str(row["TABLE_NAME"])
            result.setdefault(table, []).append(
                {key.lower(): value for key, value in row.items() if key != "TABLE_NAME"}
            )
        return result
    finally:
        connection.close()


def describe_table(table_name: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Return column details for a validated table name in the configured schema."""
    if not table_name or len(table_name) > 128 or not table_name.replace("_", "").isalnum():
        raise ValueError("Invalid table name.")
    schema = get_database_schema(settings)
    if table_name not in schema:
        raise ValueError(f"Table '{table_name}' does not exist in the configured database.")
    return schema[table_name]
