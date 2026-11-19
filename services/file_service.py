"""Application service for validating and ingesting Streamlit uploads."""

import logging
from pathlib import Path
from typing import Any, Sequence

from config.settings import Settings, get_settings
from rag.document_loader import SUPPORTED_SUFFIXES
from agents.file_agent import process_uploaded_files
from rag.vector_store import delete_document

logger = logging.getLogger(__name__)


def remove_indexed_document(document_id: str, settings: Settings | None = None) -> int:
    """Remove a document and all its chunks from persistent Chroma storage."""
    if not isinstance(document_id, str) or len(document_id) != 64 or any(char not in "0123456789abcdef" for char in document_id):
        raise ValueError("Invalid document identifier.")
    return delete_document(document_id, settings=settings)


def ingest_uploaded_files(
    files: Sequence[Any], settings: Settings | None = None
) -> list[dict[str, Any]]:
    """Validate upload names and size before delegating processing to File Agent."""
    active = settings or get_settings()
    accepted: list[Any] = []
    results: list[dict[str, Any]] = []
    max_bytes = active.max_upload_size_mb * 1024 * 1024
    for uploaded in files:
        filename = str(getattr(uploaded, "name", "uploaded file"))
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            results.append({"filename": filename, "status": "error", "error": "Unsupported file type."})
            continue
        try:
            raw = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded.read()
            if len(raw) > max_bytes:
                results.append({"filename": filename, "status": "error", "error": f"File exceeds {active.max_upload_size_mb} MB limit."})
                continue
            # Ingestion accepts bytes; preserve the original name for type detection/citations.
            accepted.append(_NamedBytes(raw, filename))
        except Exception:
            logger.exception("Could not read uploaded file %s", filename)
            results.append({"filename": filename, "status": "error", "error": "Could not read uploaded file."})
    for uploaded in accepted:
        outcome = process_uploaded_files([uploaded], settings=active)
        if outcome.get("status") == "error":
            results.append({"filename": uploaded.name, "status": "error", "error": "File could not be extracted or indexed. Check local service logs."})
        else:
            document = (outcome.get("uploaded_documents") or [{}])[0]
            results.append({**document, "status": "indexed", "summary": outcome.get("file_summary", "")})
    return results


class _NamedBytes:
    """Tiny in-memory upload adapter understood by the document loader."""

    def __init__(self, data: bytes, name: str) -> None:
        self._data = data
        self.name = name

    def read(self) -> bytes:
        return self._data
