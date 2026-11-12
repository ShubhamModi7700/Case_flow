from pathlib import Path
from io import BytesIO
from html import escape

from fastapi.responses import Response, HTMLResponse
from docx import Document as WordDocument
from openpyxl import load_workbook
import re
import unicodedata
from uuid import uuid4
import base64
import hashlib
import hmac
import json
import os
import time

from pydantic import BaseModel, Field

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
from app.services.case_access import (
    ensure_responsible_access,
    has_global_case_access,
    require_case_edit,
    require_case_view,
)
from app.storage import (
    create_signed_url,
    download_object,
    delete_object,
    upload_object,
    create_signed_upload_url,
    get_object_size,
)
from app.services.document_indexing import index_document
from app.services.document_jobs import enqueue
from app.services.case_embeddings import refresh_case_embedding
from app.services.document_case_routing import (
    CaseCandidate,
    suggest_document_case_route,
)
from app.services.embeddings import create_query_embedding
from app.services.retrieval import match_cases
from app.services.risk import refresh_risk_suggestion

router = APIRouter(
    tags=["Documents"],
    dependencies=[Depends(get_current_user)],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _safe_storage_filename(file_name: str) -> str:
    """Return an ASCII-only filename safe for Supabase Storage object keys.

    The original filename is still stored in Document.file_name and shown in the UI.
    Only the internal Storage key uses this normalized variant.
    """
    original = Path(file_name or "document").name
    path = Path(original)
    suffix = path.suffix.lower()
    stem = path.stem or "document"

    stem = (
        stem.replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("._-") or "document"

    stem = stem[:120].rstrip("._-") or "document"
    safe_suffix = re.sub(r"[^a-z0-9.]", "", suffix)[:16]
    return f"{stem}{safe_suffix}"

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

    storage_name = _safe_storage_filename(original_name)
    object_path = f"documents/{uuid4().hex}_{storage_name}"
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
        enqueue(db, document.id)
        db.commit()
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


DIRECT_UPLOAD_MAX_BYTES = 100 * 1024 * 1024
DIRECT_UPLOAD_TTL_SECONDS = 60 * 60
DIRECT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".eml", ".msg"}


class UploadInitRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    file_size: int = Field(gt=0, le=DIRECT_UPLOAD_MAX_BYTES)
    content_type: str = "application/octet-stream"
    case_id: int | None = None
    description: str | None = Field(default=None, max_length=2000)
    batch_item_id: str | None = None


class UploadCompleteRequest(BaseModel):
    upload_token: str


class BatchCreateRequest(BaseModel):
    filenames: list[str] = Field(min_length=1, max_length=500)
    case_id: int | None = None


class BatchFailureRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _owned_batch_item(db: Session, user: models.User, item_id: str):
    item = db.query(models.DocumentUploadBatchItem).join(
        models.DocumentUploadBatch,
        models.DocumentUploadBatch.id == models.DocumentUploadBatchItem.batch_id,
    ).filter(
        models.DocumentUploadBatchItem.id == item_id,
        models.DocumentUploadBatch.owner_id == user.id,
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Upload-Eintrag nicht gefunden")
    return item


def _batch_details(db: Session, batch: models.DocumentUploadBatch) -> dict:
    items = db.query(models.DocumentUploadBatchItem).filter_by(batch_id=batch.id).order_by(
        models.DocumentUploadBatchItem.created_at, models.DocumentUploadBatchItem.id
    ).all()
    doc_ids = [item.document_id for item in items if item.document_id is not None]
    docs = {doc.id: doc for doc in db.query(models.Document).filter(models.Document.id.in_(doc_ids)).all()} if doc_ids else {}
    jobs = {job.document_id: job for job in db.query(models.DocumentProcessingJob).filter(
        models.DocumentProcessingJob.document_id.in_(doc_ids)
    ).all()} if doc_ids else {}
    output = []
    counts = {status: 0 for status in ("Pending", "Interrupted", "Uploading", "Uploaded", "Running", "Ready", "Partial", "Failed")}
    for item in items:
        doc = docs.get(item.document_id)
        job = jobs.get(item.document_id)
        status = item.upload_status
        error = item.upload_error
        if not doc and status == "Pending" and item.created_at:
            from datetime import datetime, timezone, timedelta
            created = item.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - created > timedelta(hours=1):
                status = "Interrupted"
                error = "Upload nicht abgeschlossen; Datei erneut auswählen"
        if doc:
            if job and job.status == "Failed":
                status = "Failed"
                error = job.last_error or doc.processing_error
            elif job and job.status == "Running":
                status = "Running"
            elif doc.processing_status == "Partial":
                status = "Partial"
                error = doc.processing_error
            elif doc.processing_status == "Ready" and doc.embedding_status == "Ready":
                status = "Ready"
            elif job and job.status == "Pending":
                status = "Pending"
            else:
                status = "Uploaded"
                error = doc.processing_error
        counts[status] = counts.get(status, 0) + 1
        output.append({"id": item.id, "filename": item.filename, "document_id": item.document_id,
                       "status": status, "error": error})
    return {"id": batch.id, "case_id": batch.case_id, "created_at": batch.created_at, "total": len(items),
            "counts": counts, "items": output}


@router.post("/documents/batches", status_code=201)
def create_document_batch(
    request: BatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    filenames = [Path(name).name for name in request.filenames]
    if any(not name or len(name) > 255 for name in filenames):
        raise HTTPException(status_code=422, detail="Ungültiger Dateiname")
    if request.case_id is not None:
        require_case_edit(db, current_user, request.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Fallzuordnung erforderlich")
    batch = models.DocumentUploadBatch(id=str(uuid4()), owner_id=current_user.id, case_id=request.case_id)
    db.add(batch)
    items = [models.DocumentUploadBatchItem(id=str(uuid4()), batch_id=batch.id, filename=name)
             for name in filenames]
    db.add_all(items)
    db.commit()
    return {"id": batch.id, "items": [{"id": item.id, "filename": item.filename} for item in items]}


@router.get("/documents/batches")
def list_document_batches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    batches = db.query(models.DocumentUploadBatch).filter_by(owner_id=current_user.id).order_by(
        models.DocumentUploadBatch.created_at.desc()
    ).limit(25).all()
    return [_batch_details(db, batch) for batch in batches]


@router.get("/documents/batches/{batch_id}")
def get_document_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    batch = db.query(models.DocumentUploadBatch).filter_by(id=batch_id, owner_id=current_user.id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload-Batch nicht gefunden")
    return _batch_details(db, batch)


@router.post("/documents/batches/items/{item_id}/failed")
def report_batch_upload_failure(
    item_id: str,
    request: BatchFailureRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    item = _owned_batch_item(db, current_user, item_id)
    if item.document_id is not None:
        raise HTTPException(status_code=409, detail="Datei wurde bereits gespeichert")
    item.upload_status = "Failed"
    item.upload_error = request.message[:2000]
    db.commit()
    return {"status": "Failed"}


@router.post("/documents/batches/items/{item_id}/retry", status_code=202)
def retry_batch_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    item = _owned_batch_item(db, current_user, item_id)
    if item.document_id is None:
        raise HTTPException(status_code=409, detail="Datei muss erneut vom Browser hochgeladen werden")
    document = _get_document_or_404(item.document_id, db)
    if document.case_id is not None:
        require_case_edit(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")
    if document.processing_status == "Ready" and document.embedding_status == "Ready":
        return {"queued": False, "status": "Ready"}
    queued = enqueue(db, document.id, retry=True)
    db.commit()
    return {"queued": queued, "status": "Pending" if queued else "Running"}


def _sign_upload_session(payload: dict) -> str:
    secret = os.environ.get("DIRECT_UPLOAD_SIGNING_SECRET") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Upload-Signierung ist nicht konfiguriert")
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _verify_upload_session(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        secret = os.environ.get("DIRECT_UPLOAD_SIGNING_SECRET") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["expires"]) < time.time():
            raise ValueError("Expired")
        if not str(payload["path"]).startswith("documents/direct/"):
            raise ValueError("Invalid path")
        return payload
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail="Upload-Sitzung ungültig oder abgelaufen") from exc


@router.post("/documents/upload-init")
def initialize_direct_upload(
    request: UploadInitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    if Path(request.filename).suffix.lower() not in DIRECT_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Erlaubt: PDF, DOCX, XLSX, EML, MSG")
    if request.case_id is not None:
        require_case_edit(db, current_user, request.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Fallzuordnung erforderlich")
    if request.batch_item_id is not None:
        item = _owned_batch_item(db, current_user, request.batch_item_id)
        if item.document_id is not None:
            raise HTTPException(status_code=409, detail="Datei bereits im Batch gespeichert")
        if item.filename != Path(request.filename).name:
            raise HTTPException(status_code=409, detail="Dateiname stimmt nicht mit dem Batch überein")
        batch = db.get(models.DocumentUploadBatch, item.batch_id)
        if batch.case_id != request.case_id:
            raise HTTPException(status_code=409, detail="Fallzuordnung stimmt nicht mit dem Batch überein")
    filename = Path(request.filename).name
    path = f"documents/direct/{uuid4().hex}_{_safe_storage_filename(filename)}"
    payload = {
        "path": path,
        "filename": filename,
        "size": request.file_size,
        "content_type": request.content_type,
        "case_id": request.case_id,
        "description": request.description,
        "user_id": current_user.id,
        "batch_item_id": request.batch_item_id,
        "expires": int(time.time()) + DIRECT_UPLOAD_TTL_SECONDS,
    }
    try:
        url = create_signed_upload_url(path)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"upload_url": url, "upload_token": _sign_upload_session(payload)}


@router.post("/documents/upload-complete", response_model=schemas.DocumentResponse, status_code=201)
def complete_direct_upload(
    request: UploadCompleteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    payload = _verify_upload_session(request.upload_token)
    if payload["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Upload gehört einem anderen Benutzer")
    case_id = payload["case_id"]
    if case_id is not None:
        require_case_edit(db, current_user, case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Fallzuordnung erforderlich")
    batch_item = None
    if payload.get("batch_item_id"):
        batch_item = _owned_batch_item(db, current_user, payload["batch_item_id"])
        if batch_item.filename != payload["filename"]:
            raise HTTPException(status_code=409, detail="Batch-Dateiname stimmt nicht überein")
    existing = db.query(models.Document).filter(models.Document.storage_path == payload["path"]).first()
    if existing:
        if existing.embedding_status != "Ready":
            enqueue(db, existing.id)
            db.commit()
        if batch_item:
            if batch_item.document_id not in (None, existing.id):
                raise HTTPException(status_code=409, detail="Batch-Eintrag bereits belegt")
            batch_item.document_id = existing.id
            batch_item.upload_status = "Uploaded"
            batch_item.upload_error = None
            db.commit()
        existing.case = _get_case_or_404(case_id, db) if case_id is not None else None
        return _serialize_document(existing)
    try:
        actual_size = get_object_size(payload["path"])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if actual_size is None:
        raise HTTPException(status_code=409, detail="Datei wurde noch nicht in Supabase gespeichert")
    if actual_size != payload["size"]:
        raise HTTPException(status_code=409, detail="Dateigröße stimmt nicht mit dem Upload überein")
    document = models.Document(
        case_id=case_id,
        file_name=payload["filename"],
        storage_path=payload["path"],
        content_type=payload["content_type"],
        file_size=actual_size,
        description=(payload["description"] or "").strip() or None,
        uploaded_by=current_user.full_name,
    )
    if batch_item and batch_item.document_id is not None:
        raise HTTPException(status_code=409, detail="Batch-Eintrag bereits belegt")
    db.add(document)
    try:
        db.flush()
        if batch_item:
            batch_item.document_id = document.id
            batch_item.upload_status = "Uploaded"
            batch_item.upload_error = None
        db.commit()
        db.refresh(document)
        enqueue(db, document.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if case_id is not None:
        document.case = _get_case_or_404(case_id, db)
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
    if case_id is not None:
        require_case_edit(db, current_user, case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(
            status_code=403,
            detail=(
                "Dokumente ohne Fallzuordnung dürfen nur von globalen Rollen "
                "hochgeladen werden."
            ),
        )
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
    _get_case_or_404(case_id, db)
    require_case_edit(db, current_user, case_id)
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
def list_all_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Document)
    if not has_global_case_access(current_user):
        query = query.filter(models.Document.case_id.isnot(None))

    documents = (
        query
        .options(joinedload(models.Document.case))
        .order_by(models.Document.uploaded_at.desc())
        .all()
    )
    return [_serialize_document(document) for document in documents]


@router.get(
    "/cases/{case_id}/documents",
    response_model=list[schemas.DocumentResponse],
)
def list_case_documents(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_case_or_404(case_id, db)
    require_case_view(db, current_user, case_id)
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
    current_user: models.User = Depends(require_editor),
):
    document = _get_document_or_404(document_id, db)

    previous_case_id = document.case_id
    if document.case_id is not None:
        require_case_edit(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")
    if payload.case_id is None and not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Entfernen der Fallzuordnung")
    if payload.case_id is not None:
        require_case_edit(db, current_user, payload.case_id)
        document.case = _get_case_or_404(payload.case_id, db)
        document.case_id = payload.case_id
    else:
        document.case = None
        document.case_id = None

    if previous_case_id != document.case_id:
        _record_case_route_event(
            db, document_id=document.id, actor_id=current_user.id,
            event_type="correction", decision="manual_reassignment",
            assigned_case_id=document.case_id,
            reason="Manuelle Änderung der Fallzuordnung",
            details={"previous_case_id": previous_case_id, "new_case_id": document.case_id},
        )
    db.commit()
    db.refresh(document)

    if document.case_id is not None:
        document.case = _get_case_or_404(document.case_id, db)

    return _serialize_document(document)



@router.post("/documents/{document_id}/queue", status_code=202)
def queue_document_processing(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    document = _get_document_or_404(document_id, db)
    if document.case_id is not None:
        require_case_edit(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")
    if document.embedding_status == "Ready" and document.processing_status == "Ready":
        return {"status": "Ready", "queued": False}
    queued = enqueue(db, document_id, retry=True)
    db.commit()
    return {"status": "Pending" if queued else "Running", "queued": queued}


@router.post("/documents/queue-pending", status_code=202)
def queue_pending_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_manager),
):
    documents = db.query(models.Document).filter(
        (models.Document.processing_status != "Ready") |
        (models.Document.embedding_status != "Ready")
    ).all()
    count = 0
    for document in documents:
        if document.case_id is not None:
            try:
                require_case_edit(db, current_user, document.case_id)
            except HTTPException:
                continue
        if enqueue(db, document.id):
            count += 1
    db.commit()
    return {"queued": count}

@router.post(
    "/documents/{document_id}/process",
    response_model=schemas.DocumentProcessingResponse,
)
def process_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    document = _get_document_or_404(document_id, db)
    if document.case_id is not None:
        require_case_edit(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")
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


def _record_case_route_event(db, *, document_id: int, actor_id: int, event_type: str,
                             decision: str, suggested_case_id=None, assigned_case_id=None,
                             confidence=None, reason=None, details=None):
    """Persist an auditable routing event in the caller's transaction."""
    db.add(models.DocumentCaseRoutingEvent(
        id=str(uuid4()), document_id=document_id, actor_id=actor_id,
        event_type=event_type, decision=decision,
        suggested_case_id=suggested_case_id, assigned_case_id=assigned_case_id,
        confidence=confidence, reason=reason,
        details=json.dumps(details, ensure_ascii=False, default=str) if details is not None else None,
    ))


@router.get("/documents/{document_id}/case-routing-history")
def get_document_case_routing_history(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(document_id, db)
    if document.case_id is not None:
        require_case_view(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")
    events = (db.query(models.DocumentCaseRoutingEvent)
              .filter_by(document_id=document_id)
              .order_by(models.DocumentCaseRoutingEvent.created_at.desc())
              .limit(100).all())
    return [{
        "id": e.id, "document_id": e.document_id, "event_type": e.event_type,
        "decision": e.decision, "suggested_case_id": e.suggested_case_id,
        "assigned_case_id": e.assigned_case_id, "confidence": e.confidence,
        "reason": e.reason, "details": json.loads(e.details) if e.details else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    } for e in events]


@router.post(
    "/documents/{document_id}/suggest-case",
    response_model=schemas.DocumentCaseRouteSuggestionResponse,
)
def suggest_case_for_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    """Suggest an existing case or a new case without changing case assignment.

    Vector search is used only to retrieve plausible candidates. OpenAI compares
    the document with those candidates. The result is a suggestion; the user
    must confirm the final assignment or new-case creation separately.
    """
    document = _get_document_or_404(document_id, db)
    if document.case_id is not None:
        require_case_edit(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")

    if document.embedding_status != "Ready":
        try:
            index_document(document=document, db=db)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    chunks = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.document_id == document.id)
        .order_by(models.DocumentChunk.chunk_index)
        .all()
    )
    if not chunks:
        raise HTTPException(
            status_code=409,
            detail="Für dieses Dokument wurden keine Textabschnitte erstellt.",
        )

    document_text = "\n\n".join(chunk.content for chunk in chunks)
    query_vector = create_query_embedding(document_text[:24000])
    vector_candidates = match_cases(
        db=db,
        user=current_user,
        query_embedding=query_vector,
        limit=5,
    )

    candidates: list[CaseCandidate] = []
    for item in vector_candidates:
        case = _get_case_or_404(int(item["case_id"]), db)
        candidates.append(
            CaseCandidate(
                case_id=case.id,
                title=case.title,
                company=case.company,
                category=case.category,
                description=case.description,
                management_summary=case.management_summary,
                similarity=float(item["similarity"]),
            )
        )

    try:
        suggestion = suggest_document_case_route(
            document_context=document_text[:50000],
            candidates=candidates,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _record_case_route_event(
        db, document_id=document.id, actor_id=current_user.id,
        event_type="suggestion", decision=suggestion.decision,
        suggested_case_id=suggestion.suggested_case_id,
        confidence=suggestion.confidence, reason=suggestion.reason,
        details={
            "candidates": [item.model_dump() for item in candidates],
            "new_case": suggestion.new_case.model_dump(mode="json") if suggestion.new_case else None,
        },
    )
    db.commit()

    return schemas.DocumentCaseRouteSuggestionResponse(
        document_id=document.id,
        decision=suggestion.decision,
        suggested_case_id=suggestion.suggested_case_id,
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        new_case=(
            schemas.DocumentCaseDraftResponse(**suggestion.new_case.model_dump())
            if suggestion.new_case
            else None
        ),
        candidates=[
            schemas.DocumentCaseCandidateResponse(
                case_id=item.case_id,
                title=item.title,
                company=item.company,
                category=item.category,
                similarity=item.similarity,
            )
            for item in candidates
        ],
    )


@router.post(
    "/documents/{document_id}/confirm-case-route",
    response_model=schemas.DocumentCaseRouteConfirmationResponse,
)
def confirm_document_case_route(
    document_id: int,
    payload: schemas.DocumentCaseRouteConfirmation,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    """Apply a case routing decision only after explicit user confirmation."""
    document = _get_document_or_404(document_id, db)
    if document.case_id is not None:
        require_case_edit(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")

    if payload.action == "assign_existing":
        if payload.case_id is None:
            raise HTTPException(status_code=400, detail="Eine Fall-ID ist erforderlich.")

        case = _get_case_or_404(payload.case_id, db)
        require_case_edit(db, current_user, case.id)
        document.case_id = case.id
        db.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == document.id
        ).update({"case_id": case.id}, synchronize_session=False)
        db.add(
            models.History(
                case_id=case.id,
                change="Dokument einem Fall zugeordnet",
                note=(
                    f"Das Dokument „{document.file_name}“ wurde nach "
                    "Benutzerbestätigung diesem Fall zugeordnet."
                ),
                responsible_person=current_user.full_name,
            )
        )
        _record_case_route_event(
            db, document_id=document.id, actor_id=current_user.id,
            event_type="confirmation", decision="assign_existing",
            assigned_case_id=case.id,
            reason="Manuell bestätigte Zuordnung zu bestehendem Fall",
        )
        db.commit()
        return schemas.DocumentCaseRouteConfirmationResponse(
            document_id=document.id,
            case_id=case.id,
            action="assigned_existing",
            message="Das Dokument wurde dem bestätigten Fall zugeordnet.",
        )

    if payload.action != "create_new":
        raise HTTPException(status_code=400, detail="Ungültige Routing-Aktion.")
    if payload.new_case is None:
        raise HTTPException(
            status_code=400,
            detail="Für einen neuen Fall ist der bestätigte Fallentwurf erforderlich.",
        )

    draft = payload.new_case
    new_case = models.Case(
        title=draft.title.strip(),
        company=(draft.company or "").strip() or None,
        department=(draft.department or "").strip() or None,
        category=draft.category.value,
        external_contact=(draft.external_contact or "").strip() or None,
        responsible_person=current_user.full_name,
        status="New",
        risk="Low",
        management_summary=(draft.management_summary or "").strip() or None,
        financial_amount=draft.financial_amount,
        description=(draft.description or "").strip() or None,
        next_action=(draft.next_action or "").strip() or None,
        primary_deadline=draft.primary_deadline,
    )

    try:
        db.add(new_case)
        db.flush()

        ensure_responsible_access(
            db,
            case_id=new_case.id,
            responsible_person=new_case.responsible_person,
        )

        refresh_risk_suggestion(new_case)
        document.case_id = new_case.id
        db.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == document.id
        ).update({"case_id": new_case.id}, synchronize_session=False)
        db.add(
            models.History(
                case_id=new_case.id,
                change="Fall aus Dokument angelegt",
                note=(
                    f"Quelle: {document.file_name}\n"
                    "• KI-Fallentwurf vom Benutzer bestätigt\n"
                    "• Dokument dem neu angelegten Fall zugeordnet"
                ),
                responsible_person=current_user.full_name,
            )
        )
        _record_case_route_event(
            db, document_id=document.id, actor_id=current_user.id,
            event_type="confirmation", decision="create_new",
            assigned_case_id=new_case.id,
            reason="Manuell bestätigter neuer Fall",
        )
        db.commit()
        db.refresh(new_case)
    except Exception:
        db.rollback()
        raise

    try:
        refresh_case_embedding(case=new_case, db=db)
    except Exception:
        db.rollback()

    return schemas.DocumentCaseRouteConfirmationResponse(
        document_id=document.id,
        case_id=new_case.id,
        action="created_new",
        message="Der bestätigte Fall wurde angelegt und das Dokument zugeordnet.",
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


def _preview_html(file_name: str, content: bytes) -> str:
    """Render supported Office files as escaped, read-only HTML."""
    extension = Path(file_name).suffix.lower()
    body: list[str] = []
    if extension == ".docx":
        document = WordDocument(BytesIO(content))
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                body.append(f"<p>{escape(paragraph.text)}</p>")
        for table in document.tables:
            body.append("<table>")
            for row in table.rows:
                body.append("<tr>" + "".join(f"<td>{escape(cell.text)}</td>" for cell in row.cells) + "</tr>")
            body.append("</table>")
    elif extension == ".xlsx":
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            for sheet in workbook.worksheets:
                body.append(f"<h2>{escape(sheet.title)}</h2><table>")
                for row in sheet.iter_rows():
                    body.append("<tr>" + "".join(
                        f"<td>{escape(str(cell.value)) if cell.value is not None else ''}</td>"
                        for cell in row
                    ) + "</tr>")
                body.append("</table>")
        finally:
            workbook.close()
    else:
        raise ValueError("Für diesen Dateityp ist keine Vorschau verfügbar")
    title = escape(file_name)
    return ("<!doctype html><html lang='de'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>body{{font:16px system-ui,sans-serif;max-width:1100px;"
            "margin:36px auto;padding:0 20px;line-height:1.6;color:#172033}}"
            "table{border-collapse:collapse;display:block;overflow-x:auto;margin:20px 0}"
            "td{border:1px solid #ccd4df;padding:6px 10px;white-space:pre-wrap}"
            "p{white-space:pre-wrap}</style></head><body>"
            f"<h1>{title}</h1>" + "".join(body) + "</body></html>")


@router.get("/documents/{document_id}/preview")
def preview_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(document_id, db)
    if document.case_id is not None:
        require_case_view(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")

    extension = Path(document.file_name).suffix.lower()
    if extension not in {".pdf", ".docx", ".xlsx"}:
        raise HTTPException(status_code=415, detail="Vorschau für diesen Dateityp nicht verfügbar")
    try:
        content = download_object(document.storage_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Dokument konnte nicht geladen werden") from exc
    if extension == ".pdf":
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    try:
        preview = _preview_html(document.file_name, content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Dokumentvorschau konnte nicht erstellt werden") from exc
    return HTMLResponse(
        content=preview,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        },
    )


@router.get(
    "/documents/{document_id}/download",
    response_model=schemas.DocumentDownloadResponse,
)
def get_document_download_url(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(document_id, db)
    if document.case_id is not None:
        require_case_view(db, current_user, document.case_id)
    elif not has_global_case_access(current_user):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf dieses Dokument")

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