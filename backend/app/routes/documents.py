from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.storage import create_signed_url, delete_object, upload_object

router = APIRouter(
    prefix="/cases",
    tags=["Documents"],
    dependencies=[Depends(get_current_user)],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/csv",
    "text/plain",
    "image/jpeg",
    "image/png",
}


def _get_case_or_404(case_id: int, db: Session) -> models.Case:
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _get_document_or_404(document_id: int, db: Session) -> models.Document:
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post(
    "/{case_id}/documents",
    response_model=schemas.DocumentResponse,
    status_code=201,
)
async def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_case_or_404(case_id, db)

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="The selected file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit")

    original_name = Path(file.filename or "document").name
    object_path = f"cases/{case_id}/{uuid4().hex}_{original_name}"
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
    except Exception:
        db.rollback()
        try:
            delete_object(object_path)
        except RuntimeError:
            pass
        raise

    return document


@router.get(
    "/{case_id}/documents",
    response_model=list[schemas.DocumentResponse],
)
def list_documents(case_id: int, db: Session = Depends(get_db)):
    _get_case_or_404(case_id, db)

    return (
        db.query(models.Document)
        .filter(models.Document.case_id == case_id)
        .order_by(models.Document.uploaded_at.desc())
        .all()
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
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = _get_document_or_404(document_id, db)

    try:
        delete_object(document.storage_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.delete(document)
    db.commit()
    return None
