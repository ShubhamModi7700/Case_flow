from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(
    prefix="/cases",
    tags=["Documents"],
    dependencies=[Depends(get_current_user)],
)

UPLOAD_DIRECTORY = Path("uploads")
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)


@router.post(
    "/{case_id}/documents",
    response_model=schemas.DocumentResponse,
)
def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    uploaded_by: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    case_directory = UPLOAD_DIRECTORY / str(case_id)
    case_directory.mkdir(parents=True, exist_ok=True)

    original_name = Path(
        file.filename or "document"
    ).name

    stored_name = (
        f"{uuid4().hex}_{original_name}"
    )

    file_path = case_directory / stored_name

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    document = models.Document(
        case_id=case_id,
        file_name=original_name,
        description=description,
        uploaded_by=uploaded_by,
        file_path=str(file_path),
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


@router.get(
    "/{case_id}/documents",
    response_model=list[schemas.DocumentResponse],
)
def list_documents(
    case_id: int,
    db: Session = Depends(get_db),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    return (
        db.query(models.Document)
        .filter(
            models.Document.case_id == case_id
        )
        .order_by(
            models.Document.uploaded_at.desc()
        )
        .all()
    )


@router.get(
    "/documents/{document_id}/download",
)
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = (
        db.query(models.Document)
        .filter(
            models.Document.id == document_id
        )
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = Path(document.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Stored file not found",
        )

    return FileResponse(
        path=file_path,
        filename=document.file_name,
        media_type="application/octet-stream",
    )