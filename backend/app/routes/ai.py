from copy import copy
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, require_editor
from app.database import get_db
from app.models import utc_now
from app.services.ai_analysis import analyze_document_context
from app.services.case_embeddings import refresh_case_embedding
from app.services.embeddings import create_query_embedding
from app.services.management_summary import generate_management_summary
from app.services.openai_client import analysis_model
from app.services.risk import calculate_case_risk
from app.services.retrieval import match_cases, retrieve_chunks

router = APIRouter(tags=["AI"], dependencies=[Depends(get_current_user)])


TECHNICAL_HISTORY_CHANGES = {
    "KI-Management-Zusammenfassung bestätigt",
    "KI-Vorschläge bestätigt",
    "KI-Zusammenfassung erstellt",
    "KI-Analyse erstellt",
}


def _is_meaningful_history(item: models.History) -> bool:
    change = (item.change or "").strip()
    if change in TECHNICAL_HISTORY_CHANGES:
        return False
    lowered = change.casefold()
    return not lowered.startswith("ki-")


def _document(document_id: int, db: Session) -> models.Document:
    value = db.query(models.Document).filter(models.Document.id == document_id).first()
    if value is None:
        raise HTTPException(404, "Dokument nicht gefunden")
    return value


def _case(case_id: int, db: Session) -> models.Case:
    value = db.query(models.Case).filter(models.Case.id == case_id).first()
    if value is None:
        raise HTTPException(404, "Fall nicht gefunden")
    return value


def _build_context(
    document: models.Document,
    case: models.Case | None,
    chunks: list[dict],
    candidates: list[dict],
) -> str:
    sections = [
        f"NEUES DOKUMENT\nDokument-ID: {document.id}\nDateiname: {document.file_name}"
    ]

    if case:
        sections.append(
            "AKTUELLER FALL\n"
            f"Fall-ID: {case.id}\nTitel: {case.title}\nUnternehmen: {case.company}\n"
            f"Kategorie: {case.category}\nStatus: {case.status}\nRisiko: {case.risk}\n"
            f"Risikobegründung: {case.risk_reason or 'Nicht angegeben'}\n"
            f"Nächste Maßnahme: {case.next_action or 'Nicht angegeben'}\n"
            f"Frist: {case.primary_deadline or 'Nicht angegeben'}\n"
            f"Verantwortlich: {case.responsible_person or 'Nicht angegeben'}\n"
            f"Management-Zusammenfassung: {case.management_summary or 'Nicht angegeben'}"
        )

    if candidates:
        sections.append(
            "MÖGLICHE FÄLLE\n"
            + "\n".join(
                f"Fall-ID {item['case_id']}: Ähnlichkeit {float(item['similarity']):.3f}"
                for item in candidates
            )
        )

    for index, chunk in enumerate(chunks, 1):
        sections.append(
            f"QUELLE {index}\nChunk-ID: {chunk['chunk_id']}\n"
            f"Dokument-ID: {chunk['document_id']}\nSeite: {chunk.get('page_number')}\n"
            f"Inhalt:\n{chunk['content']}"
        )

    return "\n\n---\n\n".join(sections)


