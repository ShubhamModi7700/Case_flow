from pathlib import Path
import re
import unicodedata
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
from app.services.case_access import (
    ensure_responsible_access,
    has_global_case_access,
    require_case_edit,
    require_case_view,
)
from app.storage import (
    create_signed_url,
    delete_object,
    upload_object,
)
from app.services.document_indexing import index_document
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
        allowed_case_ids = (
            db.query(models.CaseAccess.case_id)
            .filter(models.CaseAccess.user_id == current_user.id)
        )
        query = query.filter(models.Document.case_id.in_(allowed_case_ids))

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

    if document.case_id is not None:
        require_case_edit(db, current_user, document.case_id)
    if payload.case_id is not None:
        require_case_edit(db, current_user, payload.case_id)
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