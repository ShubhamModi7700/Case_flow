from __future__ import annotations

import logging
import time
from datetime import date
from typing import Literal

from openai import APIConnectionError, APIError, RateLimitError
from pydantic import BaseModel, Field

from app import schemas
from app.services.openai_client import analysis_model, get_openai_client
from app.services.text_cleanup import clean_required_user_facing_text, clean_user_facing_text

logger = logging.getLogger(__name__)


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


DRAFT_SYSTEM_PROMPT = """
Du erstellst aus einem hochgeladenen Dokument einen strukturierten Fallentwurf
für Case Flow.

Das Dokument kann ein PDF, ein gescanntes PDF, ein DOCX-Dokument, eine
XLSX-Datei, eine EML-E-Mail oder eine MSG-E-Mail sein. Case Flow verwaltet
Geschäfts-, Personal-, Vertrags-, Finanz-, Projekt- und sonstige
Unternehmensfälle.

Aufgabe:
- Formuliere einen kurzen, eindeutigen Falltitel.
- Ermittle das Unternehmen nur, wenn es aus dem Dokument ableitbar ist.
- Ermittle Abteilung und externen Kontakt nur, wenn sie klar erkennbar sind.
- Ordne genau eine Kategorie zu: Customer, Contract, Supplier, Employee,
  Project oder Other.
- Beschreibe den Sachverhalt knapp und sachlich.
- Erstelle eine kurze managementorientierte Zusammenfassung.
- Schlage die nächste konkrete Maßnahme vor.
- Übernimm eine eindeutig genannte offene Frist im ISO-Format YYYY-MM-DD.
- Übernimm einen eindeutig genannten finanziellen Betrag als Zahl.

Regeln:
- Antworte auf Deutsch.
- Erfinde keine Namen, Firmen, Fristen oder Beträge.
- Interne RAG-Kennungen wie Chunk-ID, Dokument-ID oder Dok.-ID dürfen nie in benutzerseitigem Text erscheinen.
- Verwende null, wenn ein Wert nicht verlässlich aus dem Dokument hervorgeht.
- Der Falltitel darf eine Überschrift, einen Betreff oder den zentralen
  Dokumentinhalt sinnvoll verkürzen, aber keine neuen Tatsachen hinzufügen.
- Eine Antwortfrist, Zahlungsfrist, Prüfungsfrist oder angekündigte Rückmeldung
  kann als primary_deadline verwendet werden, wenn sie für den weiteren Vorgang
  handlungsrelevant ist.
- Bei Tabellen oder Excel-Dateien nutze nur tatsächlich vorhandene Zellwerte.
- Bei E-Mails berücksichtige Absender, Empfänger, Betreff, Datum und
  Nachrichtentext.
""".strip()


ROUTING_SYSTEM_PROMPT = """
Du unterstützt die Fallzuordnung in Case Flow. Entscheide, ob ein hochgeladenes
Dokument fachlich zu einem der bereitgestellten bestehenden Fälle gehört oder
ob ein neuer Fall vorgeschlagen werden sollte.

Mögliche Entscheidungen:
- existing_case: Das Dokument gehört eindeutig zu einem bestehenden Kandidaten.
- new_case: Das Dokument beschreibt einen neuen eigenständigen Vorgang.
- uncertain: Eine verlässliche Zuordnung ist mit den vorhandenen Informationen
  nicht möglich.

Regeln:
- Die semantische Vektorähnlichkeit ist nur ein Retrieval-Hinweis und darf nie
  allein über die Zuordnung entscheiden.
- Vergleiche Unternehmen, Personen, Betreff, Vertrags-/Projektbezug,
  Referenznummern, Sachverhalt und vorhandene Fallbeschreibung.
- Ähnliche Themen bei unterschiedlichen Unternehmen/Personen sind nicht
  automatisch derselbe Fall.
- Verwende ausschließlich Case-IDs aus der Kandidatenliste.
- Bei existing_case muss suggested_case_id gesetzt sein.
- Bei new_case muss suggested_case_id null sein.
- Bei uncertain darf suggested_case_id gesetzt sein, wenn ein Kandidat plausibel
  ist; andernfalls null.
- confidence ist deine fachliche Sicherheit zwischen 0 und 1, nicht die rohe
  Vektorähnlichkeit.
- Die endgültige Entscheidung trifft immer ein Benutzer. Du speicherst nichts.
- Erfinde keine Informationen. Antworte auf Deutsch.
- Interne RAG-Kennungen wie Chunk-ID, Dokument-ID oder Dok.-ID dürfen nie in der Begründung erscheinen.
""".strip()


def _parse_structured(*, system_prompt: str, user_content: str, text_format):
    response = None
    for attempt in range(3):
        try:
            response = get_openai_client().responses.parse(
                model=analysis_model(),
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
            "model": analysis_model(),
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
            confidence=1.0,
            reason="Es sind noch keine bestehenden Fälle vorhanden. Ein neuer Fall wird vorgeschlagen.",
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
    if suggestion.decision == "existing_case" and suggestion.suggested_case_id is None:
        suggestion.decision = "uncertain"
        suggestion.reason = "Die KI konnte keinen eindeutigen bestehenden Fall bestimmen."
    if suggestion.decision == "new_case":
        suggestion.suggested_case_id = None
        if suggestion.new_case is None:
            suggestion.new_case = create_document_case_draft(document_context)

    return suggestion
