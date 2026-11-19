"""LangGraph node functions and bounded specialist retry handling."""

import logging
from typing import Any, Callable

from agents.file_agent import process_uploaded_files
from agents.rag_agent import run_rag_agent
from agents.response_agent import compose_response
from agents.sql_agent import run_sql_agent
from agents.supervisor_agent import classify_intent
from config.settings import Settings, get_settings
from graph.state import QueryMateState

logger = logging.getLogger(__name__)


def _run_with_retry(agent_name: str, operation: Callable[[], dict[str, Any]], retries: int) -> dict[str, Any]:
    """Retry bounded, idempotent specialist work and preserve final errors."""
    last: dict[str, Any] = {}
    for attempt in range(retries + 1):
        try:
            last = operation()
            if last.get("status") != "error":
                return last
            logger.warning("%s agent attempt %d failed: %s", agent_name, attempt + 1, last.get("error"))
        except Exception as exc:
            last = {"agent": agent_name, "status": "error", "error": str(exc)}
            logger.exception("%s agent attempt %d raised", agent_name, attempt + 1)
    return last


def build_nodes(
    settings: Settings | None = None,
    *,
    classify_fn: Callable[..., Any] = classify_intent,
    sql_fn: Callable[..., dict[str, Any]] = run_sql_agent,
    rag_fn: Callable[..., dict[str, Any]] = run_rag_agent,
    file_fn: Callable[..., dict[str, Any]] = process_uploaded_files,
    response_fn: Callable[..., dict[str, Any]] = compose_response,
) -> dict[str, Callable[[QueryMateState], dict[str, Any]]]:
    """Build dependency-injected graph nodes for a testable workflow."""
    active = settings or get_settings()

    def contextual_query(state: QueryMateState) -> str:
        """Include a bounded window of prior turns for context-dependent questions."""
        history = state.get("conversation_history", [])[-4:]
        context = [
            f"{message.get('role', 'context') if isinstance(message, dict) else getattr(message, 'type', getattr(message, 'role', 'context'))}: "
            f"{message.get('content', '') if isinstance(message, dict) else getattr(message, 'content', str(message))}"
            for message in history
        ]
        current = state.get("user_query", "")
        context_text = "\n".join(context)
        return f"Prior conversation:\n{context_text}\nCurrent question: {current}" if context else current

    def supervisor_node(state: QueryMateState) -> dict[str, Any]:
        # Route using only the current turn. Prior turns remain available to
        # specialist prompts, but must not make a database-only question look
        # hybrid just because an earlier turn mentioned an uploaded document.
        classification_query = state.get("user_query", "")
        intent, selected = classify_fn(
            classification_query,
            has_files=bool(state.get("uploaded_files")),
            settings=active,
        )
        return {"detected_intent": intent, "selected_agents": selected}

    def sql_node(state: QueryMateState) -> dict[str, Any]:
        result = _run_with_retry(
            "SQL",
            lambda: sql_fn(contextual_query(state), settings=active),
            active.agent_max_retries,
        )
        return {
            "database_schema": result.get("database_schema", {}),
            "generated_sql": result.get("generated_sql", ""),
            "sql_validation_status": result.get("sql_validation_status", "not_run"),
            "sql_result": result.get("sql_result", {}),
            "agent_outputs": {"SQL": result},
        }

    def rag_node(state: QueryMateState) -> dict[str, Any]:
        result = _run_with_retry(
            "RAG",
            lambda: rag_fn(contextual_query(state), settings=active),
            active.agent_max_retries,
        )
        return {
            "retrieved_documents": result.get("retrieved_documents", []),
            "agent_outputs": {"RAG": result},
        }

    def file_node(state: QueryMateState) -> dict[str, Any]:
        files = state.get("uploaded_files", [])
        result = _run_with_retry(
            "FILE",
            lambda: file_fn(files, state.get("user_query", "Summarize these files."), settings=active),
            active.agent_max_retries,
        )
        return {
            "file_summary": result.get("file_summary", ""),
            "agent_outputs": {"FILE": result},
        }

    def response_node(state: QueryMateState) -> dict[str, Any]:
        outputs = state.get("agent_outputs", {})
        final = response_fn(
            question=state.get("user_query", ""),
            intent=state.get("detected_intent", "GENERAL_QUERY"),
            agent_outputs=outputs,
            conversation_history=state.get("conversation_history", []),
            settings=active,
        )
        errors = [
            f"{name}: {item.get('error')}"
            for name, item in outputs.items()
            if item.get("status") == "error" and item.get("error")
        ]
        return {"final_answer": final, "sources": final.get("sources", []), "error": "; ".join(errors) or None}

    return {
        "supervisor": supervisor_node,
        "sql_agent": sql_node,
        "rag_agent": rag_node,
        "file_agent": file_node,
        "response_agent": response_node,
    }


def route_by_intent(state: QueryMateState) -> str | list[str]:
    """Route to specialist nodes; hybrid returns parallel SQL and RAG branches."""
    intent = state.get("detected_intent", "GENERAL_QUERY")
    routes: dict[str, str | list[str]] = {
        "SQL_QUERY": "sql_agent",
        "DOCUMENT_QUERY": "rag_agent",
        "FILE_SUMMARY": "file_agent",
        "HYBRID_QUERY": ["sql_agent", "rag_agent"],
        "GENERAL_QUERY": "response_agent",
    }
    return routes.get(intent, "response_agent")
