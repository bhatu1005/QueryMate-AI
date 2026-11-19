"""Extract searchable text and source metadata from supported document types."""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from docx import Document as DocxDocument
from langchain_core.documents import Document
from pypdf import PdfReader

logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}


class DocumentLoadError(ValueError):
    """Raised when a document cannot be identified or extracted."""


def clean_text(text: str) -> str:
    """Normalize whitespace while retaining line and paragraph boundaries."""
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read_bytes(source: str | Path | BinaryIO | bytes) -> tuple[bytes, str]:
    if isinstance(source, bytes):
        return source, "uploaded_document"
    if hasattr(source, "read"):
        name = Path(getattr(source, "name", "uploaded_document")).name
        raw = source.read()
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        return raw, name
    path = Path(source)
    try:
        return path.read_bytes(), path.name
    except OSError as exc:
        raise DocumentLoadError(f"Could not read document {path}: {exc}") from exc


def _extract_csv(raw: bytes) -> str:
    text = raw.decode("utf-8-sig", errors="replace")
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise DocumentLoadError(f"Invalid CSV document: {exc}") from exc
    if not rows:
        return ""
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)


def _extract_xlsx(raw: bytes, filename: str) -> list[Document]:
    try:
        sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None, dtype=str, engine="openpyxl")
    except Exception as exc:
        raise DocumentLoadError(f"Could not read XLSX document {filename}: {exc}") from exc
    documents = []
    for sheet_name, frame in sheets.items():
        frame = frame.fillna("").astype(str)
        rows = [" | ".join(str(value).strip() for value in row) for row in frame.values.tolist()]
        content = clean_text("\n".join(rows))
        if content:
            documents.append(Document(page_content=content, metadata={"sheet_name": str(sheet_name)}))
    return documents


def load_document(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> list[Document]:
    """Load one supported file into LangChain Documents with source metadata.

    PDF pages and XLSX sheets are returned as separate documents. CSV and other
    supported text formats return one document each. Empty/corrupt files raise
    ``DocumentLoadError`` so callers can report failures explicitly.
    """
    raw, detected_name = _read_bytes(source)
    file_name = Path(filename or detected_name).name
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DocumentLoadError(f"Unsupported file type '{suffix or '(none)'}'. Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}")
    if not raw:
        raise DocumentLoadError(f"Document {file_name} is empty.")
    source_type = suffix.lstrip(".")
    file_id = hashlib.sha256(raw).hexdigest()
    base_metadata = {"filename": file_name, "source_type": source_type, "document_id": file_id, "source": file_name}
    try:
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(raw))
            docs = [
                Document(page_content=clean_text(page.extract_text() or ""), metadata={"page_number": index, "source_location": f"page {index}"})
                for index, page in enumerate(reader.pages, start=1)
            ]
        elif suffix == ".docx":
            doc = DocxDocument(io.BytesIO(raw))
            parts = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
            for table in doc.tables:
                parts.extend(" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows)
            docs = [Document(page_content=clean_text("\n".join(parts)), metadata={})]
        elif suffix == ".txt":
            docs = [Document(page_content=clean_text(raw.decode("utf-8-sig", errors="replace")), metadata={})]
        elif suffix == ".csv":
            docs = [Document(page_content=clean_text(_extract_csv(raw)), metadata={})]
        else:
            docs = _extract_xlsx(raw, file_name)
    except DocumentLoadError:
        raise
    except Exception as exc:
        logger.exception("Failed extracting %s", file_name)
        raise DocumentLoadError(f"Could not extract {file_name}: {exc}") from exc

    result = []
    for doc in docs:
        doc.page_content = clean_text(doc.page_content)
        if not doc.page_content:
            continue
        doc.metadata = {**base_metadata, **doc.metadata}
        result.append(doc)
    if not result:
        raise DocumentLoadError(f"Document {file_name} contains no extractable text.")
    return result
