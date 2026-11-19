"""File specialist for safe ingestion, extraction, and bounded summarization."""

import io
import logging
from pathlib import Path
from typing import Any, Sequence

from config.settings import Settings, get_settings
from llm.ollama_client import get_chat_model
from rag.document_loader import load_document
from rag.retriever import retrieve_documents
from rag.vector_store import list_documents
from rag.vector_store import ingest_document

logger = logging.getLogger(__name__)


def _materialize(source: Any) -> tuple[Any, str]:
    """Rewind/retain uploaded stream data so extraction and indexing both can read it."""
    name = Path(getattr(source, "name", str(source))).name
    if isinstance(source, (str, Path)):
        return source, Path(source).name
    if hasattr(source, "getvalue"):
        raw = source.getvalue()
    elif hasattr(source, "read"):
        if hasattr(source, "seek"):
            source.seek(0)
        raw = source.read()
    else:
        raw = source
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return io.BytesIO(raw), name


def process_uploaded_files(
    files: Sequence[Any],
    question: str = "Summarize the uploaded document.",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Extract and index files, then summarize extracted content with local Llama."""
    active = settings or get_settings()
    all_content: list[str] = []
    processed: list[dict[str, Any]] = []
    errors: list[str] = []
    if not files:
        try:
            indexed = list_documents(active)
            matches = retrieve_documents(
                question or "Summarize the uploaded documents.",
                top_k=max(active.retrieval_top_k, len(indexed)),
                settings=active,
            )
            for match in matches:
                filename = str(match.get("filename", "document"))
                all_content.append(f"Source: {filename}\n{match['content']}")
                processed.append({"filename": filename, "metadata": match.get("metadata", {})})
        except Exception:
            logger.exception("Could not retrieve indexed documents for a file summary")
    for source in files:
        try:
            readable, filename = _materialize(source)
            documents = load_document(readable, filename=filename)
            # Ingest from the extracted bytes/doc content while preserving filename.
            if isinstance(readable, io.BytesIO):
                ingest_result = ingest_document(readable.getvalue(), filename=filename, settings=active)
            else:
                ingest_result = ingest_document(readable, filename=filename, settings=active)
            for document in documents:
                all_content.append(f"Source: {filename}\n{document.page_content}")
            processed.append({
                "filename": filename,
                "document_id": ingest_result["document_id"],
                "chunk_count": ingest_result["chunk_count"],
                "source_type": documents[0].metadata["source_type"],
                "metadata": [document.metadata for document in documents],
            })
        except Exception as exc:
            logger.exception("File specialist failed to process an upload")
            errors.append(f"{Path(getattr(source, 'name', 'uploaded file')).name}: document processing failed")
    if not all_content:
        return {
            "agent": "FILE", "status": "error", "file_summary": "No uploaded file could be processed.",
            "uploaded_documents": processed, "error": "; ".join(errors) or "No files provided.",
        }
    context = "\n\n".join(all_content)[:16000]
    try:
        summary = str(get_chat_model(active).invoke(
            "Summarize the following extracted document content. Use only these facts. "
            "Mention important names, dates, and figures when present. If it is too long, "
            "focus on the main points.\n\n"
            f"User request: {question}\n\nExtracted content:\n{context}"
        ).content).strip()
    except Exception as exc:
        logger.exception("File summary generation failed")
        # Extraction remains useful even if the local chat model is unavailable.
        summary = context[:1500]
        errors.append(f"Summary model unavailable: {exc}")
    return {
        "agent": "FILE", "status": "ok", "file_summary": summary,
        "uploaded_documents": processed,
        "error": "; ".join(errors) if errors else None,
        "output": summary,
    }
