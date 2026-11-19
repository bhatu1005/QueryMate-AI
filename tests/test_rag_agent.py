"""Grounding and citation behavior tests for the RAG specialist."""

from types import SimpleNamespace

from agents import rag_agent
from agents import response_agent


def test_rag_answer_includes_retrieved_source_references(monkeypatch) -> None:
    retrieved = [{
        "content": "Revenue was 42 million dollars.",
        "filename": "annual.pdf",
        "metadata": {"filename": "annual.pdf", "page_number": 3},
        "score": 0.93,
    }]
    monkeypatch.setattr(rag_agent, "retrieve_documents", lambda *args, **kwargs: retrieved)

    class Model:
        def invoke(self, messages):
            assert "[Source 1: annual.pdf (3)]" in str(messages)
            return SimpleNamespace(content="Revenue was 42 million dollars [Source 1].")

    monkeypatch.setattr(rag_agent, "get_chat_model", lambda settings: Model())
    output = rag_agent.run_rag_agent("What was the revenue?")
    assert output["status"] == "ok"
    assert "42 million" in output["output"]
    assert output["sources"][0]["filename"] == "annual.pdf"


def test_unsupported_question_does_not_call_llm(monkeypatch) -> None:
    monkeypatch.setattr(rag_agent, "retrieve_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(rag_agent, "get_chat_model", lambda settings: (_ for _ in ()).throw(AssertionError("must not hallucinate")))
    output = rag_agent.run_rag_agent("What is the secret value?")
    assert output["status"] == "ok"
    assert output["sources"] == []
    assert "couldn't find enough information" in output["output"]


def test_low_relevance_matches_do_not_reach_llm(monkeypatch) -> None:
    monkeypatch.setattr(rag_agent, "retrieve_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(rag_agent, "get_chat_model", lambda settings: (_ for _ in ()).throw(AssertionError("low relevance must not be answered")))
    output = rag_agent.run_rag_agent("unrelated unsupported question")
    assert "couldn't find enough information" in output["output"]


def test_rag_preserves_retrieved_evidence_when_chat_model_is_unavailable(monkeypatch) -> None:
    retrieved = [{"content": "fact", "filename": "f.txt", "metadata": {}, "score": 0.8}]
    monkeypatch.setattr(rag_agent, "retrieve_documents", lambda *args, **kwargs: retrieved)
    monkeypatch.setattr(rag_agent, "get_chat_model", lambda settings: (_ for _ in ()).throw(ConnectionError("offline")))
    output = rag_agent.run_rag_agent("find fact")
    assert output["status"] == "partial"
    assert output["retrieved_documents"] == retrieved
    assert output["sources"][0]["filename"] == "f.txt"


def test_response_agent_uses_rag_answer_and_safe_fallback_without_sources(monkeypatch) -> None:
    monkeypatch.setattr(response_agent, "get_chat_model", lambda settings: (_ for _ in ()).throw(ConnectionError("offline")))
    answer = response_agent.compose_response(
        question="What was revenue?",
        intent="DOCUMENT_QUERY",
        agent_outputs={"RAG": {
            "status": "ok",
            "output": "Revenue was 42 million dollars [Source 1].",
            "retrieved_documents": [{"filename": "annual.pdf", "content": "Revenue was 42 million.", "metadata": {}, "score": 0.9}],
            "sources": [{"filename": "annual.pdf"}],
        }},
    )
    assert "42 million" in answer["answer"]
    unsupported = response_agent.compose_response(
        question="What is the secret?", intent="DOCUMENT_QUERY", agent_outputs={}
    )
    assert "couldn't find enough information" in unsupported["answer"]
