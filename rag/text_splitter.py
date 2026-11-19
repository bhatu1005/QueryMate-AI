"""Metadata-preserving LangChain text chunking."""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import Settings, get_settings


def split_documents(
    documents: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    settings: Settings | None = None,
) -> list[Document]:
    """Split extracted documents into chunks while copying source metadata."""
    active = settings or get_settings()
    size = chunk_size if chunk_size is not None else active.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else active.chunk_overlap
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk_size must be positive and chunk_overlap in [0, chunk_size).")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        add_start_index=True,
        strip_whitespace=True,
    )
    return splitter.split_documents(documents)
