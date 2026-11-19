"""MCP handler and client tests plus an opt-in real stdio integration check."""

import os
import asyncio
from types import SimpleNamespace

import pytest

from config.settings import Settings
from mcp_client.client import MCPClientError, QueryMateMCPClient
from mcp_server import tools


def test_all_mcp_tool_handlers_return_structured_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "read_table_names", lambda: ["customers"])
    monkeypatch.setattr(tools, "read_database_schema", lambda: {"customers": [{"column_name": "id"}]})
    monkeypatch.setattr(tools, "describe_db_table", lambda name: [{"column_name": "id", "column_type": "int"}])
    monkeypatch.setattr(tools, "run_sql", lambda query: {"rows": [{"id": 1}], "row_count": 1})
    monkeypatch.setattr(tools, "retrieve_documents", lambda query, top_k: [{"filename": "a.txt", "content": "evidence"}])
    monkeypatch.setattr(tools, "list_documents", lambda: [{"document_id": "a" * 64, "filename": "a.txt"}])

    class Collection:
        def get(self, where, include):
            return {"documents": ["stored text"], "metadatas": [{"filename": "a.txt"}]}

    monkeypatch.setattr(tools, "_get_store", lambda **kwargs: SimpleNamespace(_collection=Collection()))
    assert tools.list_tables() == {"ok": True, "result": ["customers"]}
    assert tools.get_database_schema()["result"]["customers"]
    assert tools.describe_table("customers")["ok"] is True
    assert tools.execute_readonly_sql("SELECT 1")["result"]["row_count"] == 1
    assert tools.search_documents("evidence", 2)["result"][0]["filename"] == "a.txt"
    assert tools.list_uploaded_documents()["result"][0]["filename"] == "a.txt"
    assert tools.get_document_content("a" * 64)["result"][0]["content"] == "stored text"


@pytest.mark.parametrize(
    ("function", "args"),
    [
        (tools.describe_table, ("customers; DROP TABLE users",)),
        (tools.execute_readonly_sql, ("DELETE FROM customers",)),
        (tools.search_documents, ("hello", 0)),
        (tools.search_documents, ("hello", True)),
        (tools.get_document_content, ("../../private",)),
    ],
)
def test_mcp_handlers_reject_invalid_arguments(function, args) -> None:
    assert function(*args)["ok"] is False


def test_mcp_handler_safely_reports_tool_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "read_table_names", lambda: (_ for _ in ()).throw(ConnectionError("secret-password")))
    result = tools.list_tables()
    assert result["ok"] is False
    assert "secret-password" not in result["error"]


def test_client_discovers_invokes_and_adapts_mcp_tools() -> None:
    class Session:
        async def list_tools(self):
            return SimpleNamespace(tools=[
                SimpleNamespace(name="echo", description="Echo text", inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]})
            ])

        async def call_tool(self, name, arguments):
            return SimpleNamespace(isError=False, structuredContent={"ok": True, "result": arguments}, content=[])

    client = QueryMateMCPClient(Settings())
    client._session = Session()
    async def exercise() -> None:
        tools_found = await client.discover_tools(refresh=True)
        assert [item.name for item in tools_found] == ["echo"]
        assert await client.call_tool("echo", {"text": "hello"}) == {"ok": True, "result": {"text": "hello"}}
        adapted = await client.get_langchain_tools()
        assert adapted[0].name == "echo"
        result = await adapted[0].coroutine(text="through adapter")
        assert result["result"]["text"] == "through adapter"

    # Avoid asyncio's Proactor self-pipe, which stalls in this Windows test host.
    from types import coroutine

    @coroutine
    def run_sync(awaitable):
        try:
            awaitable.send(None)
        except StopIteration as result:
            return result.value
        raise AssertionError("Fake MCP session unexpectedly yielded control")

    run_sync(exercise())


def test_client_reports_unknown_tool_and_mcp_errors() -> None:
    class Session:
        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name="boom")])

        async def call_tool(self, name, arguments):
            return SimpleNamespace(isError=True, structuredContent=None, content=[SimpleNamespace(text="failed")])

    client = QueryMateMCPClient(Settings())
    client._session = Session()
    async def exercise() -> None:
        with pytest.raises(MCPClientError, match="Unknown MCP tool"):
            await client.call_tool("missing")
        with pytest.raises(MCPClientError, match="returned an error"):
            await client.call_tool("boom")

    from types import coroutine

    @coroutine
    def run_sync(awaitable):
        try:
            awaitable.send(None)
        except StopIteration as result:
            return result.value
        raise AssertionError("Fake MCP session unexpectedly yielded control")

    run_sync(exercise())


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("QUERYMATE_RUN_INTEGRATION") != "1"
    or not os.getenv("QUERYMATE_TEST_MYSQL_DATABASE")
    or os.getenv("QUERYMATE_RUN_LOCAL_INTEGRATION") != "1",
    reason="requires explicit integration opt-in, dedicated test DB, and running Ollama",
)
def test_real_mcp_stdio_startup_discovery_and_all_tool_invocations() -> None:
    test_database = os.environ["QUERYMATE_TEST_MYSQL_DATABASE"]
    if not test_database.startswith("querymate_test"):
        pytest.fail("Refusing MCP integration unless database starts with querymate_test")
    settings = Settings(mysql_database=test_database)

    async def exercise() -> None:
        async with QueryMateMCPClient(settings) as client:
            discovered = await client.discover_tools(refresh=True)
            names = {tool.name for tool in discovered}
            assert names == {
                "list_tables", "get_database_schema", "describe_table", "execute_readonly_sql",
                "search_documents", "list_uploaded_documents", "get_document_content",
            }
            tables = await client.call_tool("list_tables")
            assert tables["ok"] is True
            schema = await client.call_tool("get_database_schema")
            assert schema["ok"] is True
            if tables["result"]:
                described = await client.call_tool("describe_table", {"table_name": tables["result"][0]})
                assert described["ok"] is True
            selected = await client.call_tool("execute_readonly_sql", {"query": "SELECT 1 AS mcp_smoke"})
            assert selected["ok"] is True
            assert (await client.call_tool("search_documents", {"query": "integration check", "top_k": 1}))["ok"] is True
            documents = await client.call_tool("list_uploaded_documents")
            assert documents["ok"] is True
            document_id = documents["result"][0]["document_id"] if documents["result"] else "a" * 64
            content = await client.call_tool("get_document_content", {"document_id": document_id})
            assert content["ok"] is True

    asyncio.run(exercise())
