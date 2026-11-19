"""Tests for document extraction, chunking, embeddings, and retrieval."""

from io import BytesIO

import pandas as pd
import pytest
from docx import Document as DocxDocument
from langchain_core.documents import Document

from rag.document_loader import DocumentLoadError, load_document
from rag.retriever import retrieve_documents
from rag.text_splitter import split_documents
from rag.vector_store import delete_document, ingest_document, list_documents


def _docx_bytes() -> bytes:
    doc = DocxDocument()
    doc.add_paragraph("Quarterly revenue was 42 million.")
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()


def test_load_txt_and_preserve_source_metadata() -> None:
    docs = load_document(BytesIO(b"Hello\x00 world"), filename="notes.txt")
    assert docs[0].page_content == "Hello world"
    assert docs[0].metadata["filename"] == "notes.txt"
    assert docs[0].metadata["source_type"] == "txt"
    assert docs[0].metadata["document_id"]


def test_load_docx_extracts_paragraphs() -> None:
    docs = load_document(_docx_bytes(), filename="report.docx")
    assert "Quarterly revenue" in docs[0].page_content


def test_load_csv_as_readable_rows() -> None:
    docs = load_document(b"name,value\nRevenue,42\n", filename="data.csv")
    assert "name | value" in docs[0].page_content
    assert "Revenue | 42" in docs[0].page_content


def test_load_xlsx_preserves_sheet_name() -> None:
    stream = BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        pd.DataFrame([["name", "value"], ["Revenue", 42]]).to_excel(writer, sheet_name="Summary", header=False, index=False)
    docs = load_document(stream.getvalue(), filename="data.xlsx")
    assert docs[0].metadata["sheet_name"] == "Summary"
    assert "Revenue | 42" in docs[0].page_content


def test_empty_and_unsupported_files_raise_clear_errors() -> None:
    with pytest.raises(DocumentLoadError, match="empty"):
        load_document(b"", filename="empty.txt")
    with pytest.raises(DocumentLoadError, match="Unsupported"):
        load_document(b"x", filename="archive.zip")


def test_chunking_preserves_metadata_and_start_index() -> None:
    source = Document(page_content=("Paragraph about revenue. " * 30), metadata={"filename": "a.txt"})
    chunks = split_documents([source], chunk_size=80, chunk_overlap=10)
    assert len(chunks) > 1
    assert all(chunk.metadata["filename"] == "a.txt" for chunk in chunks)
    assert all("start_index" in chunk.metadata for chunk in chunks)


def test_chunking_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        split_documents([Document(page_content="hello")], chunk_size=10, chunk_overlap=10)


def test_embedding_client_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    from llm import embeddings

    class FakeSettings:
        ollama_base_url = "http://localhost:11434"
        ollama_embedding_model = "nomic-embed-text"
        ollama_timeout_seconds = 5.0

    embeddings._build_embeddings.cache_clear()
    instance = object()
    monkeypatch.setattr(embeddings, "OllamaEmbeddings", lambda **kwargs: instance)
    assert embeddings.get_embeddings(FakeSettings()) is instance  # type: ignore[arg-type]
    assert embeddings.get_embeddings(FakeSettings()) is instance  # type: ignore[arg-type]
    assert embeddings._build_embeddings.cache_info().hits == 1
    embeddings._build_embeddings.cache_clear()


def test_ingest_retrieve_list_and_delete_use_local_store(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from rag import vector_store
    from agents import file_agent

    class FakeCollection:
        def __init__(self):
            self.docs: dict[str, tuple[str, dict]] = {}

        def upsert(self, ids, documents, metadatas):
            self.docs.update({item_id: (text, metadata) for item_id, text, metadata in zip(ids, documents, metadatas)})

        def get(self, where=None, include=None):
            values = [(key, value) for key, value in self.docs.items() if not where or value[1].get("document_id") == where["document_id"]]
            return {"ids": [key for key, _ in values], "metadatas": [value[1] for _, value in values]}

        def delete(self, ids):
            for item_id in ids:
                self.docs.pop(item_id, None)

    class FakeStore:
        def __init__(self):
            self._collection = FakeCollection()
            self.embedding_calls = 0
            self.stored_embeddings = []

        def add_documents(self, documents, ids):
            self.embedding_calls += 1
            self.stored_embeddings = [[float(len(item.page_content)), 1.0] for item in documents]
            self._collection.upsert(
                ids=ids,
                documents=[item.page_content for item in documents],
                metadatas=[item.metadata for item in documents],
            )

        def similarity_search_with_relevance_scores(self, question, k):
            return [(Document(page_content=text, metadata=metadata), 0.91) for text, metadata in list(self._collection.docs.values())[:k]]

    fake_store = FakeStore()
    monkeypatch.setattr(vector_store, "_get_store", lambda settings=None, **kwargs: fake_store)
    monkeypatch.setattr(file_agent, "ingest_document", lambda path, filename=None, settings=None: vector_store.ingest_document(path, filename=filename, settings=settings))
    monkeypatch.setattr("rag.retriever._get_store", lambda settings=None: fake_store)
    path = tmp_path / "report.txt"
    path.write_text("Annual revenue reached 42 million dollars.", encoding="utf-8")
    outcome = ingest_document(path)
    assert outcome["chunk_count"] >= 1
    assert fake_store.embedding_calls == 1
    assert fake_store.stored_embeddings
    matches = retrieve_documents("What was the revenue?")
    assert matches[0]["filename"] == "report.txt"
    assert matches[0]["score"] == 0.91
    records = list_documents()
    assert records[0]["filename"] == "report.txt"
    assert delete_document(str(outcome["document_id"])) >= 1
    assert list_documents() == []
