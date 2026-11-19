"""LangGraph StateGraph construction and public query execution entry point."""

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from config.settings import Settings, get_settings
from graph.nodes import build_nodes, route_by_intent
from graph.state import QueryMateState


def create_workflow(
    settings: Settings | None = None,
    *,
    nodes: dict[str, Callable[..., dict[str, Any]]] | None = None,
):
    """Compile the QueryMate graph with parallel hybrid specialist execution."""
    active = settings or get_settings()
    nodes = nodes or build_nodes(active)
    graph = StateGraph(QueryMateState)
    for name, node in nodes.items():
        graph.add_node(name, node)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_by_intent,
        {
            "sql_agent": "sql_agent",
            "rag_agent": "rag_agent",
            "file_agent": "file_agent",
            "response_agent": "response_agent",
            # HYBRID_QUERY returns both node names; LangGraph schedules both concurrently.
        },
    )
    graph.add_edge("sql_agent", "response_agent")
    graph.add_edge("rag_agent", "response_agent")
    graph.add_edge("file_agent", "response_agent")
    graph.add_edge("response_agent", END)
    return graph.compile()


def run_query(
    user_query: str,
    uploaded_files: list[Any] | None = None,
    conversation_history: list[Any] | None = None,
    settings: Settings | None = None,
    recursion_limit: int | None = None,
) -> QueryMateState:
    """Run one user turn with a bounded graph recursion limit."""
    active = settings or get_settings()
    graph = create_workflow(active)
    initial: QueryMateState = {
        "user_query": user_query,
        "uploaded_files": uploaded_files or [],
        "conversation_history": conversation_history or [],
        "agent_outputs": {},
        "retry_counts": {},
        "sources": [],
        "error": None,
    }
    result = graph.invoke(
        initial,
        config={"recursion_limit": recursion_limit or active.graph_recursion_limit},
    )
    return result


def run_query_stream(
    user_query: str,
    uploaded_files: list[Any] | None = None,
    conversation_history: list[Any] | None = None,
    settings: Settings | None = None,
    recursion_limit: int | None = None,
):
    """Yield ``(node_name, accumulated_state)`` for live UI activity display."""
    active = settings or get_settings()
    graph = create_workflow(active)
    state: dict[str, Any] = {
        "user_query": user_query,
        "uploaded_files": uploaded_files or [],
        "conversation_history": conversation_history or [],
        "agent_outputs": {},
        "retry_counts": {},
        "sources": [],
        "error": None,
    }
    for update in graph.stream(
        state,
        config={"recursion_limit": recursion_limit or active.graph_recursion_limit},
        stream_mode="updates",
    ):
        for node_name, node_update in update.items():
            for key, value in node_update.items():
                if key == "agent_outputs":
                    state[key] = {**state.get(key, {}), **value}
                else:
                    state[key] = value
            yield node_name, dict(state)
