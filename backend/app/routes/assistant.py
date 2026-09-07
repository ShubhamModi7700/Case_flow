from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.services.case_access import require_case_view
from app.services.case_qa import (
    answer_case_question,
    build_sources,
    public_sources,
    retrieve_case_evidence,
)


router = APIRouter(tags=["Case Assistant"], dependencies=[Depends(get_current_user)])


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

    try:
        chunks = retrieve_case_evidence(
            db=db,
            user=current_user,
            case_id=case_id,
            question=payload.question,
        )
        sources = build_sources(chunks)
        result = answer_case_question(question=payload.question, sources=sources)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Die KI-Anfrage konnte nicht verarbeitet werden: {exc}",
        ) from exc

    return schemas.CaseAssistantResponse(
        **result.model_dump(),
        sources=public_sources(sources),
    )
