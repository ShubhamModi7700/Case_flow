from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.models import utc_now
from app.services.chunking import split_text
from app.services.document_extraction import ExtractedDocument, extract_document
from app.services.embeddings import create_embeddings
from app.services.openai_client import embedding_model
from app.storage import download_object


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENT_DEPTH = 3
SUPPORTED_ATTACHMENT_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".eml", ".msg", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".webp",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
DECORATIVE_IMAGE_WORDS = {
    "logo", "icon", "linkedin", "facebook", "instagram", "twitter",
    "signature", "email-signature", "profile", "avatar", "employee-photo",
}
MIN_OCR_IMAGE_BYTES = 15_000


def should_ocr_image_attachment(*, file_name: str, content: bytes) -> bool:
    """Skip common email decoration while OCR-ing real image attachments.

    This is deliberately conservative for Outlook-style embedded images.
    PDFs are not filtered here; scanned PDFs keep using the existing PDF
    vision fallback in document_extraction.py.
    """
    name = Path(file_name).name.lower()
    extension = Path(name).suffix.lower()
    if extension not in IMAGE_EXTENSIONS:
        return False
    if not content or len(content) < MIN_OCR_IMAGE_BYTES:
        return False
    if any(word in name for word in DECORATIVE_IMAGE_WORDS):
        return False

    # Outlook commonly names embedded signature graphics image001.png,
    # image002.jpg, etc. Treat those as decoration by default.
    stem = Path(name).stem
    if stem.startswith("image") and stem[5:].isdigit():
        return False

    return True


def _document_level_metadata(extracted: ExtractedDocument) -> dict[str, Any]:
    """Keep useful provenance while excluding attachment payload objects."""
    return {
        key: value
        for key, value in (extracted.metadata or {}).items()
        if key not in {"attachments"}
    }


def _prepare_extracted_document(
    *,
    extracted: ExtractedDocument,
    current_filename: str,
    root_filename: str,
    parent_filename: str | None = None,
    depth: int = 0,
    inherited_email_metadata: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Flatten an email and supported nested attachments into indexable chunks.

    Attachment contents are not written back to storage and no original file is
    modified. Every attachment chunk retains enough provenance to show the
    attachment filename and the parent/root email in citations.
    """
    prepared: list[dict[str, Any]] = []
    warnings: list[str] = []

    own_metadata = _document_level_metadata(extracted)
    email_metadata = dict(inherited_email_metadata or {})
    if extracted.source_type in {"eml", "msg"}:
        for key in ("sender", "recipient", "subject", "document_date"):
            if own_metadata.get(key):
                email_metadata[key] = own_metadata[key]

    is_attachment = depth > 0
    for section in extracted.sections:
        section_metadata = dict(email_metadata)
        section_metadata.update(own_metadata)
        section_metadata.update(section.metadata or {})
        section_metadata.update(
            {
                "source_filename": current_filename,
                "is_attachment": is_attachment,
                "attachment_depth": depth,
                "root_filename": root_filename,
            }
        )
        if parent_filename:
            section_metadata["parent_filename"] = parent_filename
        if is_attachment:
            section_metadata["attachment_filename"] = current_filename
            section_metadata["root_email_filename"] = root_filename

        for chunk in split_text(section.text):
            prepared.append(
                {
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "page_number": section.page_number,
                    "sheet_name": section.sheet_name,
                    "email_section": section.email_section,
                    "metadata": section_metadata,
                    "source_type": extracted.source_type,
                }
            )

    if not extracted.attachments:
        return prepared, warnings

    if depth >= MAX_ATTACHMENT_DEPTH:
        warnings.append(
            f"Anhänge in {current_filename} wurden ab Tiefe {MAX_ATTACHMENT_DEPTH} nicht weiter verarbeitet."
        )
        return prepared, warnings

    for attachment in extracted.attachments:
        attachment_name = Path(attachment.file_name).name
        extension = Path(attachment_name).suffix.lower()
        if extension not in SUPPORTED_ATTACHMENT_EXTENSIONS:
            warnings.append(
                f"Anhang {attachment_name}: Format {extension or 'unbekannt'} wird nicht indexiert."
            )
            continue
        if len(attachment.content) > MAX_ATTACHMENT_BYTES:
            warnings.append(
                f"Anhang {attachment_name}: größer als 10 MB und deshalb nicht indexiert."
            )
            continue

        if extension in IMAGE_EXTENSIONS and not should_ocr_image_attachment(
            file_name=attachment_name,
            content=attachment.content,
        ):
            # Decorative email images are intentionally ignored. Do not show
            # them as processing errors/warnings because this is expected.
            continue

        try:
            child = extract_document(
                file_name=attachment_name,
                content=attachment.content,
            )
        except Exception as exc:
            warnings.append(f"Anhang {attachment_name}: {exc}")
            continue

        child_prepared, child_warnings = _prepare_extracted_document(
            extracted=child,
            current_filename=attachment_name,
            root_filename=root_filename,
            parent_filename=current_filename,
            depth=depth + 1,
            inherited_email_metadata=email_metadata,
        )
        prepared.extend(child_prepared)
        warnings.extend(child_warnings)

    return prepared, warnings


def prepare_document_chunks(*, file_name: str, content: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    """Pure extraction/chunk preparation helper used by indexing and tests."""
    extracted = extract_document(file_name=file_name, content=content)
    return _prepare_extracted_document(
        extracted=extracted,
        current_filename=Path(file_name).name,
        root_filename=Path(file_name).name,
    )


def index_document(*, document: models.Document, db: Session) -> None:
    document.processing_status = "Extracting"
    document.embedding_status = "Processing"
    document.processing_error = None
    db.commit()
    try:
        payload = download_object(document.storage_path)
        prepared, warnings = prepare_document_chunks(
            file_name=document.file_name,
            content=payload,
        )
        document.processing_status = "Chunking"
        db.commit()

        if not prepared:
            raise ValueError("Keine verwertbaren Textabschnitte gefunden.")

        document.processing_status = "Embedding"
        db.commit()
        vectors = create_embeddings([item["content"] for item in prepared])

        db.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == document.id
        ).delete(synchronize_session=False)

        for index, item in enumerate(prepared):
            db.add(
                models.DocumentChunk(
                    document_id=document.id,
                    case_id=document.case_id,
                    chunk_index=index,
                    content=item["content"],
                    source_type=item["source_type"],
                    page_number=item["page_number"],
                    sheet_name=item["sheet_name"],
                    email_section=item["email_section"],
                    metadata_json=item["metadata"],
                    token_count=item["token_count"],
                    embedding=vectors[index],
                    embedding_model=embedding_model(),
                )
            )

        document.processing_status = "Ready"
        document.embedding_status = "Ready"
        document.chunk_count = len(prepared)
        document.processed_at = utc_now()
        # Keep non-fatal attachment extraction warnings visible without marking
        # the whole parent email as failed.
        document.processing_error = (
            "Warnungen bei der Anhangsverarbeitung: " + " | ".join(warnings[:20])
            if warnings
            else None
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        document.processing_status = "Failed"
        document.embedding_status = "Failed"
        document.processing_error = str(exc)
        db.add(document)
        db.commit()
        raise
