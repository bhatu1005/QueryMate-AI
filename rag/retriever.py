"""Semantic retrieval over the persistent QueryMate Chroma collection."""

from typing import Any

from config.settings import Settings, get_settings
from rag.vector_store import _get_store


def retrieve_documents(
    question: str,
    top_k: int | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Return relevant text chunks with filenames, metadata, and similarity scores."""
    if not question.strip():
        return []
    active = settings or get_settings()
    count = top_k if top_k is not None else active.retrieval_top_k
    if count < 1:
        raise ValueError("top_k must be at least 1.")
    results = _get_store(active).similarity_search_with_relevance_scores(question, k=count)
    return [
        {
            "content": doc.page_content,
            "filename": doc.metadata.get("filename", "unknown"),
            "metadata": doc.metadata,
            "score": score,
        }
        for doc, score in results
        if score >= active.retrieval_min_relevance_score
    ]
