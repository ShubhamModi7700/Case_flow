from copy import copy
from datetime import date
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.prompts.document_analysis import DOCUMENT_ANALYSIS_PROMPT_VERSION
from app.prompts.management import MANAGEMENT_PROMPT_VERSION
from app.auth import get_current_user, require_editor
from app.database import get_db
from app.services.case_access import require_case_edit, require_case_view
from app.models import utc_now
from app.services.ai_analysis import analyze_document_context
from app.services.case_embeddings import refresh_case_embedding
from app.services.embeddings import create_query_embedding
from app.services.management_summary import generate_management_summary
from app.services.openai_client import analysis_model
from app.services.risk import calculate_case_risk
from app.services.retrieval import match_cases, retrieve_chunks

router = APIRouter(tags=["AI"], dependencies=[Depends(get_current_user)])

logger = logging.getLogger(__name__)


def _normalized_role(user: models.User) -> str:
    role = (user.role or "").strip().title()
    return "Manager" if role == "Admin" else role


def _payload_risk(payload) -> schemas.RiskLevel | None:
    """Read risk defensively during rolling frontend/backend deployments.

    `risk` must still be declared on the Pydantic approval schema so FastAPI
    preserves the field from the request body. `getattr` prevents an old schema
    version from causing a 500 AttributeError while deployments overlap.
    """
    return getattr(payload, "risk", None)


def _current_state_text(*values: str | None) -> str:
    return " ".join(
        value.strip().lower()
        for value in values
        if isinstance(value, str) and value.strip()
    )


def _document_suggestion_status(
    suggestion: models.AIDocumentSuggestion | None,
) -> schemas.CaseStatus | None:
    """Read the status proposed by the newest confirmed document analysis.

    We intentionally keep this in raw_response to avoid another migration on the
    document-suggestion table. Confirmed document evidence is the source of truth
    for the current-state transition used by the management layer.
    """
    if suggestion is None or not isinstance(suggestion.raw_response, dict):
        return None

    value = suggestion.raw_response.get("suggested_status")
    if not value:
        return None

    try:
        return schemas.CaseStatus(value)
    except ValueError:
        return None


def _newest_evidence_text(
    suggestion: models.AIDocumentSuggestion | None,
) -> str:
    if suggestion is None:
        return ""

    return _current_state_text(
        suggestion.suggested_summary,
        suggestion.suggested_latest_development,
        suggestion.suggested_next_action,
        suggestion.suggested_risk_reason,
    )


