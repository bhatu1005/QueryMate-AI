"""Schema-aware natural-language to read-only SQL specialist."""

import json
import logging
import re
from typing import Any

from config.settings import Settings, get_settings
from database.sql_validator import SQLValidationError, validate_readonly_sql
from llm.ollama_client import get_chat_model
from mcp_client.client import QueryMateMCPClient

logger = logging.getLogger(__name__)


def _tool_payload(payload: dict[str, Any], tool_name: str) -> Any:
    """Unwrap QueryMate MCP structured results or raise a safe error."""
    if payload.get("ok") is False:
        raise RuntimeError(f"{tool_name} failed: {payload.get('error', 'unknown tool error')}")
    return payload.get("result", payload)


def _extract_sql(text: str) -> str:
    """Extract SQL from plain output, a SQL fence, or a JSON field."""
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        return fence.group(1).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("sql"), str):
            return parsed["sql"].strip()
    except json.JSONDecodeError:
        pass
    start = re.search(r"\b(?:WITH|SELECT)\b", text, re.IGNORECASE)
    return text[start.start():].strip() if start else text.strip()


def run_sql_agent(
    question: str,
    settings: Settings | None = None,
    client: QueryMateMCPClient | None = None,
) -> dict[str, Any]:
    """Discover schema over MCP, generate and validate SQL, then execute via MCP."""
    active = settings or get_settings()
    owns_client = client is None
    mcp_client = client or QueryMateMCPClient(active)

    async def _run() -> dict[str, Any]:
        if owns_client:
            await mcp_client.connect()
        try:
            names = {tool.name for tool in await mcp_client.discover_tools()}
            if not {"get_database_schema", "execute_readonly_sql"}.issubset(names):
                raise RuntimeError("MCP server is missing required database tools.")
            schema_payload = await mcp_client.call_tool("get_database_schema")
            schema = _tool_payload(schema_payload, "get_database_schema")
            prompt = (
                "Generate one MySQL SELECT statement answering the question using only the given schema. "
                "Never generate writes, DDL, multiple statements, SELECT INTO, or locking reads. "
                "Return only SQL, without markdown or explanation. If the schema cannot answer it, "
                "return SELECT 1 WHERE 1 = 0.\n"
                f"Schema JSON: {json.dumps(schema, default=str)}\nQuestion: {question}"
            )
            raw = str(get_chat_model(active).invoke(prompt).content)
            candidate = _extract_sql(raw)
            validated_sql = validate_readonly_sql(candidate)
            result_payload = await mcp_client.call_tool(
                "execute_readonly_sql", {"query": validated_sql}
            )
            result = _tool_payload(result_payload, "execute_readonly_sql")
            return {
                "agent": "SQL",
                "status": "ok",
                "database_schema": schema,
                "generated_sql": validated_sql,
                "sql_validation_status": "valid_read_only_select",
                "sql_result": result,
                "output": "Database query completed.",
            }
        finally:
            if owns_client:
                await mcp_client.close()

    import asyncio
    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("SQL agent failed")
        return {
            "agent": "SQL", "status": "error", "sql_validation_status": "rejected_or_failed",
            "error": str(exc) if isinstance(exc, SQLValidationError) else "Database operation failed; check server logs.",
            "output": "I couldn't safely complete the database query.",
        }
