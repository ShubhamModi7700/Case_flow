from sqlalchemy.orm import Session

from app import models
from app.models import utc_now
from app.services.chunking import split_text
from app.services.document_extraction import extract_document
from app.services.embeddings import create_embeddings
from app.services.openai_client import embedding_model
from app.storage import download_object


def index_document(*, document: models.Document, db: Session) -> None:
    document.processing_status = "Extracting"
    document.embedding_status = "Processing"
    document.processing_error = None
    db.commit()
    try:
        payload = download_object(document.storage_path)
        extracted = extract_document(file_name=document.file_name, content=payload)
        document.processing_status = "Chunking"
        db.commit()

        prepared: list[dict] = []
        for section in extracted.sections:
            for chunk in split_text(section.text):
                prepared.append({
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "page_number": section.page_number,
                    "sheet_name": section.sheet_name,
                    "email_section": section.email_section,
                    "metadata": section.metadata,
                })
        if not prepared:
            raise ValueError("Keine verwertbaren Textabschnitte gefunden.")

        document.processing_status = "Embedding"
        db.commit()
        vectors = create_embeddings([item["content"] for item in prepared])

        db.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == document.id
        ).delete(synchronize_session=False)

        for index, item in enumerate(prepared):
            db.add(models.DocumentChunk(
                document_id=document.id,
                case_id=document.case_id,
                chunk_index=index,
                content=item["content"],
                source_type=extracted.source_type,
                page_number=item["page_number"],
                sheet_name=item["sheet_name"],
                email_section=item["email_section"],
                metadata_json=item["metadata"],
                token_count=item["token_count"],
                embedding=vectors[index],
                embedding_model=embedding_model(),
            ))

        document.processing_status = "Ready"
        document.embedding_status = "Ready"
        document.chunk_count = len(prepared)
        document.processed_at = utc_now()
        db.commit()
    except Exception as exc:
        db.rollback()
        document.processing_status = "Failed"
        document.embedding_status = "Failed"
        document.processing_error = str(exc)
        db.add(document)
        db.commit()
        raise
