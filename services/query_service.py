"""Application service facade for QueryMate graph execution."""

from typing import Any, Iterator

from config.settings import Settings
from graph.workflow import run_query, run_query_stream


def ask_querymate(
    question: str,
    uploaded_files: list[Any] | None = None,
    conversation_history: list[Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run a complete user turn through LangGraph."""
    return run_query(question, uploaded_files, conversation_history, settings=settings)


def stream_querymate(
    question: str,
    uploaded_files: list[Any] | None = None,
    conversation_history: list[Any] | None = None,
    settings: Settings | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield graph node updates for frontend progress indicators."""
    return run_query_stream(question, uploaded_files, conversation_history, settings=settings)
