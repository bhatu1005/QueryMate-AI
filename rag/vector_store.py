"""Persistent Chroma vector storage with idempotent document ingestion."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document

from config.settings import Settings, get_settings
from llm.embeddings import get_embeddings
from rag.document_loader import load_document
from rag.text_splitter import split_documents

logger = logging.getLogger(__name__)
COLLECTION_NAME = "querymate_documents"


def _get_store(settings: Settings | None = None, *, with_embeddings: bool = True) -> Chroma:
    """Create a Chroma handle for the configured persistent local collection."""
    active = settings or get_settings()
    path = Path(active.chroma_persist_dir)
    path.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(path),
        embedding_function=get_embeddings(active) if with_embeddings else None,
    )


def _chunk_ids(chunks: Sequence[Document]) -> list[str]:
    """Create deterministic IDs from source identity, location, and chunk text."""
    ids = []
    for index, chunk in enumerate(chunks):
        document_id = str(chunk.metadata.get("document_id", "unknown"))
        location = str(chunk.metadata.get("page_number", chunk.metadata.get("sheet_name", "")))
        start = str(chunk.metadata.get("start_index", index))
        digest = hashlib.sha256(chunk.page_content.encode("utf-8")).hexdigest()
        ids.append(f"{document_id}:{location}:{start}:{digest[:16]}")
    return ids


def ingest_documents(chunks: Sequence[Document], settings: Settings | None = None) -> int:
    """Upsert chunks into persistent Chroma and return the number stored."""
    if not chunks:
        return 0
    store = _get_store(settings)
    ids = _chunk_ids(chunks)
    # Chroma's LangChain API computes vectors with the configured Ollama embeddings.
    # Raw collection.upsert(documents=...) would skip that integration boundary.
    normalized = [
        Document(
            page_content=chunk.page_content,
            metadata={key: value for key, value in chunk.metadata.items() if value is not None},
        )
        for chunk in chunks
    ]
    store.add_documents(normalized, ids=ids)
    logger.info("Upserted %d chunks from %s", len(chunks), chunks[0].metadata.get("filename"))
    return len(chunks)


def delete_document(document_id: str, settings: Settings | None = None) -> int:
    """Delete all chunks matching a content-derived document ID."""
    store = _get_store(settings, with_embeddings=False)
    existing = store._collection.get(where={"document_id": document_id}, include=[])
    ids = existing.get("ids", [])
    if ids:
        store._collection.delete(ids=ids)
    return len(ids)


def list_documents(settings: Settings | None = None) -> list[dict[str, str | int]]:
    """List unique indexed documents and their chunk counts."""
    store = _get_store(settings, with_embeddings=False)
    records = store._collection.get(include=["metadatas"])
    grouped: dict[str, dict[str, str | int]] = {}
    for metadata in records.get("metadatas", []) or []:
        if not metadata:
            continue
        doc_id = str(metadata.get("document_id", ""))
        if not doc_id:
            continue
        if doc_id not in grouped:
            grouped[doc_id] = {
                "document_id": doc_id,
                "filename": str(metadata.get("filename", "unknown")),
                "source_type": str(metadata.get("source_type", "unknown")),
                "chunk_count": 0,
            }
        grouped[doc_id]["chunk_count"] = int(grouped[doc_id]["chunk_count"]) + 1
    return sorted(grouped.values(), key=lambda item: str(item["filename"]).lower())


def ingest_document(
    source: str | Path | object,
    filename: str | None = None,
    settings: Settings | None = None,
) -> dict[str, str | int]:
    """Extract, split, and idempotently store one document."""
    documents = load_document(source, filename=filename)  # type: ignore[arg-type]
    chunks = split_documents(documents, settings=settings)
    document_id = str(documents[0].metadata["document_id"])
    # A replaced file can produce fewer chunks; remove stale chunk IDs before upsert.
    delete_document(document_id, settings=settings)
    count = ingest_documents(chunks, settings=settings)
    first = documents[0].metadata
    return {"document_id": str(first["document_id"]), "filename": str(first["filename"]), "chunk_count": count}


def ingest_multiple_documents(
    sources: Sequence[str | Path | object], settings: Settings | None = None
) -> list[dict[str, str | int]]:
    """Ingest multiple paths or uploaded file objects, reporting per-file errors."""
    outcomes: list[dict[str, str | int]] = []
    for source in sources:
        filename = getattr(source, "name", None)
        try:
            outcomes.append(ingest_document(source, filename=filename, settings=settings))
        except Exception as exc:
            outcomes.append({"filename": str(filename or source), "error": str(exc)})
    return outcomes
