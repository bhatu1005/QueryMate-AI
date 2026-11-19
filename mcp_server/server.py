"""Local stdio MCP server exposing safe database and document tools."""

import logging

from mcp.server.fastmcp import FastMCP

from config.logging_config import configure_logging
from config.settings import get_settings
from mcp_server import tools

configure_logging(get_settings().log_level)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "QueryMate AI",
    instructions="Local read-only database and indexed-document tools for QueryMate AI.",
)


@mcp.tool()
def list_tables() -> dict:
    """List table names in the configured MySQL database."""
    return tools.list_tables()


@mcp.tool()
def get_database_schema() -> dict:
    """Return the configured database tables, columns, types, and constraints."""
    return tools.get_database_schema()


@mcp.tool()
def describe_table(table_name: str) -> dict:
    """Describe one table. table_name must be a simple SQL identifier."""
    return tools.describe_table(table_name)


@mcp.tool()
def execute_readonly_sql(query: str) -> dict:
    """Validate and execute exactly one read-only SELECT query; mutations are rejected."""
    return tools.execute_readonly_sql(query)


@mcp.tool()
def search_documents(query: str, top_k: int = 5) -> dict:
    """Find semantically relevant uploaded-document chunks and return citations."""
    return tools.search_documents(query, top_k)


@mcp.tool()
def list_uploaded_documents() -> dict:
    """List indexed documents by safe identifier, filename, type, and chunk count."""
    return tools.list_uploaded_documents()


@mcp.tool()
def get_document_content(document_id: str) -> dict:
    """Get indexed chunks by their 64-character content-derived document identifier."""
    return tools.get_document_content(document_id)


def main() -> None:
    """Run the server over MCP stdio for a local subprocess client."""
    logger.info("Starting QueryMate MCP server over stdio")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
