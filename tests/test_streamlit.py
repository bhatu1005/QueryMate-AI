"""Headless Streamlit app tests for startup, chat, upload, and rendering."""

from contextlib import nullcontext
from types import SimpleNamespace

import app
import ui.components as ui_components
import pytest


class FakeStreamlit:
    """Small deterministic Streamlit facade for testing app flow without a server."""

    def __init__(self, question=None, uploads=None, clicked_buttons=None):
        self.session_state = SessionState()
        self.sidebar = nullcontext()
        self.question = question
        self.uploads = uploads or []
        self.clicked_buttons = clicked_buttons or set()
        self.rendered = []
        self.successes = []
        self.exceptions = []
        self.chat = nullcontext()
        self.status = lambda *args, **kwargs: nullcontext(SimpleNamespace(update=lambda **options: None))
        self.placeholder = SimpleNamespace(write=lambda *args, **kwargs: None, markdown=lambda *args, **kwargs: None, markown=lambda *args, **kwargs: None)

    def __getattr__(self, name):
        if name in {"title", "caption", "divider", "subheader", "markdown", "write", "dataframe", "plotly_chart", "code", "set_page_config", "empty", "rerun"}:
            if name == "empty":
                return lambda *args, **kwargs: self.placeholder
            return lambda *args, **kwargs: self.rendered.append((name, args, kwargs))
        if name == "button":
            return lambda label, **kwargs: (label, kwargs.get("key")) in self.clicked_buttons
        if name == "file_uploader":
            return lambda *args, **kwargs: self.uploads
        if name == "chat_input":
            return lambda *args, **kwargs: self.question
        if name == "chat_message":
            return lambda *args, **kwargs: self.chat
        if name == "spinner":
            return lambda *args, **kwargs: nullcontext()
        if name == "success":
            return lambda message, **kwargs: self.successes.append(message)
        if name == "error":
            return lambda message, **kwargs: self.exceptions.append(message)
        if name == "expander":
            return lambda *args, **kwargs: nullcontext()
        if name == "cache_data":
            return lambda *args, **kwargs: (lambda function: function)
        if name == "status":
            return self.status
        raise AttributeError(name)


class SessionState(dict):
    """Streamlit-like mapping with attribute access for session values."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _install_streamlit(monkeypatch, fake):
    monkeypatch.setattr(app, "st", fake)
    monkeypatch.setattr(ui_components, "st", fake)
    monkeypatch.setattr(app, "_database_status", lambda: (True, "Connected"))
    monkeypatch.setattr(app, "_model_status", lambda: (True, "Models ready"))
    monkeypatch.setattr(app, "_mcp_status", lambda: (True, "Ready (7 tools)"))
    documents = lambda: []
    documents.clear = lambda: None
    monkeypatch.setattr(app, "_indexed_documents", documents)


def test_app_startup_chat_history_and_result_rendering(monkeypatch) -> None:
    fake = FakeStreamlit(question="show a result")
    _install_streamlit(monkeypatch, fake)

    def fake_stream(question, conversation_history=None):
        supervisor = {"detected_intent": "GENERAL_QUERY", "selected_agents": [], "agent_outputs": {}}
        yield "supervisor", supervisor
        yield "response_agent", {
            **supervisor,
            "final_answer": {
                "answer": f"Local response to: {question}",
                "sql_query": "SELECT 1 AS total",
                "sql_validation_status": "valid_read_only_select",
                "table": {"columns": ["total"], "rows": [{"total": 1}], "row_count": 1},
                "sources": [{"filename": "report.pdf", "metadata": {"page_number": 2}, "score": 0.9}],
            },
            "error": None,
        }

    monkeypatch.setattr(app, "stream_querymate", fake_stream)
    app.main()
    conversation = fake.session_state["conversation"]
    assert [message["role"] for message in conversation] == ["assistant", "user", "assistant"]
    assert conversation[-1]["result"]["answer"] == "Local response to: show a result"
    assert fake.session_state["conversation"][0]["result"]["answer"] == app.WELCOME
    assert any(args and args[0] == "SELECT 1 AS total" for name, args, _ in fake.rendered if name == "code")
    assert any(args and "total" in str(args[0]) for name, args, _ in fake.rendered if name == "dataframe")


def test_app_uploads_multiple_files_and_records_status(monkeypatch) -> None:
    class Upload:
        def __init__(self, name, content):
            self.name = name
            self.content = content

        def getvalue(self):
            return self.content

    fake = FakeStreamlit(uploads=[Upload("first.txt", b"one"), Upload("second.csv", b"two")])
    _install_streamlit(monkeypatch, fake)
    processed = []

    def ingest(files):
        processed.extend(upload.name for upload in files)
        return [{"filename": upload.name, "status": "indexed", "summary": "Indexed", "chunk_count": 1} for upload in files]

    monkeypatch.setattr(app, "ingest_uploaded_files", ingest)
    app.main()
    assert processed == ["first.txt", "second.csv"]
    assert len(fake.session_state["upload_statuses"]) == 2
    assert "Indexed first.txt" in fake.successes


def test_sidebar_removes_document_from_persistent_index(monkeypatch) -> None:
    doc_id = "a" * 64
    fake = FakeStreamlit(clicked_buttons={("Remove", f"remove_document_{doc_id}")})
    _install_streamlit(monkeypatch, fake)
    documents = lambda: [{"document_id": doc_id, "filename": "quarterly_report.txt", "source_type": "txt", "chunk_count": 2}]
    documents.clear = lambda: None
    monkeypatch.setattr(app, "_indexed_documents", documents)
    removed = []
    monkeypatch.setattr(app, "remove_indexed_document", lambda document_id: removed.append(document_id) or 2)
    app.main()
    assert removed == [doc_id]
    assert any("Removed quarterly_report.txt" in message for message in fake.successes)


def test_remove_indexed_document_rejects_invalid_ids(monkeypatch) -> None:
    from services import file_service

    monkeypatch.setattr(file_service, "delete_document", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("invalid id must not delete")))
    with pytest.raises(ValueError, match="Invalid document identifier"):
        file_service.remove_indexed_document("../../private")


def test_chart_service_infers_numeric_csv_style_results() -> None:
    from services.chart_service import build_result_chart

    chart = build_result_chart({
        "columns": ["department", "revenue"],
        "rows": [{"department": "Sales", "revenue": "10.5"}, {"department": "Support", "revenue": "8.2"}],
    })
    assert chart is not None
    assert chart.data
