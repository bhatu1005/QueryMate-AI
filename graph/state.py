"""Typed shared state for the QueryMate LangGraph workflow."""

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

Intent = Literal["SQL_QUERY", "DOCUMENT_QUERY", "FILE_SUMMARY", "HYBRID_QUERY", "GENERAL_QUERY"]


class QueryMateState(TypedDict, total=False):
    """Data carried between supervisor, specialist, and response graph nodes."""

    user_query: str
    uploaded_files: list[Any]
    conversation_history: list[BaseMessage]
    detected_intent: Intent
    selected_agents: list[str]
    database_schema: dict[str, Any]
    generated_sql: str
    sql_validation_status: str
    sql_result: dict[str, Any]
    retrieved_documents: list[dict[str, Any]]
    file_summary: str
    agent_outputs: Annotated[dict[str, Any], operator.or_]
    final_answer: dict[str, Any]
    sources: list[dict[str, Any]]
    error: str | None
    retry_counts: dict[str, int]
