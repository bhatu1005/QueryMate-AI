"""File extraction and upload service tests for every supported file type."""

from io import BytesIO

import pandas as pd
import pytest
from docx import Document as DocxDocument
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from rag.document_loader import DocumentLoadError, load_document
from services import file_service


def make_pdf(text: str) -> bytes:
    """Build a minimal one-page PDF containing extractable text using pypdf objects."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})})
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 40 250 Td ({escaped}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_docx() -> bytes:
    document = DocxDocument()
    document.add_paragraph("DOCX body for QueryMate.")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def make_xlsx() -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([["metric", "value"], ["sales", 17]]).to_excel(writer, sheet_name="Stats", header=False, index=False)
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "content", "expected"),
    [
        ("sample.pdf", make_pdf("PDF body"), "PDF body"),
        ("sample.docx", make_docx(), "DOCX body"),
        ("sample.txt", b"TXT body", "TXT body"),
        ("sample.csv", b"metric,value\nsales,17", "sales | 17"),
        ("sample.xlsx", make_xlsx(), "sales | 17"),
    ],
    ids=["pdf", "docx", "txt", "csv", "xlsx"],
)
def test_loads_all_supported_file_types(filename: str, content: bytes, expected: str) -> None:
    documents = load_document(content, filename=filename)
    assert documents
    assert expected in "\n".join(document.page_content for document in documents)
    assert all(document.metadata["filename"] == filename for document in documents)
    assert all(document.metadata["source_type"] == filename.rsplit(".", 1)[-1] for document in documents)


def test_pdf_page_metadata_and_corrupt_empty_handling() -> None:
    document = load_document(make_pdf("Page text"), filename="pages.pdf")[0]
    assert document.metadata["page_number"] == 1
    with pytest.raises(DocumentLoadError):
        load_document(b"%PDF-corrupt", filename="bad.pdf")
    with pytest.raises(DocumentLoadError, match="empty"):
        load_document(b"", filename="empty.txt")
    with pytest.raises(DocumentLoadError):
        load_document(b"not-a-docx", filename="bad.docx")
    with pytest.raises(DocumentLoadError):
        load_document(b"not-an-xlsx", filename="bad.xlsx")


def test_upload_service_delegates_to_file_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    class Upload:
        name = "input.txt"

        def getvalue(self):
            return b"Upload body"

    observed = []

    def fake_file_agent(files, settings=None):
        observed.append(files[0].name)
        return {"status": "ok", "file_summary": "Summary", "uploaded_documents": [{"document_id": "abc", "chunk_count": 1}]}

    monkeypatch.setattr(file_service, "process_uploaded_files", fake_file_agent)
    results = file_service.ingest_uploaded_files([Upload()])
    assert observed == ["input.txt"]
    assert results[0]["status"] == "indexed"
    assert results[0]["summary"] == "Summary"


def test_upload_service_rejects_unsupported_and_oversized(monkeypatch: pytest.MonkeyPatch) -> None:
    class Upload:
        def __init__(self, name, data):
            self.name = name
            self.data = data

        def getvalue(self):
            return self.data

    from types import SimpleNamespace

    results = file_service.ingest_uploaded_files(
        [Upload("bad.exe", b"x"), Upload("large.txt", b"12345")],
        SimpleNamespace(max_upload_size_mb=0),
    )
    assert [item["status"] for item in results] == ["error", "error"]
