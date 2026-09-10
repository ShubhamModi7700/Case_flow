from email.message import EmailMessage
from io import BytesIO

from docx import Document as WordDocument

from app.services.case_qa import build_sources
from app.services.document_indexing import prepare_document_chunks


def _docx_bytes(text: str) -> bytes:
    document = WordDocument()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _email_with_attachment(*, attachment_name: str, attachment_bytes: bytes) -> bytes:
    message = EmailMessage()
    message["From"] = "kanzlei@example.com"
    message["To"] = "empfaenger@example.com"
    message["Subject"] = "Übergabe Buchhaltungsunterlagen"
    message["Date"] = "Fri, 26 Sep 2025 10:30:00 +0200"
    message.set_content("Anbei übersenden wir die Buchhaltungsunterlagen.")
    message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=attachment_name,
    )
    return message.as_bytes()


def test_eml_attachment_content_is_flattened_with_provenance():
    payload = _email_with_attachment(
        attachment_name="Buchhaltung_2025.docx",
        attachment_bytes=_docx_bytes("Kontenblätter und Buchungsjournal wurden übergeben."),
    )

    prepared, warnings = prepare_document_chunks(
        file_name="Mail_26-09-2025.eml",
        content=payload,
    )

    assert warnings == []
    assert any("Anbei übersenden" in item["content"] for item in prepared)

    attachment_chunks = [
        item
        for item in prepared
        if item["metadata"].get("is_attachment") is True
    ]
    assert attachment_chunks
    attachment = attachment_chunks[0]
    assert "Kontenblätter" in attachment["content"]
    assert attachment["metadata"]["source_filename"] == "Buchhaltung_2025.docx"
    assert attachment["metadata"]["parent_filename"] == "Mail_26-09-2025.eml"
    assert attachment["metadata"]["root_email_filename"] == "Mail_26-09-2025.eml"
    assert attachment["metadata"]["sender"] == "kanzlei@example.com"
    assert "26 Sep 2025" in attachment["metadata"]["document_date"]


def test_build_sources_exposes_attachment_as_individual_citable_source():
    chunks = [
        {
            "chunk_id": 501,
            "document_id": 12,
            "file_name": "Mail_26-09-2025.eml",
            "content": "Kontenblätter und Buchungsjournal wurden übergeben.",
            "page_number": None,
            "sheet_name": None,
            "email_section": None,
            "metadata": {
                "source_filename": "Buchhaltung_2025.docx",
                "is_attachment": True,
                "parent_filename": "Mail_26-09-2025.eml",
                "root_email_filename": "Mail_26-09-2025.eml",
                "attachment_depth": 1,
                "sender": "kanzlei@example.com",
                "document_date": "Fri, 26 Sep 2025 10:30:00 +0200",
            },
        }
    ]

    sources = build_sources(chunks)

    assert sources[0]["source_id"] == "S1"
    assert sources[0]["filename"] == "Buchhaltung_2025.docx"
    assert sources[0]["is_attachment"] is True
    assert sources[0]["parent_filename"] == "Mail_26-09-2025.eml"
