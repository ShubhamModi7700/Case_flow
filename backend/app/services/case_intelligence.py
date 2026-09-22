from __future__ import annotations

from sqlalchemy.orm import Session

from app import models, schemas
from app.services.ai_audit import create_ai_query_log, mark_ai_query_completed, mark_ai_query_failed, record_ai_query_sources
from app.services.case_qa import CASE_ASSISTANT_PROMPT_VERSION, answer_case_question, build_sources, public_sources, retrieve_case_evidence
from app.services.case_work_status import build_case_work_status
from app.services.openai_client import analysis_model

INTELLIGENCE_REQUEST = (
    "Erstelle eine konsolidierte Fall-Intelligence-Übersicht mit Schlüsseltatsachen, "
    "Chronologie, Beteiligten und Rollen, Beweiszuordnung, Widersprüchen, "
    "Informationslücken und offenen Tatsachen-/Prüffragen."
)

def build_case_intelligence(*, db: Session, user: models.User, case: models.Case) -> schemas.AssistantCaseIntelligenceResponse:
    query = create_ai_query_log(db=db, user_id=user.id, case_id=case.id, task_type="intelligence",
                                question=INTELLIGENCE_REQUEST, model_name=analysis_model(),
                                prompt_version=CASE_ASSISTANT_PROMPT_VERSION)
    try:
        chunks = retrieve_case_evidence(db=db, user=user, case_id=case.id, question=INTELLIGENCE_REQUEST, task_type="intelligence")
        sources = build_sources(chunks)
        record_ai_query_sources(db=db, query=query, chunks=chunks, sources=sources)
        result = answer_case_question(question=INTELLIGENCE_REQUEST, sources=sources, task_type="intelligence")
        mark_ai_query_completed(db=db, query_id=query.id, result=result)
        tasks = db.query(models.Task).filter(models.Task.case_id == case.id).order_by(models.Task.due_date.asc(), models.Task.created_at.desc()).all()
        work_status = build_case_work_status(case=case, tasks=tasks)
        intelligence = result.intelligence or schemas.AssistantCaseIntelligence(
            information_gaps=["Aus den freigegebenen Dokumenten konnte keine strukturierte Fall-Intelligence erzeugt werden."]
        )
        return schemas.AssistantCaseIntelligenceResponse(intelligence=intelligence, work_status=work_status, sources=public_sources(sources))
    except Exception as exc:
        db.rollback()
        try:
            mark_ai_query_failed(db=db, query_id=query.id, error=exc)
        except Exception:
            db.rollback()
        raise
