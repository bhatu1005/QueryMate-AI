"""Supervisor classification fallback tests for all supported intents."""

import pytest

from agents import supervisor_agent


@pytest.mark.parametrize(
    ("question", "has_files", "expected"),
    [
        ("show database rows", False, "SQL_QUERY"),
        ("what does the uploaded report say?", False, "DOCUMENT_QUERY"),
        ("summarize the uploaded report", True, "FILE_SUMMARY"),
        ("compare the database table with the uploaded document", False, "HYBRID_QUERY"),
        ("hello there", False, "GENERAL_QUERY"),
    ],
)
def test_supervisor_uses_safe_intent_fallback(monkeypatch, question, has_files, expected) -> None:
    monkeypatch.setattr(
        supervisor_agent,
        "get_chat_model",
        lambda settings: (_ for _ in ()).throw(ConnectionError("Ollama unavailable")),
    )
    intent, selected = supervisor_agent.classify_intent(question, has_files=has_files)
    assert intent == expected
    assert selected == {
        "SQL_QUERY": ["SQL"],
        "DOCUMENT_QUERY": ["RAG"],
        "FILE_SUMMARY": ["FILE"],
        "HYBRID_QUERY": ["SQL", "RAG"],
        "GENERAL_QUERY": [],
    }[expected]


def test_supervisor_overrides_inconsistent_valid_model_intent(monkeypatch) -> None:
    class Model:
        def invoke(self, prompt):
            return type("Response", (), {"content": '{"intent":"GENERAL_QUERY","agents":[]} '})()

    monkeypatch.setattr(supervisor_agent, "get_chat_model", lambda settings: Model())
    intent, selected = supervisor_agent.classify_intent(
        "According to quarterly_report.txt, what was the total revenue?"
    )
    assert intent == "DOCUMENT_QUERY"
    assert selected == ["RAG"]


def test_supervisor_recognizes_filename_reference_without_report_word(monkeypatch) -> None:
    class Model:
        def invoke(self, prompt):
            return type("Response", (), {"content": '{"intent":"GENERAL_QUERY"}'})()

    monkeypatch.setattr(supervisor_agent, "get_chat_model", lambda settings: Model())
    intent, _ = supervisor_agent.classify_intent("According to quarterly_report.txt, what was revenue?")
    assert intent == "DOCUMENT_QUERY"


def test_supervisor_routes_clear_hybrid_question_to_both_specialists(monkeypatch) -> None:
    class Model:
        def invoke(self, prompt):
            return type("Response", (), {"content": '{"intent":"DOCUMENT_QUERY","agents":["RAG"]}'})()

    monkeypatch.setattr(supervisor_agent, "get_chat_model", lambda settings: Model())
    intent, selected = supervisor_agent.classify_intent(
        "Compare the database salaries with the uploaded annual report."
    )
    assert intent == "HYBRID_QUERY"
    assert selected == ["SQL", "RAG"]
