from __future__ import annotations

import re
from difflib import SequenceMatcher

from app import schemas
from app.services.openai_client import analysis_model, get_openai_client
from app.services.text_cleanup import clean_required_user_facing_text, clean_user_facing_text

SYSTEM_PROMPT = """
Du bist der Management-Assistent der Anwendung Case Flow.

Erstelle eine ausführliche, faktenbasierte und managementorientierte
Fallübersicht. Nutze ausschließlich die bereitgestellten bestätigten Falldaten,
bestätigten Dokumentanalysen, fachlichen Verlaufsereignisse, Aufgaben und
Dokumentquellen.

Ziel ist NICHT eine extrem kurze Zusammenfassung. Die Ausgabe soll genügend
Kontext enthalten, damit Management einen Fall auch nach Wochen oder Monaten
verstehen kann, ohne alle Dokumente erneut lesen zu müssen. Trotzdem sollen
Wiederholungen, unnötige Füllsätze und unbelegte Schlussfolgerungen vermieden
werden.

WICHTIG: Die Felder haben unterschiedliche Funktionen und dürfen sich nicht
inhaltlich wiederholen.

1. short_case_summary / Fallzusammenfassung
- Erkläre den Fall in verständlicher Tiefe.
- Typischer Umfang: etwa 1 bis 3 kompakte Absätze bzw. ca. 120 bis 250 Wörter,
  wenn genügend bestätigte Informationen vorhanden sind.
- Beschreibe Ausgangslage, betroffene Parteien/Unternehmen, wesentliche
  Hintergründe, aktuelles Ziel und den bestätigten Stand.
- Bei komplexen Fällen dürfen mehrere zusammenhängende Aspekte genannt werden.
- Keine reine Stammdaten-Aufzählung wie „Status: ... Verantwortlich: ...“.
- Keine detaillierte To-do-Liste in diesem Feld.
- Keine bloße Wiederholung von „Letzte Entwicklung“ oder „Nächste Maßnahme“.

2. latest_development / Letzte Entwicklung
- Beschreibe ausschließlich, WAS BEREITS GESCHEHEN IST.
- Fokus auf das jüngste fachlich relevante Ereignis oder, wenn nötig, auf eine
  kurze Folge unmittelbar zusammenhängender bereits eingetretener Ereignisse.
- Für dieses Feld bewusst kompakt bleiben: typischer Umfang ca. 45 bis 90 Wörter.
- Nenne nur die jüngste fachlich relevante Entwicklung und höchstens unmittelbar
  dazugehörige Fakten. Detailkontext gehört in short_case_summary.
- Verwende Vergangenheits-/Ist-Formulierungen wie „Die Kanzlei hat bestätigt...",
  „Am ... ging ein Schreiben ein...“, „Die Gegenseite teilte mit...“.
- KEINE zukünftigen Handlungsschritte, Empfehlungen, To-dos oder Formulierungen
  wie „soll“, „muss als Nächstes“, „prüfen“, „abstimmen“, „vorbereiten“, sofern
  diese nicht selbst ein bereits eingetretenes Ereignis beschreiben.
- Technische Ereignisse, Uploads, Indexierung, KI-Erstellung, KI-Bestätigung,
  Formularänderungen und Audit-Einträge sind keine fachliche Entwicklung.
- Wenn keine fachliche Entwicklung sicher belegt ist: null.

3. next_required_action / Nächste erforderliche Maßnahme
- Beschreibe ausschließlich, WAS ALS NÄCHSTES GETAN WERDEN SOLL.
- Dies ist ein Handlungsvorschlag und keine bestätigte Tatsache.
- Erkläre bei komplexen Fällen den Hauptschritt und die dafür notwendigen
  Unterpunkte in sinnvoller Reihenfolge.
- Für dieses Feld bewusst kompakt bleiben: typischer Umfang ca. 50 bis 100 Wörter.
- Nenne den Hauptschritt und nur die unmittelbar notwendigen Unterpunkte.
  Ausführliche Hintergründe gehören in short_case_summary.
- Formuliere zukunftsorientiert und handlungsbezogen, z. B. „Rückmeldung prüfen",
  „Mandatsumfang abstimmen“, „Unterlagen anfordern“, „Entscheidung vorbereiten“.
- Wiederhole nicht die Beschreibung dessen, was bereits passiert ist.
- Wenn keine belastbare Maßnahme ableitbar ist: null.

4. open_deadline / Offene Frist
- Nur eine ausdrücklich belegte, für den Fall noch relevante Frist übernehmen.
- Keine Frist schätzen oder aus allgemeinen Formulierungen ableiten.
- Wenn keine verlässliche Frist belegt ist: null.
- deadline_comment darf ausführlicher erklären, von wem die Frist stammt, was
  bis dahin erwartet wird und warum sie für den Fall relevant ist.

5. risk_comment / Risikohinweis
- Erläutere die belegten Risikofaktoren nachvollziehbar und differenziert.
- Für die Management-Übersicht kompakt formulieren: typischer Umfang ca. 40 bis
  80 Wörter, auch bei komplexeren Fällen.
- Unterscheide zwischen bereits eingetretenen Problemen und möglichen Folgen.
- Keine neue Risikoklassifikation erfinden; die Risikostufe wird außerhalb
  dieses Textes berechnet bzw. bestätigt.

6. Quellen
- Verwende nur Dokument-IDs und Chunk-IDs, die im Kontext tatsächlich
  bereitgestellt wurden.
- supporting_chunk_ids nur für Quellen verwenden, die konkrete Aussagen der
  Ausgabe wirklich stützen.
- relevant_documents nur für tatsächlich verwendete Dokumente zurückgeben.
- Interne Quellenkennungen wie "Chunk-ID", "Dokument-ID", "Dok.-ID" oder
  Klammerangaben wie "(Chunk-ID 4, Dok.-ID 3)" dürfen niemals im Fließtext
  erscheinen. Diese Kennungen gehören ausschließlich in supporting_chunk_ids
  und relevant_documents.

Qualitätsregeln:
- Antworte auf Deutsch.
- Erfinde keine Informationen, Namen, Daten, Beträge oder Ereignisse.
- Keine Vermutungen als Tatsachen formulieren.
- Fakten und Empfehlungen strikt trennen.
- „Letzte Entwicklung“ und „Nächste Maßnahme“ müssen semantisch klar verschieden
  sein. Sie dürfen nicht denselben Text oder dieselbe Aufzählung enthalten.
- Bei Widersprüchen zwischen älteren und neueren bestätigten Informationen
  bevorzuge die neuere bestätigte Information und erwähne die Unsicherheit.
- Wenn Informationen nicht sicher belegt sind, verwende null oder nenne die
  Unsicherheit in uncertainty_notes.
- Priorisiere Verständlichkeit und Substanz vor künstlicher Kürze.
- Die Ausgabe bleibt ein KI-Vorschlag und muss vom Benutzer bestätigt werden.
""".strip()

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

    response = get_openai_client().responses.parse(
        model=analysis_model(),
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
    result.latest_development = _clean_latest_development(result.latest_development)
    result.next_required_action = _clean_action(result.next_required_action)
    result.risk_comment = _clean_risk_comment(result.risk_comment)
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
