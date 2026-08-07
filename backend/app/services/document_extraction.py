from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
from typing import Any

import extract_msg
from docx import Document as WordDocument
from openpyxl import load_workbook
from pypdf import PdfReader

from app.services.pdf_vision import extract_scanned_pdf_with_openai


@dataclass
class ExtractedSection:
    text: str
    page_number: int | None = None
    sheet_name: str | None = None
    email_section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    source_type: str
    sections: list[ExtractedSection]
    metadata: dict[str, Any] = field(default_factory=dict)


def extract_pdf(
    content: bytes,
    *,
    file_name: str = "document.pdf",
) -> ExtractedDocument:
    reader = PdfReader(BytesIO(content))
    sections: list[ExtractedSection] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            sections.append(
                ExtractedSection(
                    text=text,
                    page_number=page_number,
                    metadata={"vision_extraction": False},
                )
            )

    # A scan can occasionally contain only a tiny text layer (for example a
    # scanner watermark or page number). Treat that as insufficient and use
    # the PDF vision fallback as well.
    extracted_character_count = sum(len(section.text) for section in sections)
    if extracted_character_count >= 50:
        return ExtractedDocument(
            "pdf",
            sections,
            {
                "page_count": len(reader.pages),
                "vision_extraction": False,
            },
        )

    vision_result = extract_scanned_pdf_with_openai(
        content,
        file_name=file_name,
    )
    vision_sections = [
        ExtractedSection(
            text=page.text.strip(),
            page_number=page.page_number,
            metadata={
                "vision_extraction": True,
                "extraction_provider": "openai",
            },
        )
        for page in vision_result.pages
        if page.text.strip()
    ]

    return ExtractedDocument(
        "pdf_vision",
        vision_sections,
        {
            "page_count": len(reader.pages),
            "vision_extraction": True,
            "extraction_provider": "openai",
        },
    )


def extract_docx(content: bytes) -> ExtractedDocument:
    document = WordDocument(BytesIO(content))
    sections: list[ExtractedSection] = []
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    if paragraphs:
        sections.append(ExtractedSection("\n\n".join(paragraphs)))
    for index, table in enumerate(document.tables):
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        table_text = "\n".join(row for row in rows if row.strip()).strip()
        if table_text:
            sections.append(
                ExtractedSection(table_text, metadata={"table_index": index})
            )
    if not sections:
        raise ValueError("Das DOCX-Dokument enthält keinen extrahierbaren Text.")
    return ExtractedDocument("docx", sections)


def extract_xlsx(content: bytes) -> ExtractedDocument:
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    sections: list[ExtractedSection] = []
    for worksheet in workbook.worksheets:
        rows = []
        for row in worksheet.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            if any(value.strip() for value in values):
                rows.append(" | ".join(values))
        if rows:
            sections.append(
                ExtractedSection("\n".join(rows), sheet_name=worksheet.title)
            )
    if not sections:
        raise ValueError("Die XLSX-Datei enthält keine verwertbaren Zellwerte.")
    return ExtractedDocument("xlsx", sections, {"sheet_count": len(workbook.sheetnames)})


def extract_eml(content: bytes) -> ExtractedDocument:
    message = BytesParser(policy=policy.default).parsebytes(content)
    body_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                try:
                    value = part.get_content()
                    if value and value.strip():
                        body_parts.append(value.strip())
                except Exception:
                    continue
    else:
        try:
            value = message.get_content()
            if value and value.strip():
                body_parts.append(value.strip())
        except Exception:
            pass

    header = "\n".join(
        [
            f"Von: {message.get('From', '')}",
            f"An: {message.get('To', '')}",
            f"Betreff: {message.get('Subject', '')}",
            f"Datum: {message.get('Date', '')}",
        ]
    )
    attachments = [part.get_filename() for part in message.iter_attachments() if part.get_filename()]
    text = f"{header}\n\n" + "\n\n".join(body_parts)
    if attachments:
        text += "\n\nAnhänge: " + ", ".join(attachments)
    return ExtractedDocument(
        "eml",
        [ExtractedSection(text.strip(), email_section="message")],
        {"attachments": attachments},
    )


def extract_msg_document(content: bytes) -> ExtractedDocument:
    message = extract_msg.Message(BytesIO(content))
    text = "\n".join(
        [
            f"Von: {message.sender or ''}",
            f"An: {message.to or ''}",
            f"Betreff: {message.subject or ''}",
            f"Datum: {message.date or ''}",
            "",
            message.body or "",
        ]
    ).strip()
    if not text:
        raise ValueError("Die MSG-Datei enthält keinen extrahierbaren Inhalt.")
    return ExtractedDocument("msg", [ExtractedSection(text, email_section="message")])


def extract_document(*, file_name: str, content: bytes) -> ExtractedDocument:
    extension = Path(file_name).suffix.lower()
    if extension == ".pdf":
        return extract_pdf(content, file_name=file_name)
    if extension == ".docx":
        return extract_docx(content)
    if extension == ".xlsx":
        return extract_xlsx(content)
    if extension == ".eml":
        return extract_eml(content)
    if extension == ".msg":
        return extract_msg_document(content)
    if extension in {".doc", ".xls"}:
        raise ValueError(
            "Legacy-DOC/XLS muss vor der KI-Verarbeitung in DOCX/XLSX umgewandelt werden."
        )
    raise ValueError(f"Das Format {extension or 'unbekannt'} wird nicht unterstützt.")
