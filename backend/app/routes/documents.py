from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth import get_current_user, require_editor, require_manager
from app.database import get_db
from app.storage import (
    create_signed_url,
    delete_object,
    upload_object,
)
from app.services.document_indexing import index_document

router = APIRouter(
    tags=["Documents"],
    dependencies=[Depends(get_current_user)],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Version 1 supported formats:
# PDF, Word (DOC/DOCX), Excel (XLS/XLSX), Email (EML/MSG)
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "message/rfc822",
    "application/vnd.ms-outlook",
    "application/x-msg",
}

ALLOWED_FILE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".eml",
    ".msg",
}


def _get_case_or_404(case_id: int, db: Session) -> models.Case:
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden")
    return case


def _get_document_or_404(document_id: int, db: Session) -> models.Document:
    document = (
        db.query(models.Document)
        .options(joinedload(models.Document.case))
        .filter(models.Document.id == document_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return document


def _serialize_document(document: models.Document) -> schemas.DocumentResponse:
    return schemas.DocumentResponse(
        id=document.id,
        case_id=document.case_id,
        file_name=document.file_name,
        content_type=document.content_type,
        file_size=document.file_size,
        description=document.description,
        uploaded_by=document.uploaded_by,
        uploaded_at=document.uploaded_at,
        processing_status=document.processing_status,
        processing_error=document.processing_error,
        embedding_status=document.embedding_status,
        chunk_count=document.chunk_count,
        processed_at=document.processed_at,
        company=document.case.company if document.case else None,
        department=document.case.department if document.case else None,
    )


def _validate_file_type(*, file_name: str, content_type: str) -> None:
    """Validate using MIME type and extension.

    Some browsers upload Outlook MSG files with a generic MIME type such as
    application/octet-stream, so the extension is checked as a fallback.
    """
    extension = Path(file_name).suffix.lower()
    mime_is_allowed = content_type in ALLOWED_CONTENT_TYPES
    extension_is_allowed = extension in ALLOWED_FILE_EXTENSIONS

    if not mime_is_allowed and not extension_is_allowed:
        raise HTTPException(
            status_code=415,
            detail=(
                "Nicht unterstützter Dateityp. "
                "Erlaubte Formate: PDF, DOC, DOCX, XLS, XLSX, EML und MSG."
            ),
        )


async def _store_document(
    *,
    file: UploadFile,
    description: str | None,
    case_id: int | None,
    db: Session,
    current_user: models.User,
) -> schemas.DocumentResponse:
    if case_id is not None:
        _get_case_or_404(case_id, db)

    original_name = Path(file.filename or "document").name
    content_type = file.content_type or "application/octet-stream"

    _validate_file_type(
        file_name=original_name,
        content_type=content_type,
    )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Die ausgewählte Datei ist leer",
        )

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Die Datei überschreitet das Limit von 10 MB",
        )

    object_path = f"documents/{uuid4().hex}_{original_name}"
    cleaned_description = description.strip() if description else None
    cleaned_description = cleaned_description or None

    try:
        upload_object(object_path, content, content_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    document = models.Document(
        case_id=case_id,
        file_name=original_name,
        storage_path=object_path,
        content_type=content_type,
        file_size=len(content),
        description=cleaned_description,
        uploaded_by=current_user.full_name,
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)
        if document.case_id is not None:
            document.case = _get_case_or_404(document.case_id, db)
    except Exception:
        db.rollback()
        try:
            delete_object(object_path)
        except RuntimeError:
            pass
        raise

    return _serialize_document(document)


@router.post(
    "/documents",
    response_model=schemas.DocumentResponse,
    status_code=201,
)
async def upload_independent_document(
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    case_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    """Upload a document independently, optionally linking it to a case."""
    return await _store_document(
        file=file,
        description=description,
        case_id=case_id,
        db=db,
        current_user=current_user,
    )


@router.post(
    "/cases/{case_id}/documents",
    response_model=schemas.DocumentResponse,
    status_code=201,
)
async def upload_case_document(
    case_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    """Upload a document and link it directly to a case."""
    return await _store_document(
        file=file,
        description=description,
        case_id=case_id,
        db=db,
        current_user=current_user,
    )


@router.get(
    "/documents",
    response_model=list[schemas.DocumentResponse],
)
def list_all_documents(db: Session = Depends(get_db)):
    documents = (
        db.query(models.Document)
        .options(joinedload(models.Document.case))
        .order_by(models.Document.uploaded_at.desc())
        .all()
    )
    return [_serialize_document(document) for document in documents]


@router.get(
    "/cases/{case_id}/documents",
    response_model=list[schemas.DocumentResponse],
)
def list_case_documents(case_id: int, db: Session = Depends(get_db)):
    _get_case_or_404(case_id, db)
    documents = (
        db.query(models.Document)
        .options(joinedload(models.Document.case))
        .filter(models.Document.case_id == case_id)
        .order_by(models.Document.uploaded_at.desc())
        .all()
    )
    return [_serialize_document(document) for document in documents]


@router.patch(
    "/documents/{document_id}/case",
    response_model=schemas.DocumentResponse,
)
def assign_document_to_case(
    document_id: int,
    payload: schemas.DocumentCaseUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_editor),
):
    document = _get_document_or_404(document_id, db)

    if payload.case_id is not None:
        document.case = _get_case_or_404(payload.case_id, db)
        document.case_id = payload.case_id
    else:
        document.case = None
        document.case_id = None

    db.commit()
    db.refresh(document)

    if document.case_id is not None:
        document.case = _get_case_or_404(document.case_id, db)

    return _serialize_document(document)


@router.post(
    "/documents/{document_id}/process",
    response_model=schemas.DocumentProcessingResponse,
)
def process_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_editor),
):
    document = _get_document_or_404(document_id, db)
    if document.processing_status in {"Extracting", "Chunking", "Embedding"}:
        raise HTTPException(status_code=409, detail="Das Dokument wird bereits verarbeitet.")
    try:
        index_document(document=document, db=db)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return schemas.DocumentProcessingResponse(
        document_id=document.id,
        processing_status=document.processing_status,
        embedding_status=document.embedding_status,
        chunk_count=document.chunk_count,
        processing_error=document.processing_error,
    )


@router.get(
    "/documents/{document_id}/processing-status",
    response_model=schemas.DocumentProcessingResponse,
)
def get_processing_status(document_id: int, db: Session = Depends(get_db)):
    document = _get_document_or_404(document_id, db)
    return schemas.DocumentProcessingResponse(
        document_id=document.id,
        processing_status=document.processing_status,
        embedding_status=document.embedding_status,
        chunk_count=document.chunk_count,
        processing_error=document.processing_error,
    )


@router.get(
    "/documents/{document_id}/download",
    response_model=schemas.DocumentDownloadResponse,
)
def get_document_download_url(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = _get_document_or_404(document_id, db)

    try:
        signed_url = create_signed_url(document.storage_path, expires_in=60)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return schemas.DocumentDownloadResponse(
        download_url=signed_url,
        file_name=document.file_name,
        expires_in=60,
    )


@router.delete(
    "/documents/{document_id}",
    status_code=204,
)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_manager),
):
    document = _get_document_or_404(document_id, db)

    try:
        delete_object(document.storage_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.delete(document)
    db.commit()
    return None