def _build_management_context(
    case: models.Case,
    tasks: list[models.Task],
    history: list[models.History],
    documents: list[models.Document],
    chunks: list[dict],
) -> str:
    sections = [
        (
            "FALLDATEN\n"
            f"Fall-ID: {case.id}\n"
            f"Titel: {case.title}\n"
            f"Unternehmen: {case.company}\n"
            f"Abteilung: {case.department or 'Nicht angegeben'}\n"
            f"Kategorie: {case.category}\n"
            f"Status: {case.status}\n"
            f"Risiko: {case.risk}\n"
            f"Risikobegründung: {case.risk_reason or 'Nicht angegeben'}\n"
            f"Nächste Maßnahme: {case.next_action or 'Nicht angegeben'}\n"
            f"Frist: {case.primary_deadline or 'Nicht angegeben'}\n"
            f"Nächste Prüfung: {case.follow_up_date or 'Nicht angegeben'}\n"
            f"Verantwortlich: {case.responsible_person or 'Nicht angegeben'}\n"
            f"Beschreibung: {case.description or 'Nicht angegeben'}\n"
            f"Bisherige Management-Zusammenfassung: "
            f"{case.management_summary or 'Nicht angegeben'}"
        )
    ]

    if tasks:
        sections.append(
            "AUFGABEN\n"
            + "\n".join(
                f"- {task.title}; Status: {task.status}; "
                f"Priorität: {task.priority}; Frist: {task.due_date or 'Keine'}; "
                f"Verantwortlich: {task.responsible_person or 'Nicht angegeben'}"
                for task in tasks
            )
        )

    if history:
        sections.append(
            "FACHLICHE VERLAUFSEREIGNISSE\n"
            + "\n".join(
                f"- {item.created_at.date().isoformat()}: {item.change}; "
                f"{item.note or ''}"
                for item in history
            )
        )

    if documents:
        sections.append(
            "DOKUMENTE DES FALLS\n"
            + "\n".join(
                f"- Dokument-ID {document.id}; Dateiname: {document.file_name}; "
                f"Hochgeladen am: {document.uploaded_at.isoformat()}; "
                f"Beschreibung: {document.description or 'Nicht angegeben'}; "
                f"Verarbeitungsstatus: {document.processing_status}"
                for document in documents
            )
        )

    for index, chunk in enumerate(chunks, start=1):
        document = next(
            (item for item in documents if item.id == chunk["document_id"]),
            None,
        )
        file_name = document.file_name if document else "Unbekannt"
        sections.append(
            f"QUELLE {index}\n"
            f"Chunk-ID: {chunk['chunk_id']}\n"
            f"Dokument-ID: {chunk['document_id']}\n"
            f"Dateiname: {file_name}\n"
            f"Seite: {chunk.get('page_number')}\n"
            f"Inhalt:\n{chunk['content']}"
        )

    return "\n\n---\n\n".join(sections)


