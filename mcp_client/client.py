"""Async stdio MCP client with discovery and LangChain tool adaptation."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import Field, create_model

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class MCPClientError(RuntimeError):
    """Raised for MCP connection, discovery, or tool invocation failures."""


def _python_type(schema: dict[str, Any]) -> Any:
    """Map JSON Schema primitive input types to Python types."""
    return {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}.get(
        schema.get("type"), Any
    )


class QueryMateMCPClient:
    """Manage a protocol-level stdio session to the QueryMate MCP server."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._tools: list[Any] = []

    async def connect(self) -> None:
        """Start the configured server subprocess and complete MCP initialization."""
        if self._session is not None:
            return
        root = Path(__file__).resolve().parents[1]
        command = self.settings.mcp_server_command
        args = self.settings.mcp_server_args.split()
        if args == ["mcp_server/server.py"]:
            args = ["-m", "mcp_server.server"]
        # stdio_client deliberately starts children with a restricted environment.
        # Forward only the settings the trusted local MCP server needs.
        server_env = {
            "APP_NAME": self.settings.app_name,
            "APP_ENV": self.settings.app_env,
            "LOG_LEVEL": self.settings.log_level,
            "OLLAMA_BASE_URL": self.settings.ollama_base_url,
            "OLLAMA_CHAT_MODEL": self.settings.ollama_chat_model,
            "OLLAMA_EMBEDDING_MODEL": self.settings.ollama_embedding_model,
            "OLLAMA_TEMPERATURE": str(self.settings.ollama_temperature),
            "OLLAMA_TIMEOUT_SECONDS": str(self.settings.ollama_timeout_seconds),
            "MYSQL_HOST": self.settings.mysql_host,
            "MYSQL_PORT": str(self.settings.mysql_port),
            "MYSQL_DATABASE": self.settings.mysql_database,
            "MYSQL_USER": self.settings.mysql_user,
            "MYSQL_PASSWORD": self.settings.mysql_password.get_secret_value(),
            "MYSQL_CONNECT_TIMEOUT": str(self.settings.mysql_connect_timeout),
            "SQL_MAX_ROWS": str(self.settings.sql_max_rows),
            "SQL_QUERY_TIMEOUT_SECONDS": str(self.settings.sql_query_timeout_seconds),
            "UPLOAD_DIR": str(self.settings.upload_dir),
            "CHROMA_PERSIST_DIR": str(self.settings.chroma_persist_dir),
            "MAX_UPLOAD_SIZE_MB": str(self.settings.max_upload_size_mb),
            "CHUNK_SIZE": str(self.settings.chunk_size),
            "CHUNK_OVERLAP": str(self.settings.chunk_overlap),
            "RETRIEVAL_TOP_K": str(self.settings.retrieval_top_k),
            "RETRIEVAL_MIN_RELEVANCE_SCORE": str(self.settings.retrieval_min_relevance_score),
        }
        params = StdioServerParameters(command=command, args=args, cwd=str(root), env=server_env)
        self._stack = AsyncExitStack()
        try:
            read, write = await self._stack.enter_async_context(stdio_client(params))
            self._session = await self._stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()
            logger.info("Connected to QueryMate MCP server over stdio")
        except Exception as exc:
            await self.close()
            raise MCPClientError(f"Could not connect to QueryMate MCP server: {exc}") from exc

    async def close(self) -> None:
        """Close the MCP session and subprocess transport."""
        if self._stack is not None:
            try:
                await self._stack.aclose()
            finally:
                self._stack = None
                self._session = None
                self._tools = []

    async def __aenter__(self) -> "QueryMateMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def discover_tools(self, refresh: bool = False) -> list[Any]:
        """Discover and return MCP tool descriptions and JSON input schemas."""
        await self.connect()
        if refresh or not self._tools:
            try:
                result = await self._session.list_tools()  # type: ignore[union-attr]
                self._tools = result.tools
            except Exception as exc:
                raise MCPClientError(f"Could not discover MCP tools: {exc}") from exc
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invoke one discovered MCP tool and return structured content."""
        tools = await self.discover_tools()
        tool = next((candidate for candidate in tools if candidate.name == name), None)
        if tool is None:
            raise MCPClientError(f"Unknown MCP tool: {name}")
        try:
            result = await self._session.call_tool(name, arguments or {})  # type: ignore[union-attr]
        except Exception as exc:
            raise MCPClientError(f"MCP tool '{name}' failed: {exc}") from exc
        if result.isError:
            detail = "; ".join(getattr(item, "text", "") for item in result.content)
            raise MCPClientError(f"MCP tool '{name}' returned an error: {detail}")
        if result.structuredContent is not None:
            return result.structuredContent
        return {"content": [getattr(item, "text", str(item)) for item in result.content]}

    async def get_langchain_tools(self) -> list[Any]:
        """Wrap discovered MCP tools as LangChain StructuredTool instances."""
        from langchain_core.tools import StructuredTool

        discovered = await self.discover_tools(refresh=True)
        adapted = []
        for mcp_tool in discovered:
            input_schema = mcp_tool.inputSchema or {"type": "object", "properties": {}}
            properties = input_schema.get("properties", {})
            required = set(input_schema.get("required", []))
            fields = {
                field_name: (
                    _python_type(field_schema),
                    Field(... if field_name in required else field_schema.get("default", None), description=field_schema.get("description")),
                )
                for field_name, field_schema in properties.items()
            }
            schema_model = create_model(f"{mcp_tool.name.title().replace('_', '')}Input", **fields)

            async def invoke(_name: str = mcp_tool.name, **kwargs: Any) -> dict[str, Any]:
                return await self.call_tool(_name, kwargs)

            adapted.append(
                StructuredTool(
                    name=mcp_tool.name,
                    description=mcp_tool.description or f"MCP tool {mcp_tool.name}",
                    args_schema=schema_model,
                    coroutine=invoke,
                )
            )
        return adapted


async def discover_tools(settings: Settings | None = None) -> list[Any]:
    """Convenience function to connect, discover tools, and close the client."""
    async with QueryMateMCPClient(settings) as client:
        return await client.discover_tools(refresh=True)


async def get_langchain_tools(client: QueryMateMCPClient) -> list[Any]:
    """Return LangChain tool adapters bound to an active MCP client session."""
    return await client.get_langchain_tools()


def main() -> None:
    """Print tools discovered from a locally launched MCP server."""
    async def _run() -> None:
        async with QueryMateMCPClient() as client:
            for tool in await client.discover_tools(refresh=True):
                print(f"{tool.name}: {tool.description}")

    try:
        asyncio.run(_run())
    except MCPClientError as exc:
        logger.error("MCP client failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
