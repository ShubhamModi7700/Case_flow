from __future__ import annotations

import logging
import time
from datetime import date
from typing import Literal

from openai import APIConnectionError, APIError, RateLimitError
from pydantic import BaseModel, Field

from app import schemas
from app.services.ai_provider import get_ai_provider
from app.services.text_cleanup import clean_required_user_facing_text, clean_user_facing_text
from app.prompts.document_routing import DRAFT_SYSTEM_PROMPT, ROUTING_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MIN_EXISTING_CASE_CONFIDENCE = 0.80


class DocumentCaseDraft(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    category: schemas.CaseCategory = schemas.CaseCategory.OTHER
    external_contact: str | None = Field(default=None, max_length=255)
    description: str | None = None
    management_summary: str | None = None
    next_action: str | None = None
    primary_deadline: date | None = None
    financial_amount: float | None = Field(default=None, ge=0)


class CaseCandidate(BaseModel):
    case_id: int
    title: str
    company: str | None = None
    category: str | None = None
    description: str | None = None
    management_summary: str | None = None
    similarity: float | None = None


class DocumentCaseRouteSuggestion(BaseModel):
    decision: Literal["existing_case", "new_case", "uncertain"]
    suggested_case_id: int | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str
    new_case: DocumentCaseDraft | None = None


def _parse_structured(*, system_prompt: str, user_content: str, text_format):
    response = None
    for attempt in range(3):
        try:
            response = get_ai_provider().structured_parse(
                                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                text_format=text_format,
            )
            break
        except RateLimitError:
            if attempt == 2:
                raise RuntimeError("OpenAI-Ratenlimit erreicht.")
            time.sleep(2**attempt)
        except APIConnectionError as exc:
            raise RuntimeError("Keine Verbindung zum OpenAI-Dienst.") from exc
        except APIError as exc:
            raise RuntimeError(f"OpenAI API Fehler: {exc}") from exc

    if response is None or response.output_parsed is None:
        raise RuntimeError("Die strukturierte KI-Antwort konnte nicht gelesen werden.")
    return response.output_parsed


def create_document_case_draft(document_context: str) -> DocumentCaseDraft:
    if not document_context.strip():
        raise ValueError("Für das Dokument stehen keine extrahierten Inhalte zur Verfügung.")

    draft = _parse_structured(
        system_prompt=DRAFT_SYSTEM_PROMPT,
        user_content=document_context,
        text_format=DocumentCaseDraft,
    )
    draft.title = clean_required_user_facing_text(draft.title, field_name="Falltitel")
    draft.company = clean_user_facing_text(draft.company)
    draft.department = clean_user_facing_text(draft.department)
    draft.external_contact = clean_user_facing_text(draft.external_contact)
    draft.description = clean_user_facing_text(draft.description)
    draft.management_summary = clean_user_facing_text(draft.management_summary)
    draft.next_action = clean_user_facing_text(draft.next_action)

    logger.info(
        "Document case draft created",
        extra={
            "model": get_ai_provider().analysis_model(),
            "context_length": len(document_context),
            "category": draft.category.value,
        },
    )
    return draft


def suggest_document_case_route(
    *, document_context: str, candidates: list[CaseCandidate]
) -> DocumentCaseRouteSuggestion:
    if not document_context.strip():
        raise ValueError("Für das Dokument stehen keine extrahierten Inhalte zur Verfügung.")

    if not candidates:
        return DocumentCaseRouteSuggestion(
            decision="new_case",
            suggested_case_id=None,
            confidence=0.0,
            reason="Es gibt keine bestehenden Fallkandidaten. Ein neuer Fallentwurf wird zur manuellen Prüfung vorgeschlagen; die Zuordnungssicherheit ist nicht messbar.",
            new_case=create_document_case_draft(document_context),
        )

    candidate_text = "\n\n".join(
        (
            f"FALL-ID: {item.case_id}\n"
            f"Titel: {item.title}\n"
            f"Unternehmen: {item.company or 'Nicht angegeben'}\n"
            f"Kategorie: {item.category or 'Nicht angegeben'}\n"
            f"Beschreibung: {item.description or 'Nicht angegeben'}\n"
            f"Management-Zusammenfassung: {item.management_summary or 'Nicht angegeben'}\n"
            f"Retrieval-Ähnlichkeit: {item.similarity if item.similarity is not None else 'n/a'}"
        )
        for item in candidates
    )
    prompt = (
        "DOKUMENT\n========\n"
        f"{document_context}\n\n"
        "MÖGLICHE BESTEHENDE FÄLLE\n============================\n"
        f"{candidate_text}"
    )
    suggestion = _parse_structured(
        system_prompt=ROUTING_SYSTEM_PROMPT,
        user_content=prompt,
        text_format=DocumentCaseRouteSuggestion,
    )

    suggestion.reason = clean_required_user_facing_text(
        suggestion.reason,
        field_name="Fallzuordnungsbegründung",
    )

    valid_ids = {item.case_id for item in candidates}
    if suggestion.suggested_case_id is not None and suggestion.suggested_case_id not in valid_ids:
        raise RuntimeError("Die KI hat eine ungültige Fall-ID vorgeschlagen.")

    if suggestion.decision == "existing_case":
        if suggestion.suggested_case_id is None:
            suggestion.decision = "uncertain"
            suggestion.confidence = 0.0
            suggestion.reason = "Die KI konnte keinen eindeutigen bestehenden Fall bestimmen."
        elif suggestion.confidence < MIN_EXISTING_CASE_CONFIDENCE:
            suggestion.decision = "uncertain"
            suggestion.reason = (
                f"Die vorgeschlagene Zuordnung liegt unter der Prüfschwelle "
                f"von {MIN_EXISTING_CASE_CONFIDENCE:.0%}. "
                + suggestion.reason
            )

    if suggestion.decision == "new_case":
        suggestion.suggested_case_id = None
        suggestion.confidence = 0.0
        if suggestion.new_case is None:
            suggestion.new_case = create_document_case_draft(document_context)
    elif suggestion.decision == "uncertain":
        suggestion.new_case = None
        if suggestion.suggested_case_id is None:
            suggestion.confidence = 0.0
    else:
        suggestion.new_case = None

    return suggestion


def suggest_for_indexed_document(*, document, db, user):
    """Use the same retrieval and routing logic for background and interactive uploads.

    Returns the suggestion and its candidates; never changes case assignment.
    """
    from app import models
    from app.services.embeddings import create_query_embedding
    from app.services.retrieval import match_cases

    chunks = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.document_id == document.id)
        .order_by(models.DocumentChunk.chunk_index)
        .all()
    )
    if not chunks:
        raise ValueError("Für dieses Dokument wurden keine Textabschnitte erstellt.")

    document_text = "\n\n".join(chunk.content for chunk in chunks)
    matches = match_cases(
        db=db,
        user=user,
        query_embedding=create_query_embedding(document_text[:24000]),
        limit=5,
    )
    candidates = []
    for match in matches:
        case = db.get(models.Case, int(match["case_id"]))
        if case is None or getattr(case, "is_archived", False):
            continue
        candidates.append(CaseCandidate(
            case_id=case.id,
            title=case.title,
            company=case.company,
            category=case.category,
            description=case.description,
            management_summary=case.management_summary,
            similarity=float(match["similarity"]),
        ))
    return suggest_document_case_route(
        document_context=document_text[:50000],
        candidates=candidates,
    ), candidates
