from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.storage import download_object, upload_object

router = APIRouter(
    prefix="/cases",
    tags=["Documents"],
    dependencies=[Depends(get_current_user)],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post(
    "/{case_id}/documents",
    response_model=schemas.DocumentResponse,
)
async def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    uploaded_by: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit")

    original_name = Path(file.filename or "document").name
    object_path = f"cases/{case_id}/{uuid4().hex}_{original_name}"

    try:
        upload_object(
            object_path,
            content,
            file.content_type or "application/octet-stream",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    document = models.Document(
        case_id=case_id,
        file_name=original_name,
        description=description,
        uploaded_by=uploaded_by,
        file_path=object_path,
    )

    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get(
    "/{case_id}/documents",
    response_model=list[schemas.DocumentResponse],
)
def list_documents(case_id: int, db: Session = Depends(get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    return (
        db.query(models.Document)
        .filter(models.Document.case_id == case_id)
        .order_by(models.Document.uploaded_at.desc())
        .all()
    )


@router.get("/documents/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        content, media_type = download_object(document.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Stored file not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    safe_filename = document.file_name.replace('"', "")
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"'
        },
    )
