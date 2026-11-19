"""Model-free tests for intent routing and graph branch coordination."""

from graph.nodes import route_by_intent
from graph.workflow import create_workflow, run_query_stream


def test_routes_all_supported_intents() -> None:
    assert route_by_intent({"detected_intent": "SQL_QUERY"}) == "sql_agent"
    assert route_by_intent({"detected_intent": "DOCUMENT_QUERY"}) == "rag_agent"
    assert route_by_intent({"detected_intent": "FILE_SUMMARY"}) == "file_agent"
    assert route_by_intent({"detected_intent": "HYBRID_QUERY"}) == ["sql_agent", "rag_agent"]
    assert route_by_intent({"detected_intent": "GENERAL_QUERY"}) == "response_agent"


def test_hybrid_runs_both_specialists_before_response() -> None:
    observed: dict[str, object] = {}

    def classify_fn(question, has_files=False, settings=None):
        return "HYBRID_QUERY", ["SQL", "RAG"]

    def sql_fn(question, settings=None):
        return {"agent": "SQL", "status": "ok", "generated_sql": "SELECT 1", "sql_result": {"rows": [1]}}

    def rag_fn(question, settings=None):
        return {"agent": "RAG", "status": "ok", "retrieved_documents": [{"content": "evidence"}], "sources": []}

    def response_fn(question, intent, agent_outputs, **kwargs):
        observed["agents"] = set(agent_outputs)
        observed["intent"] = intent
        return {"answer": "combined", "sources": []}

    nodes = __import__("graph.nodes", fromlist=["build_nodes"]).build_nodes(
        classify_fn=classify_fn, sql_fn=sql_fn, rag_fn=rag_fn, response_fn=response_fn
    )
    result = create_workflow(nodes=nodes).invoke({"user_query": "combine both"})
    assert observed["agents"] == {"SQL", "RAG"}
    assert observed["intent"] == "HYBRID_QUERY"
    assert result["final_answer"]["answer"] == "combined"


def test_general_query_terminates_without_specialist_agents() -> None:
    def classify_fn(question, has_files=False, settings=None):
        return "GENERAL_QUERY", []

    def response_fn(question, intent, agent_outputs, **kwargs):
        assert agent_outputs == {}
        return {"answer": "general response"}

    nodes = __import__("graph.nodes", fromlist=["build_nodes"]).build_nodes(
        classify_fn=classify_fn,
        response_fn=response_fn,
    )
    result = create_workflow(nodes=nodes).invoke({"user_query": "hello"}, config={"recursion_limit": 5})
    assert result["final_answer"]["answer"] == "general response"


def test_graph_stream_emits_updates_for_streamlit_activity(monkeypatch) -> None:
    from graph import workflow

    def classify_fn(question, has_files=False, settings=None):
        return "GENERAL_QUERY", []

    def response_fn(question, intent, agent_outputs, **kwargs):
        return {"answer": "streamed response", "sources": []}

    from graph.nodes import build_nodes

    injected = build_nodes(classify_fn=classify_fn, response_fn=response_fn)
    monkeypatch.setattr(workflow, "create_workflow", lambda settings=None: create_workflow(nodes=injected))
    events = list(run_query_stream("hello", conversation_history=[{"role": "user", "content": "prior"}]))
    assert [name for name, _ in events] == ["supervisor", "response_agent"]
    assert events[-1][1]["final_answer"]["answer"] == "streamed response"


def test_previous_document_context_does_not_hybridize_database_question() -> None:
    observed = {}

    def classify_fn(question, has_files=False, settings=None):
        observed["classified_question"] = question
        from agents.supervisor_agent import _intent_from_explicit_cues
        intent = _intent_from_explicit_cues(question, has_files) or "GENERAL_QUERY"
        return intent, {"SQL_QUERY": ["SQL"], "DOCUMENT_QUERY": ["RAG"], "HYBRID_QUERY": ["SQL", "RAG"], "GENERAL_QUERY": []}.get(intent, [])

    def sql_fn(question, settings=None):
        return {"agent": "SQL", "status": "ok", "generated_sql": "SELECT 1", "sql_result": {"rows": []}}

    def rag_fn(question, settings=None):
        raise AssertionError("RAG should not run for a database-only current turn")

    from graph.nodes import build_nodes
    nodes = build_nodes(classify_fn=classify_fn, sql_fn=sql_fn, rag_fn=rag_fn)
    result = create_workflow(nodes=nodes).invoke({
        "user_query": "List employees and their departments.",
        "conversation_history": [
            {"role": "user", "content": "What was the sample report's revenue?"},
            {"role": "assistant", "content": "The report says revenue was 125,000."},
        ],
    })
    assert observed["classified_question"] == "List employees and their departments."
    assert result["detected_intent"] == "SQL_QUERY"
    assert set(result["agent_outputs"]) == {"SQL"}
