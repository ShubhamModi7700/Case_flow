from __future__ import annotations

import re
from difflib import SequenceMatcher

from app import schemas
from app.services.ai_provider import get_ai_provider
from app.services.text_cleanup import clean_required_user_facing_text, clean_user_facing_text
from app.prompts.management import SYSTEM_PROMPT


_TECHNICAL_SUMMARY_SUFFIX = re.compile(
    r"\s*(?:Status\s*:\s*[^.]+\.\s*)?"
    r"(?:Verantwortlich(?:e Person)?\s*:\s*[^.]+\.\s*)?"
    r"(?:Risiko\s*:\s*[^.]+\.?)\s*$",
    flags=re.IGNORECASE,
)

_TECHNICAL_DEVELOPMENT_TERMS = (
    "ki-management-zusammenfassung",
    "ki-vorschläge bestätigt",
    "ki-zusammenfassung",
    "ki-analyse",
    "dokument verarbeitet",
    "dokument indexiert",
    "embedding",
    "hochgeladen",
    "upload",
)


def _clean_text(value: str | None) -> str | None:
    cleaned = clean_user_facing_text(value)
    if not cleaned:
        return None
    paragraphs = [" ".join(part.split()).strip() for part in re.split(r"\n\s*\n", cleaned)]
    return "\n\n".join(part for part in paragraphs if part) or None


def _clean_short_summary(value: str) -> str:
    cleaned = _clean_text(value) or ""
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _TECHNICAL_SUMMARY_SUFFIX.sub("", cleaned).strip()
    if not cleaned:
        raise RuntimeError("Die KI hat keine belastbare Fallzusammenfassung geliefert.")
    return clean_required_user_facing_text(cleaned, field_name="Fallzusammenfassung")


def _clean_latest_development(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    if any(term in lowered for term in _TECHNICAL_DEVELOPMENT_TERMS):
        return None
    return cleaned


def _clean_action(value: str | None) -> str | None:
    return _clean_text(value)


def _clean_risk_comment(value: str | None) -> str | None:
    return _clean_text(value)


def _clean_deadline_comment(value: str | None) -> str | None:
    return _clean_text(value)


_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
    "eines", "einem", "einen", "und", "oder", "zu", "zur", "zum", "von",
    "vom", "mit", "für", "auf", "im", "in", "am", "an", "als", "auch",
    "ist", "sind", "war", "wurde", "werden", "wird", "hat", "haben", "bei",
    "nach", "vor", "über", "durch", "sowie", "dass", "dies", "diese", "dieser",
    "noch", "nicht", "bzw", "bzw.", "bisher", "aktuell",
}


def _significant_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    words = re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", value.casefold())
    return {word for word in words if len(word) >= 4 and word not in _STOPWORDS}


def _semantic_overlap(first: str | None, second: str | None) -> float:
    if not first or not second:
        return 0.0
    normalize = lambda value: re.sub(r"[^a-z0-9äöüß]+", " ", value.casefold()).strip()
    left = normalize(first)
    right = normalize(second)
    if not left or not right:
        return 0.0

    sequence_score = SequenceMatcher(None, left, right).ratio()
    left_tokens = _significant_tokens(first)
    right_tokens = _significant_tokens(second)
    if not left_tokens or not right_tokens:
        return sequence_score

    common = len(left_tokens & right_tokens)
    containment_score = common / min(len(left_tokens), len(right_tokens))
    return max(sequence_score, containment_score)


def _parse_management_summary(context: str, *, correction: str | None = None) -> schemas.ManagementSummaryAnalysis:
    user_content = context
    if correction:
        user_content += (
            "\n\nQUALITÄTSKORREKTUR\n"
            "==================\n"
            + correction
        )

    response = get_ai_provider().structured_parse(
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        text_format=schemas.ManagementSummaryAnalysis,
    )
    if response.output_parsed is None:
        raise RuntimeError(
            "Die strukturierte Management-Zusammenfassung konnte nicht gelesen werden."
        )
    return response.output_parsed


def _clean_result(result: schemas.ManagementSummaryAnalysis) -> schemas.ManagementSummaryAnalysis:
    result.short_case_summary = _clean_short_summary(result.short_case_summary)
    result.document_facts = [
        clean_required_user_facing_text(item, field_name="Dokumentfakt")
        for item in result.document_facts
        if clean_user_facing_text(item)
    ][:6]
    result.interpretation = _clean_text(result.interpretation)
    result.responsible_role = _clean_text(result.responsible_role)
    result.action_justification = _clean_text(result.action_justification)
    result.uncertainty_notes = [
        clean_required_user_facing_text(item, field_name="Unsicherheitshinweis")
        for item in result.uncertainty_notes
        if clean_user_facing_text(item)
    ][:6]
    result.latest_development = _clean_latest_development(result.latest_development)
    result.next_required_action = _clean_action(result.next_required_action)
    result.risk_comment = _clean_risk_comment(result.risk_comment)
    result.status_reason = _clean_text(result.status_reason)
    result.deadline_comment = _clean_deadline_comment(result.deadline_comment)
    return result


def generate_management_summary(
    context: str,
) -> schemas.ManagementSummaryAnalysis:
    if not context.strip():
        raise ValueError("Für die Management-Zusammenfassung fehlen Falldaten.")

    result = _clean_result(_parse_management_summary(context))

    # The two fields have opposite temporal purposes. If the first answer makes
    # them too similar, ask once for a targeted rewrite instead of showing a
    # confusing duplicate to management.
    overlap = _semantic_overlap(
        result.latest_development,
        result.next_required_action,
    )
    if overlap >= 0.55:
        correction = (
            "Die Felder 'latest_development' und 'next_required_action' sind in "
            "der ersten Fassung zu ähnlich. Erstelle die gesamte strukturierte "
            "Antwort erneut. 'latest_development' darf ausschließlich bereits "
            "eingetretene, bestätigte Ereignisse beschreiben. "
            "'next_required_action' darf ausschließlich zukünftige, konkrete "
            "Handlungsschritte beschreiben. Behalte die inhaltliche Tiefe bei "
            "und kürze die Felder nicht künstlich."
        )
        result = _clean_result(_parse_management_summary(context, correction=correction))
        overlap = _semantic_overlap(
            result.latest_development,
            result.next_required_action,
        )

    # If a second model pass still cannot separate past evidence from future
    # action, do not persist a misleading duplicate. Keep the confirmed past
    # development and leave the action empty for human review/regeneration.
    if overlap >= 0.65:
        result.uncertainty_notes.append(
            "Letzte Entwicklung und nächste Maßnahme konnten nicht ausreichend "
            "getrennt werden; die nächste Maßnahme wurde deshalb nicht übernommen."
        )
        result.next_required_action = None

    return result
