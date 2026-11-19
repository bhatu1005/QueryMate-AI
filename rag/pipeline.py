"""Public operations for document ingestion, retrieval, and deletion."""

from rag.retriever import retrieve_documents
from rag.vector_store import delete_document, ingest_document, ingest_multiple_documents, list_documents

__all__ = ["ingest_document", "ingest_multiple_documents", "retrieve_documents", "delete_document", "list_documents"]
