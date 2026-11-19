"""Opt-in persistent Chroma/Ollama end-to-end RAG tests."""

import os

import pytest

from config.settings import Settings
from llm.ollama_client import require_ollama
from rag.retriever import retrieve_documents
from rag.vector_store import delete_document, ingest_document, list_documents
from agents.rag_agent import run_rag_agent


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("QUERYMATE_RUN_LOCAL_INTEGRATION") != "1", reason="set QUERYMATE_RUN_LOCAL_INTEGRATION=1")
def test_local_ollama_chroma_ingestion_retrieval_citations_and_low_relevance(tmp_path) -> None:
    settings = Settings(chroma_persist_dir=tmp_path / "chroma", chunk_size=220, chunk_overlap=20, retrieval_top_k=3)
    require_ollama(settings)
    file_path = tmp_path / "querymate_rag_fixture.txt"
    file_path.write_text(
        "The QueryMate fixture records that the amber telescope is stored in lab room 42. " * 8,
        encoding="utf-8",
    )
    indexed = ingest_document(file_path, settings=settings)
    assert indexed["chunk_count"] > 0
    assert any(doc["document_id"] == indexed["document_id"] for doc in list_documents(settings))
    matches = retrieve_documents("Where is the amber telescope?", settings=settings)
    assert matches and matches[0]["filename"] == file_path.name
    answer = run_rag_agent("Where is the amber telescope?", settings=settings)
    assert answer["sources"]
    assert file_path.name in answer["sources"][0]["filename"]
    unsupported = run_rag_agent("What is the recipe for moonstone soup?", settings=settings)
    if not unsupported["retrieved_documents"]:
        assert "couldn't find enough information" in unsupported["output"]
    delete_document(str(indexed["document_id"]), settings=settings)