def _normalize_management_current_state(
    *,
    case: models.Case,
    result: schemas.ManagementSummaryAnalysis,
    newest_confirmed: models.AIDocumentSuggestion | None = None,
) -> None:
    """Normalize risk/status from the newest confirmed evidence.

    Historical case prose is deliberately not used to decide whether an
    escalation is current. Otherwise old phrases such as "Klage", "42.000 EUR"
    or "Frist überschritten" can keep a settled case at High/Critical forever.
    """
    newest_text = _newest_evidence_text(newest_confirmed)

    resolution_terms = (
        "vergleich", "einigung", "erledigt", "beendet", "abgeschlossen",
        "streit beigelegt", "streit geregelt", "ansprüche erledigt",
    )
    live_escalation_terms = (
        "vergleichsbruch", "nicht gezahlt", "zahlung überfällig",
        "klage anhängig", "klage eingereicht", "vollstreckung",
        "neue klage", "erneute klage", "frist überschritten",
        "überfällige zahlung",
    )
    waiting_terms = (
        "abwarten", "wartet auf", "rückmeldung", "antwort ausstehend",
        "gegenpartei", "behörde",
    )
    own_action_terms = (
        "zahlen", "zahlung", "beschaffen", "prüfen", "dokumentieren",
        "unterzeichnen", "einreichen", "umsetzen", "erfüllen",
        "veranlassen", "vorbereiten",
    )

    has_resolution = any(term in newest_text for term in resolution_terms)
    has_live_escalation = any(term in newest_text for term in live_escalation_terms)
    has_open_deadline = result.open_deadline is not None
    next_action = (result.next_required_action or "").lower()

    # The newest confirmed document risk is the strongest current-state signal.
    # It may lower a stale official High risk after a later settlement.
    if newest_confirmed and newest_confirmed.suggested_risk:
        try:
            result.suggested_risk = schemas.RiskLevel(
                newest_confirmed.suggested_risk
            )
        except ValueError:
            pass

    newest_status = _document_suggestion_status(newest_confirmed)
    if newest_status is not None:
        result.suggested_status = newest_status

    if has_resolution and not has_live_escalation:
        # A settlement with a material future obligation is residual Medium risk,
        # not historical High. If no material step remains, Low is appropriate.
        if has_open_deadline or next_action:
            if result.suggested_risk == schemas.RiskLevel.HIGH:
                result.suggested_risk = schemas.RiskLevel.MEDIUM
            if not result.risk_comment:
                result.risk_comment = (
                    "Das frühere hohe Streitrisiko wurde durch die neuere "
                    "Vergleichs-/Erledigungslage wesentlich reduziert. "
                    "Ein materielles Restrisiko besteht bis zur vollständigen "
                    "Erfüllung und Dokumentation der noch offenen Verpflichtungen."
                )

            if any(term in next_action for term in waiting_terms) and not any(
                term in next_action for term in own_action_terms
            ):
                result.suggested_status = schemas.CaseStatus.WAITING
                result.status_reason = (
                    "Der Hauptstreit ist durch die neueste bestätigte Evidenz "
                    "weitgehend geregelt; der nächste materielle Schritt hängt "
                    "überwiegend von einem externen Ereignis ab."
                )
            else:
                result.suggested_status = schemas.CaseStatus.IN_PROGRESS
                result.status_reason = (
                    "Der Hauptstreit ist durch die neueste bestätigte Evidenz "
                    "weitgehend geregelt; es bestehen jedoch noch konkrete "
                    "Erfüllungs-, Zahlungs- oder Dokumentationsschritte."
                )
        else:
            result.suggested_risk = schemas.RiskLevel.LOW
            result.suggested_status = schemas.CaseStatus.COMPLETED
            result.status_reason = (
                "Die neueste bestätigte Evidenz weist auf eine materielle "
                "Erledigung ohne wesentliche offene Verpflichtungen hin."
            )

    # High/Critical may only be reintroduced by a live escalation found in the
    # newest confirmed evidence, never by historical case text.
    if has_live_escalation:
        result.suggested_risk = schemas.RiskLevel.HIGH
        if result.open_deadline is not None:
            result.suggested_status = schemas.CaseStatus.CRITICAL


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
    confirmed_suggestions: list[models.AIDocumentSuggestion] | None = None,
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

    if confirmed_suggestions:
        sections.append(
            "BISHER BESTÄTIGTE DOKUMENT-EVIDENZ\n"
            + "\n".join(
                (
                    f"- Dokument-ID {item.document_id}; "
                    f"Zusammenfassung: {item.suggested_summary or 'Nicht angegeben'}; "
                    f"Letzte Entwicklung: {item.suggested_latest_development or 'Nicht angegeben'}; "
                    f"Neue Erkenntnisse: "
                    f"{'; '.join(item.new_facts or []) or 'Keine'}; "
                    f"Nächste Maßnahme: {item.suggested_next_action or 'Nicht angegeben'}"
                )
                for item in confirmed_suggestions
            )
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
    confirmed_suggestions: list[models.AIDocumentSuggestion],
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

    if confirmed_suggestions:
        sections.append(
            "BESTÄTIGTE FAKTEN AUS DOKUMENTANALYSEN\n"
            + "\n".join(
                (
                    f"- Dokument-ID {item.document_id}; "
                    f"Zusammenfassung: {item.suggested_summary or 'Nicht angegeben'}; "
                    f"Letzte Entwicklung: {item.suggested_latest_development or 'Nicht angegeben'}; "
                    f"Vorgeschlagene Frist: {item.suggested_deadline or 'Nicht angegeben'}; "
                    f"Nächste Maßnahme: {item.suggested_next_action or 'Nicht angegeben'}; "
                    f"Risikohinweis: {item.suggested_risk or 'Nicht angegeben'}; "
                    f"Risikobegründung: {item.suggested_risk_reason or 'Nicht angegeben'}; "
                    f"Neue Erkenntnisse: "
                    f"{'; '.join(item.new_facts or []) or 'Keine'}"
                )
                for item in confirmed_suggestions
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
    candidates = match_cases(
        db=db,
        query_embedding=query_vector,
        user=current_user,
        limit=5,
    )
    related = retrieve_chunks(
        db=db,
        query_embedding=query_vector,
        case_id=document.case_id,
        document_id=None if document.case_id else document.id,
        limit=12,
    )

    # The document the user just asked us to analyse must always be present in
    # the prompt. Pure similarity retrieval can otherwise return only older case
    # documents, which makes an old demand/deadline incorrectly look current.
    own_chunk_payloads = [
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
    seen_chunk_ids = {item["chunk_id"] for item in own_chunk_payloads}
    related = own_chunk_payloads + [
        item for item in related if item["chunk_id"] not in seen_chunk_ids
    ]
    related = related[:20]

    current_case = _case(document.case_id, db) if document.case_id else None
    confirmed_context: list[models.AIDocumentSuggestion] = []
    if current_case is not None:
        confirmed_context = (
            db.query(models.AIDocumentSuggestion)
            .filter(
                models.AIDocumentSuggestion.current_case_id == current_case.id,
                models.AIDocumentSuggestion.document_id != document.id,
                models.AIDocumentSuggestion.status.in_(
                    ["Approved", "EditedAndApproved"]
                ),
            )
            .order_by(models.AIDocumentSuggestion.reviewed_at.desc().nullslast())
            .limit(8)
            .all()
        )

    analysis = analyze_document_context(
        _build_context(
            document,
            current_case,
            related,
            candidates,
            confirmed_context,
        )
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

        if analysis.suggested_risk is not None:
            suggested_risk = analysis.suggested_risk.value
            suggested_risk_reason = (
                analysis.risk_reason
                or "Aktuelles Restrisiko wurde aus der neuesten Dokumentlage abgeleitet."
            )
        else:
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
        new_facts=analysis.new_facts,
        proposed_tasks=[
            item.model_dump(mode="json") for item in analysis.proposed_tasks
        ],
        created_task_ids=[],
        status="Pending",
        model_name=analysis_model(),
        prompt_version=DOCUMENT_ANALYSIS_PROMPT_VERSION,
        raw_response=analysis.model_dump(mode="json"),
        created_by=current_user.id,
    )
    # A newer analysis for the same case supersedes older unreviewed proposals.
    # Keep them for audit/history, but do not present them as concurrently valid.
    target_case_id = document.case_id or suggested_case_id
    if target_case_id is not None:
        db.query(models.AIDocumentSuggestion).filter(
            models.AIDocumentSuggestion.status == "Pending",
            (models.AIDocumentSuggestion.current_case_id == target_case_id)
            | (models.AIDocumentSuggestion.suggested_case_id == target_case_id),
        ).update({"status": "Outdated"}, synchronize_session=False)

    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.get(
    "/cases/{case_id}/ai-suggestions",
    response_model=list[schemas.AISuggestionResponse],
)
def list_case_suggestions(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_case_view(db, current_user, case_id)
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
    normalized_role = _normalized_role(current_user)
    approved_risk = _payload_risk(payload)

    if approved_risk is not None and normalized_role != "Manager":
        raise HTTPException(403, "Nur Manager dürfen das Risiko bestätigen.")

    try:
        # Confirm the document analysis as evidence. Do not overwrite the
        # official case-level management state here; that happens only after
        # the subsequently generated management proposal is reviewed.
        suggestion.suggested_summary = payload.summary
        suggestion.suggested_latest_development = payload.latest_development
        suggestion.suggested_deadline = payload.deadline
        suggestion.suggested_next_action = payload.next_action
        if approved_risk is not None:
            suggestion.suggested_risk = approved_risk.value
            suggestion.suggested_risk_reason = payload.risk_reason

        # A Manager has explicitly reviewed and confirmed this document
        # analysis. Confirmed operational values become official immediately.
        # The generated management summary remains the place for consolidated
        # narrative, status and official risk approval.
        if normalized_role == "Manager" and case.status != "Completed":
            if payload.next_action is not None:
                case.next_action = payload.next_action.strip() or None
            if payload.deadline is not None:
                case.primary_deadline = payload.deadline

        proposed_tasks = suggestion.proposed_tasks or []
        selected_indexes = sorted(set(payload.selected_task_indexes))
        invalid_indexes = [
            index
            for index in selected_indexes
            if index < 0 or index >= len(proposed_tasks)
        ]
        if invalid_indexes:
            raise HTTPException(
                422,
                "Mindestens eine ausgewählte KI-Aufgabe ist nicht mehr verfügbar.",
            )

        created_task_ids: list[int] = []
        created_task_titles: list[str] = []
        for index in selected_indexes:
            task_payload = dict(proposed_tasks[index])
            task_payload.pop("evidence", None)
            if not task_payload.get("priority"):
                task_payload["priority"] = schemas.TaskPriority.MEDIUM.value
            task_payload["status"] = schemas.TaskStatus.OPEN.value
            validated_task = schemas.TaskCreate.model_validate(task_payload)

            duplicate = (
                db.query(models.Task)
                .filter(
                    models.Task.case_id == case.id,
                    models.Task.title == validated_task.title,
                    models.Task.status == schemas.TaskStatus.OPEN.value,
                )
                .first()
            )
            if duplicate is not None:
                continue

            task = models.Task(
                case_id=case.id,
                **validated_task.model_dump(),
            )
            db.add(task)
            db.flush()
            created_task_ids.append(task.id)
            created_task_titles.append(task.title)

        suggestion.created_task_ids = created_task_ids

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

        approved_changes = [
            f"Quelle: {document.file_name}",
            "Dokumentanalyse als bestätigte Evidenz gespeichert",
        ]
        if payload.latest_development:
            approved_changes.append(
                f"Letzte Entwicklung: {payload.latest_development}"
            )
        if payload.deadline:
            approved_changes.append(
                (
                    f"Offene Frist übernommen: {payload.deadline.strftime('%d.%m.%Y')}"
                    if normalized_role == "Manager"
                    else f"Erkannte Frist bestätigt: {payload.deadline.strftime('%d.%m.%Y')}"
                )
            )
        if payload.next_action:
            approved_changes.append(
                (
                    f"Nächste Maßnahme übernommen: {payload.next_action}"
                    if normalized_role == "Manager"
                    else f"Vorgeschlagene nächste Maßnahme bestätigt: {payload.next_action}"
                )
            )
        if approved_risk is not None:
            approved_changes.append(
                f"Risikohinweis aus Dokument bestätigt: {approved_risk.value}"
            )
            if payload.risk_reason:
                approved_changes.append(
                    f"Risikobegründung: {payload.risk_reason}"
                )
        if suggestion.new_facts:
            approved_changes.append(
                "Neue Erkenntnisse: " + "; ".join(suggestion.new_facts)
            )
        if created_task_titles:
            approved_changes.append(
                "Übernommene Aufgaben: " + "; ".join(created_task_titles)
            )
        if suggestion.current_case_id != case.id:
            approved_changes.append(
                f"Dokument dem Fall CF-{case.id:04d} zugeordnet"
            )

        db.add(
            models.History(
                case_id=case.id,
                change="KI-Dokumentanalyse bestätigt",
                note="\n".join(f"• {item}" for item in approved_changes),
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

    management_summary_created = False
    try:
        _create_management_summary_record(
            case=_case(case.id, db),
            db=db,
            user=current_user,
            generated_by=current_user.id,
        )
        management_summary_created = True
    except Exception:
        # Document approval must remain valid even if the follow-up AI call
        # temporarily fails. The user can still regenerate it manually.
        db.rollback()
        logger.exception(
            "Automatic management-summary generation failed after document approval",
            extra={"case_id": case.id, "suggestion_id": suggestion.id},
        )

    return {
        "status": "approved",
        "case_id": case.id,
        "management_summary_created": management_summary_created,
        "tasks_created": len(suggestion.created_task_ids or []),
    }


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


def _risk_rank(value: str | None) -> int:
    return {"Low": 1, "Medium": 2, "High": 3}.get(value or "", 0)


def _create_management_summary_record(
    *,
    case: models.Case,
    db: Session,
    user: models.User,
    generated_by: int | None,
) -> models.CaseAISummary:
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

    confirmed_suggestions = (
        db.query(models.AIDocumentSuggestion)
        .filter(
            (models.AIDocumentSuggestion.current_case_id == case.id)
            | (models.AIDocumentSuggestion.suggested_case_id == case.id),
            models.AIDocumentSuggestion.status.in_(["Approved", "EditedAndApproved"]),
        )
        .order_by(models.AIDocumentSuggestion.reviewed_at.desc().nullslast(), models.AIDocumentSuggestion.id.desc())
        .limit(6)
        .all()
    )

    query_text = (
        f"Fall {case.title}: aktueller Stand, letzte Entwicklung, nächste "
        "erforderliche Maßnahme, wichtigste offene Frist, Risikohinweis "
        "und relevante Dokumente"
    )
    query_embedding = create_query_embedding(query_text)

    # Management summaries do not depend on per-document ``KI analysieren``.
    # Every indexed document linked to the case is considered directly through
    # its document chunks. Retrieval remains permission-scoped before any
    # evidence can be sent to the model.
    chunks = retrieve_chunks(
        db=db,
        user=user,
        query_embedding=query_embedding,
        case_id=case.id,
        document_id=None,
        threshold=0.50,
        limit=16,
    )

    # Also retrieve a small number of candidates from each uploaded/indexed
    # document. A single global vector ranking can otherwise be dominated by one
    # long document and completely omit another case document. This does not
    # send every full document to OpenAI; it makes every indexed document part
    # of the RAG candidate set and then keeps a bounded, deduplicated context.
    per_document_chunks: list[dict] = []
    for document in documents:
        document_chunks = retrieve_chunks(
            db=db,
            user=user,
            query_embedding=query_embedding,
            case_id=case.id,
            document_id=document.id,
            threshold=0.35,
            limit=3,
        )
        per_document_chunks.extend(document_chunks)

    combined_chunks = per_document_chunks + chunks
    seen_chunk_ids: set[int] = set()
    chunks = []
    for item in combined_chunks:
        chunk_id = int(item["chunk_id"])
        if chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)
        chunks.append(item)
    chunks = chunks[:24]

    # Always include chunks from the newest case document. This prevents an old
    # but semantically similar lawyer letter from outranking a newer settlement
    # or closure document in the management summary.
    if documents:
        newest_document = documents[0]
        newest_chunks = (
            db.query(models.DocumentChunk)
            .filter(models.DocumentChunk.document_id == newest_document.id)
            .order_by(models.DocumentChunk.chunk_index.asc())
            .limit(8)
            .all()
        )
        newest_payloads = [
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "case_id": chunk.case_id,
                "content": chunk.content,
                "page_number": chunk.page_number,
                "similarity": 1.0,
            }
            for chunk in newest_chunks
        ]
        newest_ids = {item["chunk_id"] for item in newest_payloads}
        chunks = newest_payloads + [
            item for item in chunks if item["chunk_id"] not in newest_ids
        ]
        chunks = chunks[:24]

    context = _build_management_context(
        case=case,
        tasks=tasks,
        history=history,
        documents=documents,
        confirmed_suggestions=confirmed_suggestions,
        chunks=chunks,
    )
    result = generate_management_summary(context)
    _normalize_management_current_state(
        case=case,
        result=result,
        newest_confirmed=confirmed_suggestions[0] if confirmed_suggestions else None,
    )

    valid_document_ids = {document.id for document in documents}
    valid_chunk_ids = {int(chunk["chunk_id"]) for chunk in chunks}

    # Never persist source IDs that were not actually provided to the model.
    relevant_document_ids = list(
        dict.fromkeys(
            item.document_id
            for item in result.relevant_documents
            if item.document_id in valid_document_ids
        )
    )[:5]
    supporting_chunk_ids = list(
        dict.fromkeys(
            int(chunk_id)
            for chunk_id in result.supporting_chunk_ids
            if int(chunk_id) in valid_chunk_ids
        )
    )[:8]

    # If the model returned supporting chunks but omitted the document list,
    # derive documents only from those validated chunks (not from every RAG hit).
    if not relevant_document_ids and supporting_chunk_ids:
        relevant_document_ids = list(
            dict.fromkeys(
                int(chunk["document_id"])
                for chunk in chunks
                if int(chunk["chunk_id"]) in supporting_chunk_ids
                and int(chunk["document_id"]) in valid_document_ids
            )
        )[:5]

    # A management action must not be presented as evidence-grounded when the
    # model did not identify any validated supporting chunk/document. Keep the
    # generated text for human review, but make the lack of evidence explicit.
    if result.next_required_action and not supporting_chunk_ids:
        note = (
            "Für die vorgeschlagene nächste Maßnahme wurde keine konkrete "
            "bestätigte Dokumentstelle als Beleg zugeordnet. Der Vorschlag ist "
            "daher nur ein Prüfhinweis und darf nicht als belastbare "
            "Handlungsempfehlung übernommen werden."
        )
        if note not in result.uncertainty_notes:
            result.uncertainty_notes.append(note)
        result.action_justification = None
        relevant_document_ids = []

    # A deadline is allowed only when it is already represented by confirmed
    # case/task/document evidence. This prevents an unsupported date from
    # becoming a management proposal merely because the model inferred it.
    supported_deadlines = {
        value
        for value in [case.primary_deadline, case.follow_up_date]
        if value is not None
    }
    supported_deadlines.update(
        task.due_date for task in tasks if task.due_date is not None
    )
    supported_deadlines.update(
        item.suggested_deadline
        for item in confirmed_suggestions
        if item.suggested_deadline is not None
    )
    if result.open_deadline is not None and result.open_deadline not in supported_deadlines:
        result.uncertainty_notes.append(
            "Die vorgeschlagene Frist war nicht durch bestätigte strukturierte Falldaten belegt und wurde verworfen."
        )
        result.open_deadline = None
        result.deadline_comment = None

    # Do not invent a business development from the mere fact that a file was
    # uploaded. Prefer confirmed document evidence when the model cannot state
    # a grounded latest development.
    if not result.latest_development:
        for item in confirmed_suggestions:
            if item.suggested_latest_development:
                result.latest_development = item.suggested_latest_development.strip()
                break

    # A confirmed document analysis is evidence. Its risk suggestion can raise
    # the pending case-level recommendation, but never changes the official
    # case risk until a manager approves the management summary.
    # confirmed_suggestions are ordered newest-first. The newest confirmed
    # document analysis represents the current evidence and must be able to lower
    # an older risk level after settlement/closure. Falling back to the case risk
    # preserves current behaviour when no confirmed document risk exists.
    newest_confirmed_risk = next(
        (item.suggested_risk for item in confirmed_suggestions if item.suggested_risk),
        None,
    )
    suggested_risk = (
        result.suggested_risk.value
        if result.suggested_risk is not None
        else newest_confirmed_risk or case.suggested_risk or case.risk
    )

    db.query(models.CaseAISummary).filter(
        models.CaseAISummary.case_id == case.id,
        models.CaseAISummary.status == "Pending",
    ).update({"status": "Outdated"}, synchronize_session=False)

    summary = models.CaseAISummary(
        case_id=case.id,
        short_case_summary=result.short_case_summary,
        document_facts=result.document_facts,
        interpretation=result.interpretation,
        responsible_role=result.responsible_role,
        action_justification=result.action_justification,
        uncertainty_notes=result.uncertainty_notes,
        latest_development=result.latest_development,
        next_required_action=result.next_required_action,
        open_deadline=result.open_deadline,
        deadline_comment=result.deadline_comment,
        suggested_risk=suggested_risk,
        risk_comment=result.risk_comment,
        suggested_status=result.suggested_status.value,
        status_reason=result.status_reason,
        relevant_document_ids=relevant_document_ids,
        relevant_chunk_ids=supporting_chunk_ids,
        status="Pending",
        model_name=analysis_model(),
        prompt_version=MANAGEMENT_PROMPT_VERSION,
        generated_by=generated_by,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


@router.post(
    "/cases/{case_id}/management-summary",
    response_model=schemas.CaseAISummaryResponse,
)
def create_management_summary(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    require_case_edit(db, current_user, case_id)
    case = _case(case_id, db)

    try:
        return _create_management_summary_record(
            case=case,
            db=db,
            user=current_user,
            generated_by=current_user.id,
        )
    except HTTPException:
        # Preserve intentional FastAPI errors (403/404/etc.).
        db.rollback()
        raise
    except Exception as exc:
        # The management-summary flow includes retrieval, OpenAI parsing,
        # validation and persistence. Log the full traceback so deployment logs
        # show the exact failing line instead of only an HTTP 500.
        db.rollback()
        logger.exception(
            "Management-summary creation failed for case_id=%s user_id=%s",
            case_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Management-Zusammenfassung konnte nicht erstellt werden. "
                f"Debug: {type(exc).__name__}: {exc}"
            ),
        ) from exc



@router.get(
    "/cases/{case_id}/management-summaries",
    response_model=list[schemas.CaseAISummaryResponse],
)
def list_management_summaries(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),):
    require_case_view(db, current_user, case_id)
    _case(case_id, db)
    return (
        db.query(models.CaseAISummary)
        .filter(models.CaseAISummary.case_id == case_id)
        .order_by(models.CaseAISummary.created_at.desc())
        .all()
    )


@router.get(
    "/cases/{case_id}/management-summaries/latest-approved",
    response_model=schemas.CaseAISummaryResponse | None,
)
def latest_approved_management_summary(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),):
    require_case_view(db, current_user, case_id)
    """Return the latest confirmed management summary for Overview screens."""
    _case(case_id, db)
    return (
        db.query(models.CaseAISummary)
        .filter(
            models.CaseAISummary.case_id == case_id,
            models.CaseAISummary.status.in_(["Approved", "EditedAndApproved"]),
        )
        .order_by(models.CaseAISummary.reviewed_at.desc(), models.CaseAISummary.created_at.desc())
        .first()
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
        if payload.document_facts:
            summary.document_facts = payload.document_facts
        summary.interpretation = payload.interpretation or summary.interpretation
        summary.responsible_role = payload.responsible_role or summary.responsible_role
        summary.action_justification = payload.action_justification or summary.action_justification
        if payload.uncertainty_notes:
            summary.uncertainty_notes = payload.uncertainty_notes
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
        summary.status_reason = payload.status_reason or summary.status_reason
        if payload.status is not None:
            summary.suggested_status = payload.status.value
        if payload.relevant_document_ids:
            summary.relevant_document_ids = payload.relevant_document_ids

        case.management_summary = summary.short_case_summary

        # Keep the blue automatic recommendation aligned with the latest
        # approved management current-state analysis. This remains a suggestion;
        # the official risk changes only when a Manager approves it.
        if summary.suggested_risk:
            case.suggested_risk = summary.suggested_risk
            case.suggested_risk_reason = summary.risk_comment

        # Only Managers may change the official deadline or next action.
        normalized_role = _normalized_role(current_user)
        approved_risk = _payload_risk(payload)
        if approved_risk is not None and normalized_role != "Manager":
            raise HTTPException(403, "Nur Manager dürfen das Risiko bestätigen.")
        if payload.status is not None and normalized_role != "Manager":
            raise HTTPException(403, "Nur Manager dürfen den Fallstatus bestätigen.")
        if normalized_role == "Manager":
            approved_status = payload.status.value if payload.status is not None else None

            # Closing a case is authoritative current-state information. Do not
            # reintroduce an AI-generated action/deadline into a completed case.
            if approved_status == "Completed":
                case.next_action = None
                case.primary_deadline = None
                case.follow_up_date = None
            else:
                if summary.next_required_action:
                    case.next_action = summary.next_required_action
                if summary.open_deadline:
                    case.primary_deadline = summary.open_deadline

            if approved_risk is not None:
                summary.suggested_risk = approved_risk.value
                case.risk = approved_risk.value
                case.risk_reason = summary.risk_comment
                case.risk_is_manual = True
            if payload.status is not None:
                case.status = payload.status.value

        db.query(models.CaseAISummary).filter(
            models.CaseAISummary.case_id == case.id,
            models.CaseAISummary.id != summary.id,
            models.CaseAISummary.status == "Approved",
        ).update({"status": "Outdated"}, synchronize_session=False)

        summary.status = "Approved"
        summary.reviewed_by = current_user.id
        summary.reviewed_at = utc_now()

        summary_changes = [
            "Management-Zusammenfassung geprüft und veröffentlicht",
        ]
        if summary.latest_development:
            summary_changes.append(
                f"Letzte Entwicklung: {summary.latest_development}"
            )
        if normalized_role == "Manager" and summary.next_required_action:
            summary_changes.append(
                f"Nächste Maßnahme übernommen: {summary.next_required_action}"
            )
        if normalized_role == "Manager" and summary.open_deadline:
            summary_changes.append(
                f"Offene Frist übernommen: {summary.open_deadline.strftime('%d.%m.%Y')}"
            )
        if normalized_role == "Manager" and approved_risk is not None:
            summary_changes.append(
                f"Risiko übernommen: {approved_risk.value}"
            )
        if normalized_role == "Manager" and payload.status is not None:
            summary_changes.append(
                f"Status übernommen: {payload.status.value}"
            )
            if summary.status_reason:
                summary_changes.append(
                    f"Statusbegründung: {summary.status_reason}"
                )
        if summary.risk_comment:
            summary_changes.append(
                f"Risikohinweis: {summary.risk_comment}"
            )

        db.add(
            models.History(
                case_id=case.id,
                change="KI-Management-Zusammenfassung bestätigt",
                note="\n".join(f"• {item}" for item in summary_changes),
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
        logger.exception(
            "Case embedding refresh failed after management-summary approval",
            extra={"case_id": case.id, "summary_id": summary.id},
        )

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