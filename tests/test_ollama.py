"""Unit and opt-in local integration tests for Ollama clients."""

import os

import httpx
import pytest

from config.settings import Settings
from llm import embeddings, ollama_client
from llm.ollama_client import OllamaConnectionError


def test_health_check_reports_models_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "llama3.2:1b"}, {"name": "nomic-embed-text:latest"}]}

    class Client:
        def __init__(self, timeout):
            assert timeout == 7

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url):
            assert url.endswith("/api/tags")
            return Response()

    monkeypatch.setattr(ollama_client.httpx, "Client", Client)
    report = ollama_client.check_ollama_health(Settings(ollama_timeout_seconds=7))
    assert report["server_connected"] is True
    assert report["chat_model_available"] is True
    assert report["embedding_model_available"] is True


def test_health_check_connection_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_client(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(ollama_client.httpx, "Client", fail_client)
    report = ollama_client.check_ollama_health(Settings())
    assert report["server_connected"] is False
    assert "Cannot check Ollama" in report["error"]
    with pytest.raises(OllamaConnectionError):
        ollama_client.require_ollama(Settings())


def test_chat_and_embedding_clients_are_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_client._build_chat_model.cache_clear()
    embeddings._build_embeddings.cache_clear()
    chat = object()
    embedder = object()
    monkeypatch.setattr(ollama_client, "ChatOllama", lambda **kwargs: chat)
    monkeypatch.setattr(embeddings, "OllamaEmbeddings", lambda **kwargs: embedder)
    settings = Settings()
    assert ollama_client.get_chat_model(settings) is chat
    assert ollama_client.get_chat_model(settings) is chat
    assert embeddings.get_embeddings(settings) is embedder
    assert embeddings.get_embeddings(settings) is embedder
    assert ollama_client._build_chat_model.cache_info().hits == 1
    assert embeddings._build_embeddings.cache_info().hits == 1
    ollama_client._build_chat_model.cache_clear()
    embeddings._build_embeddings.cache_clear()


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("QUERYMATE_RUN_LOCAL_INTEGRATION") != "1", reason="set QUERYMATE_RUN_LOCAL_INTEGRATION=1")
def test_local_ollama_chat_and_embedding() -> None:
    settings = Settings()
    ollama_client.require_ollama(settings)
    answer = ollama_client.get_chat_model(settings).invoke("Reply with the word ready.")
    vector = embeddings.get_embeddings(settings).embed_query("QueryMate embedding integration test")
    assert str(answer.content).strip()
    assert len(vector) > 0
