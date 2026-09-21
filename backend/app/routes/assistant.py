from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.services.case_access import require_case_view
from app.services.ai_audit import (
    create_ai_query_log,
    mark_ai_query_completed,
    mark_ai_query_failed,
    record_ai_query_sources,
)
from app.services.openai_client import analysis_model
from app.services.case_work_status import build_case_work_status
from app.services.case_qa import (
    CASE_ASSISTANT_PROMPT_VERSION,
    answer_case_question,
    build_sources,
    public_sources,
    retrieve_case_evidence,
    build_task_request_text,
)


router = APIRouter(tags=["Case Assistant"], dependencies=[Depends(get_current_user)])


@router.get(
    "/cases/{case_id}/assistant/work-status",
    response_model=schemas.AssistantCaseWorkStatus,
)
def get_case_work_status(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Step 12 is structured workflow data, not generative AI. Enforce the same
    # case permission before reading the case or its tasks.
    require_case_view(db, current_user, case_id)

    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden")

    tasks = (
        db.query(models.Task)
        .filter(models.Task.case_id == case_id)
        .order_by(models.Task.due_date.asc(), models.Task.created_at.desc())
        .all()
    )
    return build_case_work_status(case=case, tasks=tasks)


@router.post(
    "/cases/{case_id}/assistant/query",
    response_model=schemas.CaseAssistantResponse,
)
def query_case_assistant(
    case_id: int,
    payload: schemas.CaseAssistantQueryRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_case_view(db, current_user, case_id)

    case_exists = db.query(models.Case.id).filter(models.Case.id == case_id).first()
    if case_exists is None:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden")

    if payload.task_type in {"brief_evidence", "brief_outline", "brief_draft", "brief_review"} and payload.brief_context is None:
        raise HTTPException(
            status_code=422,
            detail="Für die Schriftsatzvorbereitung werden Mandant/Partei und Ziel benötigt.",
        )

    audit_request_text = build_task_request_text(
        question=payload.question,
        task_type=payload.task_type,
        brief_context=payload.brief_context,
    )

    # Manager requirement: every AI request must be auditable. Persist the
    # request before retrieval starts. If this fails, do not continue to RAG or
    # OpenAI, otherwise an unlogged AI request could occur.
    try:
        audit_query = create_ai_query_log(
            db=db,
            user_id=current_user.id,
            case_id=case_id,
            task_type=payload.task_type,
            question=audit_request_text,
            model_name=analysis_model(),
            prompt_version=CASE_ASSISTANT_PROMPT_VERSION,
        )
        audit_query_id = audit_query.id
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Die KI-Anfrage konnte nicht revisionssicher protokolliert werden.",
        ) from exc

    try:
        chunks = retrieve_case_evidence(
            db=db,
            user=current_user,
            case_id=case_id,
            question=audit_request_text,
            task_type=payload.task_type,
        )
        sources = build_sources(chunks)

        # These are exactly the authorized evidence chunks that are about to be
        # supplied to the model. Commit them before the OpenAI call.
        record_ai_query_sources(
            db=db,
            query=audit_query,
            chunks=chunks,
            sources=sources,
        )

        result = answer_case_question(
            question=payload.question,
            sources=sources,
            task_type=payload.task_type,
            brief_context=payload.brief_context,
        )
        mark_ai_query_completed(db=db, query_id=audit_query_id, result=result)
    except HTTPException as exc:
        db.rollback()
        try:
            mark_ai_query_failed(db=db, query_id=audit_query_id, error=exc.detail)
        except Exception:
            db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        try:
            mark_ai_query_failed(db=db, query_id=audit_query_id, error=exc)
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"Die KI-Anfrage konnte nicht verarbeitet werden: {exc}",
        ) from exc

    return schemas.CaseAssistantResponse(
        **result.model_dump(),
        task_type=payload.task_type,
        sources=public_sources(sources),
    )
