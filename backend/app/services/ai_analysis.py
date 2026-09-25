from __future__ import annotations

import logging
import re
import time
from difflib import SequenceMatcher

from openai import APIConnectionError, APIError, RateLimitError

from app import schemas
from app.services.ai_provider import get_ai_provider
from app.services.text_cleanup import clean_required_user_facing_text, clean_user_facing_text
from app.prompts.document_analysis import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


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


def _parse_document_analysis(
    context: str,
    *,
    correction: str | None = None,
) -> schemas.DocumentAIAnalysis:
    user_content = context
    if correction:
        user_content += (
            "\n\nQUALITÄTSKORREKTUR\n"
            "==================\n"
            + correction
        )

    response = None
    for attempt in range(3):
        try:
            response = get_ai_provider().structured_parse(
                                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                text_format=schemas.DocumentAIAnalysis,
            )
            break
        except RateLimitError:
            if attempt == 2:
                raise RuntimeError("OpenAI-Ratenlimit erreicht.")
            time.sleep(2 ** attempt)
        except APIConnectionError as exc:
            raise RuntimeError("Keine Verbindung zum OpenAI-Dienst.") from exc
        except APIError as exc:
            raise RuntimeError(f"OpenAI API Fehler: {exc}") from exc

    if response is None or response.output_parsed is None:
        raise RuntimeError("Die strukturierte KI-Antwort konnte nicht gelesen werden.")
    return response.output_parsed


def analyze_document_context(context: str) -> schemas.DocumentAIAnalysis:
    if not context.strip():
        raise ValueError("Für die Dokumentanalyse fehlen Inhalte.")

    result = _parse_document_analysis(context)
    result.suggested_summary = clean_required_user_facing_text(
        result.suggested_summary,
        field_name="Dokumentzusammenfassung",
    )
    result.latest_development = clean_user_facing_text(result.latest_development)
    result.deadline_source = clean_user_facing_text(result.deadline_source)
    result.proposed_next_action = clean_user_facing_text(result.proposed_next_action)
    result.risk_reason = clean_user_facing_text(result.risk_reason)
    result.status_reason = clean_user_facing_text(result.status_reason)
    for item in result.relevant_documents:
        item.reason = clean_user_facing_text(item.reason) or item.reason
    result.uncertainty_notes = [
        cleaned
        for note in result.uncertainty_notes
        if (cleaned := clean_user_facing_text(note))
    ]

    overlap = _semantic_overlap(result.latest_development, result.proposed_next_action)

    # Repair the source-level evidence before it can propagate into the case-level
    # management summary. Containment catches paraphrases where one field embeds
    # most of the content of the other even when the raw strings differ.
    if overlap >= 0.55:
        correction = (
            "Die Felder 'latest_development' und 'proposed_next_action' überlappen "
            "inhaltlich zu stark. Formuliere die gesamte strukturierte Antwort neu. "
            "'latest_development' darf nur bereits eingetretene, bestätigte Ereignisse "
            "enthalten. 'proposed_next_action' darf nur noch auszuführende, zukünftige "
            "Handlungen enthalten. Behalte die fachliche Tiefe bei, aber wiederhole "
            "keine Sätze, Aufzählungen oder Handlungspläne zwischen diesen Feldern."
        )
        result = _parse_document_analysis(context, correction=correction)
        result.suggested_summary = clean_required_user_facing_text(
            result.suggested_summary,
            field_name="Dokumentzusammenfassung",
        )
        result.latest_development = clean_user_facing_text(result.latest_development)
        result.deadline_source = clean_user_facing_text(result.deadline_source)
        result.proposed_next_action = clean_user_facing_text(result.proposed_next_action)
        for item in result.relevant_documents:
            item.reason = clean_user_facing_text(item.reason) or item.reason
        result.uncertainty_notes = [
            cleaned
            for note in result.uncertainty_notes
            if (cleaned := clean_user_facing_text(note))
        ]
        overlap = _semantic_overlap(result.latest_development, result.proposed_next_action)

    if overlap >= 0.65:
        # Prefer missing data over misleading duplication. The management layer can
        # still derive an action from the remaining confirmed evidence later.
        result.uncertainty_notes.append(
            "Letzte Entwicklung und nächste Maßnahme konnten nicht ausreichend "
            "getrennt werden; die nächste Maßnahme wurde deshalb nicht übernommen."
        )
        result.proposed_next_action = None

    logger.info(
        "AI analysis completed",
        extra={
            "model": get_ai_provider().analysis_model(),
            "context_length": len(context),
            "latest_action_overlap": overlap,
        },
    )
    return result