@router.post(
    "/documents/{document_id}/analyze",
    response_model=schemas.AISuggestionResponse,
)
def analyze_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    document = _document(document_id, db)
    if document.embedding_status != "Ready":
        raise HTTPException(
            409,
            "Das Dokument muss zuerst verarbeitet und indexiert werden.",
        )

    own_chunks = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.document_id == document.id)
        .order_by(models.DocumentChunk.chunk_index)
        .all()
    )
    if not own_chunks:
        raise HTTPException(
            409,
            "Für dieses Dokument sind keine Textabschnitte vorhanden.",
        )

    document_text = "\n\n".join(chunk.content for chunk in own_chunks[:12])
    query_vector = create_query_embedding(document_text[:24000])
    candidates = match_cases(db=db, query_embedding=query_vector, limit=5)
    related = retrieve_chunks(
        db=db,
        query_embedding=query_vector,
        case_id=document.case_id,
        document_id=None if document.case_id else document.id,
        limit=12,
    )

    if not related:
        related = [
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "case_id": chunk.case_id,
                "content": chunk.content,
                "page_number": chunk.page_number,
                "similarity": 1.0,
            }
            for chunk in own_chunks[:12]
        ]

    current_case = _case(document.case_id, db) if document.case_id else None
    analysis = analyze_document_context(
        _build_context(document, current_case, related, candidates)
    )

    suggested_case_id = analysis.proposed_case.case_id
    confidence = analysis.proposed_case.confidence
    if suggested_case_id is None and candidates:
        suggested_case_id = int(candidates[0]["case_id"])
        confidence = float(candidates[0]["similarity"])

    risk_case = current_case or (
        _case(suggested_case_id, db) if suggested_case_id else None
    )
    suggested_risk = "Low"
    suggested_risk_reason = "Keine ausreichenden Risikodaten erkannt."

    if risk_case:
        # Use a detached shallow copy so SQLAlchemy does not track temporary
        # AI values as real database changes.
        simulated_case = copy(risk_case)
        simulated_case.primary_deadline = (
            analysis.recognized_deadline or risk_case.primary_deadline
        )
        simulated_case.management_summary = analysis.suggested_summary
        simulated_case.next_action = (
            analysis.proposed_next_action or risk_case.next_action
        )
        if analysis.detected_financial_amount is not None:
            simulated_case.financial_amount = analysis.detected_financial_amount

        risk_result = calculate_case_risk(simulated_case)
        suggested_risk = risk_result.level
        suggested_risk_reason = risk_result.reason

    suggestion = models.AIDocumentSuggestion(
        document_id=document.id,
        current_case_id=document.case_id,
        suggested_case_id=suggested_case_id,
        case_match_confidence=confidence,
        suggested_summary=analysis.suggested_summary,
        suggested_latest_development=analysis.latest_development,
        suggested_deadline=analysis.recognized_deadline,
        deadline_source=analysis.deadline_source,
        suggested_next_action=analysis.proposed_next_action,
        suggested_risk=suggested_risk,
        suggested_risk_reason=suggested_risk_reason,
        relevant_chunk_ids=analysis.supporting_chunk_ids,
        relevant_document_ids=[
            item.document_id for item in analysis.relevant_documents
        ],
        status="Pending",
        model_name=analysis_model(),
        prompt_version="document-analysis-v1",
        raw_response=analysis.model_dump(mode="json"),
        created_by=current_user.id,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.get(
    "/cases/{case_id}/ai-suggestions",
    response_model=list[schemas.AISuggestionResponse],
)
def list_case_suggestions(case_id: int, db: Session = Depends(get_db)):
    _case(case_id, db)
    return (
        db.query(models.AIDocumentSuggestion)
        .filter(
            (models.AIDocumentSuggestion.current_case_id == case_id)
            | (models.AIDocumentSuggestion.suggested_case_id == case_id)
        )
        .order_by(models.AIDocumentSuggestion.created_at.desc())
        .all()
    )


@router.post("/ai-suggestions/{suggestion_id}/approve")
def approve_suggestion(
    suggestion_id: int,
    payload: schemas.AISuggestionApproval,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    suggestion = (
        db.query(models.AIDocumentSuggestion)
        .filter(models.AIDocumentSuggestion.id == suggestion_id)
        .first()
    )
    if suggestion is None:
        raise HTTPException(404, "KI-Vorschlag nicht gefunden")
    if suggestion.status not in {"Pending", "Outdated"}:
        raise HTTPException(409, "Dieser Vorschlag wurde bereits bearbeitet.")

    case = _case(payload.selected_case_id, db)
    document = _document(suggestion.document_id, db)
    normalized_role = (current_user.role or "").strip().title()
    if normalized_role == "Admin":
        normalized_role = "Manager"

    if payload.risk is not None and normalized_role != "Manager":
        raise HTTPException(403, "Nur Manager dürfen das Risiko bestätigen.")

    try:
        case.management_summary = payload.summary
        case.next_action = payload.next_action
        case.primary_deadline = payload.deadline

        if payload.risk is not None:
            case.risk = payload.risk.value
            case.risk_reason = payload.risk_reason
            case.risk_is_manual = True

        document.case_id = case.id
        db.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == document.id
        ).update({"case_id": case.id}, synchronize_session=False)

        suggestion.status = "EditedAndApproved"
        suggestion.reviewed_by = current_user.id
        suggestion.reviewed_at = utc_now()

        # Existing pending case summaries are now stale because approved
        # document information changes the case context.
        db.query(models.CaseAISummary).filter(
            models.CaseAISummary.case_id == case.id,
            models.CaseAISummary.status.in_(["Pending", "Approved"]),
        ).update({"status": "Outdated"}, synchronize_session=False)

        db.add(
            models.History(
                case_id=case.id,
                change="KI-Vorschläge bestätigt",
                note=(
                    f"Vorschläge aus dem Dokument '{document.file_name}' "
                    "wurden geprüft und gespeichert."
                ),
                responsible_person=current_user.full_name,
            )
        )
        db.commit()
        db.refresh(case)
    except Exception:
        db.rollback()
        raise

    # Embedding refresh is intentionally a separate operation. A failure here
    # must not undo the already approved user changes.
    try:
        refresh_case_embedding(case=case, db=db)
    except Exception:
        db.rollback()
        record = (
            db.query(models.CaseEmbedding)
            .filter(models.CaseEmbedding.case_id == case.id)
            .first()
        )
        if record is not None:
            db.delete(record)
            db.commit()

    return {"status": "approved", "case_id": case.id}


@router.post("/ai-suggestions/{suggestion_id}/reject")
def reject_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    suggestion = (
        db.query(models.AIDocumentSuggestion)
        .filter(models.AIDocumentSuggestion.id == suggestion_id)
        .first()
    )
    if suggestion is None:
        raise HTTPException(404, "KI-Vorschlag nicht gefunden")

    suggestion.status = "Rejected"
    suggestion.reviewed_by = current_user.id
    suggestion.reviewed_at = utc_now()
    db.commit()
    return {"status": "rejected"}


@router.post(
    "/cases/{case_id}/management-summary",
    response_model=schemas.CaseAISummaryResponse,
)
def create_management_summary(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    case = _case(case_id, db)

    tasks = (
        db.query(models.Task)
        .filter(models.Task.case_id == case.id)
        .order_by(models.Task.due_date.asc().nullslast(), models.Task.id.desc())
        .all()
    )
    history_candidates = (
        db.query(models.History)
        .filter(models.History.case_id == case.id)
        .order_by(models.History.created_at.desc())
        .limit(40)
        .all()
    )
    history = [
        item for item in history_candidates if _is_meaningful_history(item)
    ][:12]

    documents = (
        db.query(models.Document)
        .filter(models.Document.case_id == case.id)
        .order_by(models.Document.uploaded_at.desc(), models.Document.id.desc())
        .all()
    )

    query_text = (
        f"Fall {case.title}: aktueller Stand, letzte Entwicklung, nächste "
        "erforderliche Maßnahme, wichtigste offene Frist, Risikohinweis "
        "und relevante Dokumente"
    )
    query_embedding = create_query_embedding(query_text)
    chunks = retrieve_chunks(
        db=db,
        query_embedding=query_embedding,
        case_id=case.id,
        document_id=None,
        threshold=0.45,
        limit=15,
    )

    context = _build_management_context(
        case=case,
        tasks=tasks,
        history=history,
        documents=documents,
        chunks=chunks,
    )
    result = generate_management_summary(context)

    valid_document_ids = {document.id for document in documents}
    relevant_document_ids = [
        item.document_id
        for item in result.relevant_documents
        if item.document_id in valid_document_ids
    ]
    if not relevant_document_ids:
        relevant_document_ids = list(
            dict.fromkeys(
                int(chunk["document_id"])
                for chunk in chunks
                if int(chunk["document_id"]) in valid_document_ids
            )
        )[:5]

    if not result.latest_development and documents:
        newest_document = documents[0]
        result.latest_development = (
            f"Das Dokument „{newest_document.file_name}“ wurde am "
            f"{newest_document.uploaded_at.date().strftime('%d.%m.%Y')} "
            "dem Fall zugeordnet und ist für die weitere Bearbeitung relevant."
        )

    # Keep older approved summaries for audit, but only one pending proposal.
    db.query(models.CaseAISummary).filter(
        models.CaseAISummary.case_id == case.id,
        models.CaseAISummary.status == "Pending",
    ).update({"status": "Outdated"}, synchronize_session=False)

    summary = models.CaseAISummary(
        case_id=case.id,
        short_case_summary=result.short_case_summary,
        latest_development=result.latest_development,
        next_required_action=result.next_required_action,
        open_deadline=result.open_deadline,
        deadline_comment=result.deadline_comment,
        suggested_risk=case.suggested_risk or case.risk,
        risk_comment=result.risk_comment,
        relevant_document_ids=relevant_document_ids,
        relevant_chunk_ids=result.supporting_chunk_ids,
        status="Pending",
        model_name=analysis_model(),
        prompt_version="management-summary-v2",
        generated_by=current_user.id,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


@router.get(
    "/cases/{case_id}/management-summaries",
    response_model=list[schemas.CaseAISummaryResponse],
)
def list_management_summaries(
    case_id: int,
    db: Session = Depends(get_db),
):
    _case(case_id, db)
    return (
        db.query(models.CaseAISummary)
        .filter(models.CaseAISummary.case_id == case_id)
        .order_by(models.CaseAISummary.created_at.desc())
        .all()
    )


@router.post(
    "/case-ai-summaries/{summary_id}/approve",
    response_model=schemas.CaseAISummaryResponse,
)
def approve_management_summary(
    summary_id: int,
    payload: schemas.CaseAISummaryApproval,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    summary = (
        db.query(models.CaseAISummary)
        .filter(models.CaseAISummary.id == summary_id)
        .first()
    )
    if summary is None:
        raise HTTPException(404, "KI-Management-Zusammenfassung nicht gefunden")
    if summary.status not in {"Pending", "Outdated"}:
        raise HTTPException(409, "Diese Zusammenfassung wurde bereits bearbeitet.")

    case = _case(summary.case_id, db)

    try:
        summary.short_case_summary = (
            payload.short_case_summary or summary.short_case_summary
        )
        summary.latest_development = (
            payload.latest_development or summary.latest_development
        )
        summary.next_required_action = (
            payload.next_required_action or summary.next_required_action
        )
        summary.open_deadline = payload.open_deadline or summary.open_deadline
        summary.deadline_comment = (
            payload.deadline_comment or summary.deadline_comment
        )
        summary.risk_comment = payload.risk_comment or summary.risk_comment
        if payload.relevant_document_ids:
            summary.relevant_document_ids = payload.relevant_document_ids

        case.management_summary = summary.short_case_summary

        # Only Managers may change the official deadline or next action.
        normalized_role = (current_user.role or "").strip().title()
        if normalized_role == "Admin":
            normalized_role = "Manager"
        if normalized_role == "Manager":
            if summary.next_required_action:
                case.next_action = summary.next_required_action
            if summary.open_deadline:
                case.primary_deadline = summary.open_deadline

        db.query(models.CaseAISummary).filter(
            models.CaseAISummary.case_id == case.id,
            models.CaseAISummary.id != summary.id,
            models.CaseAISummary.status == "Approved",
        ).update({"status": "Outdated"}, synchronize_session=False)

        summary.status = "Approved"
        summary.reviewed_by = current_user.id
        summary.reviewed_at = utc_now()

        db.add(
            models.History(
                case_id=case.id,
                change="KI-Management Zusammenfassung bestätigt",
                note="Die KI-Zusammenfassung wurde geprüft und übernommen.",
                responsible_person=current_user.full_name,
            )
        )
        db.commit()
        db.refresh(summary)
        db.refresh(case)
    except Exception:
        db.rollback()
        raise

    try:
        refresh_case_embedding(case=case, db=db)
    except Exception:
        db.rollback()

    return summary


@router.post("/case-ai-summaries/{summary_id}/reject")
def reject_management_summary(
    summary_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    summary = (
        db.query(models.CaseAISummary)
        .filter(models.CaseAISummary.id == summary_id)
        .first()
    )
    if summary is None:
        raise HTTPException(404, "KI-Management Zusammenfassung nicht gefunden")

    summary.status = "Rejected"
    summary.reviewed_by = current_user.id
    summary.reviewed_at = utc_now()
    db.commit()
    return {"status": "rejected"}
