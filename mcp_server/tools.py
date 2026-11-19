"""MCP tool handlers with argument validation and safe structured results."""

import logging
import re
from typing import Any

from database.query_executor import execute_readonly_sql as run_sql
from database.schema_manager import describe_table as describe_db_table
from database.schema_manager import get_database_schema as read_database_schema
from database.schema_manager import list_tables as read_table_names
from rag.retriever import retrieve_documents
from rag.vector_store import list_documents
from rag.vector_store import _get_store

logger = logging.getLogger(__name__)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def _tool_call(name: str, fn, *args: Any, **kwargs: Any) -> dict[str, Any]:
    logger.info("MCP tool started: %s", name)
    try:
        result = fn(*args, **kwargs)
        return {"ok": True, "result": result}
    except Exception as exc:
        logger.exception("MCP tool failed: %s", name)
        # Driver/client exceptions can contain connection strings or local paths.
        safe_error = str(exc) if isinstance(exc, (ValueError, TypeError)) else "Operation failed. Check server logs for details."
        return {"ok": False, "error": safe_error}


def list_tables() -> dict[str, Any]:
    """List table names in the configured MySQL database."""
    return _tool_call("list_tables", read_table_names)


def get_database_schema() -> dict[str, Any]:
    """Return table and column metadata for the configured MySQL database."""
    return _tool_call("get_database_schema", read_database_schema)


def describe_table(table_name: str) -> dict[str, Any]:
    """Return columns, data types, nullability, keys, and defaults for one table."""
    if not isinstance(table_name, str) or not _SAFE_IDENTIFIER.fullmatch(table_name):
        return {"ok": False, "error": "table_name must be a valid SQL identifier."}
    return _tool_call("describe_table", describe_db_table, table_name)


def execute_readonly_sql(query: str) -> dict[str, Any]:
    """Validate and execute a single read-only SELECT query."""
    if not isinstance(query, str) or not query.strip() or len(query) > 20_000:
        return {"ok": False, "error": "query must be a non-empty SQL string under 20000 characters."}
    return _tool_call("execute_readonly_sql", run_sql, query)


def search_documents(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search uploaded document chunks semantically and return source metadata."""
    if not isinstance(query, str) or not query.strip() or len(query) > 10_000:
        return {"ok": False, "error": "query must be a non-empty string under 10000 characters."}
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
        return {"ok": False, "error": "top_k must be an integer between 1 and 20."}
    return _tool_call("search_documents", retrieve_documents, query, top_k)


def list_uploaded_documents() -> dict[str, Any]:
    """List indexed documents without exposing local filesystem paths."""
    return _tool_call("list_uploaded_documents", list_documents)


def get_document_content(document_id: str) -> dict[str, Any]:
    """Retrieve indexed chunks for a known content-derived document ID."""
    if not isinstance(document_id, str) or not re.fullmatch(r"[a-f0-9]{64}", document_id):
        return {"ok": False, "error": "document_id must be a valid document identifier."}

    def read_chunks() -> list[dict[str, Any]]:
        collection = _get_store(with_embeddings=False)._collection
        result = collection.get(where={"document_id": document_id}, include=["documents", "metadatas"])
        return [
            {"content": content, "metadata": metadata}
            for content, metadata in zip(result.get("documents", []) or [], result.get("metadatas", []) or [])
        ]

    return _tool_call("get_document_content", read_chunks)
