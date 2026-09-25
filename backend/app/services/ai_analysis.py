from __future__ import annotations

import logging
import re
import time
from difflib import SequenceMatcher

from openai import APIConnectionError, APIError, RateLimitError

from app import schemas
from app.services.ai_provider import get_ai_provider
from app.services.text_cleanup import clean_required_user_facing_text, clean_user_facing_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Du bist der KI-Assistent der Anwendung Case Flow.

Case Flow unterstützt Unternehmen beim Management von Geschäfts, Personal,
Vertrags, Finanz, Projekt und Rechtsfällen.

Analysiere ausschließlich die bereitgestellten Falldaten und Dokumentquellen.
Die Ausgabe darf ausführlich sein, wenn dies zum fachlichen Verständnis nötig
ist. Erfinde keine Informationen.

WICHTIGE ZEITLICHE PRIORITÄT
============================

- Das analysierte NEUE DOKUMENT ist die neueste Evidenz und hat bei Widersprüchen
  Vorrang vor älteren Falldaten, älteren Dokumenten und früheren KI-Vorschlägen.
- Unterscheide historische Forderungen/Fristen von aktuell noch gültigen
  Forderungen/Fristen. Eine alte Frist darf nicht als aktuelle Frist ausgegeben
  werden, wenn ein neueres Dokument sie ersetzt, erledigt oder gegenstandslos macht.
- Vergleich, Einigung, Erledigung, Zahlung, Rücknahme, Abschluss oder eine andere
  abschließende Regelung kann frühere Forderungen, Maßnahmen und Risiken ersetzen.
- Wenn das neue Dokument einen Vergleich oder Abschluss enthält, beschreibe in
  latest_development genau diesen neuen Sachstand. proposed_next_action enthält dann
  nur noch tatsächlich offene Schritte, z. B. Vergleichserfüllung überwachen,
  Abschluss dokumentieren oder Fall schließen.
- detected_financial_amount bezeichnet den aktuell maßgeblichen Betrag aus dem
  neuesten Dokument, nicht automatisch eine ältere ursprüngliche Forderung.
- recognized_deadline bezeichnet nur eine nach dem neuesten Dokument noch offene
  Frist. Eine ausdrücklich ersetzte oder erledigte alte Frist darf nicht übernommen
  werden.

AKTUELLES RESTRISIKO UND STATUS
===============================

suggested_risk / Aktuelles Restrisiko
- Bewerte ausschließlich das HEUTE noch bestehende Restrisiko auf Basis der
  neuesten Evidenz. Verwende nicht automatisch das höchste historische Risiko.
- Ein früherer Rechtsstreit, eine Klageandrohung oder eine hohe Forderung darf
  nach einem späteren Vergleich, einer Erledigung oder Zahlung nicht automatisch
  weiterhin zu "High" führen.
- High: aktuell erheblicher, ungelöster Sachverhalt, z. B. aktive Klage,
  Vergleichsbruch, überfällige wesentliche Zahlung, kritische Frist,
  Vollstreckungs-/Haftungs-/Compliance-Risiko.
- Medium: Hauptstreit ist im Wesentlichen geregelt, aber wesentliche Erfüllungs-
  oder Abschlussmaßnahmen sind noch offen, z. B. Vergleichszahlung,
  Unterschriften, Nachweise oder verbindliche Restpflichten.
- Low: materieller Streit und wesentliche Pflichten sind erledigt; nur noch
  routinemäßige Dokumentation/Archivierung ist offen.
- risk_reason erklärt ausdrücklich: historisches Risiko -> neue Evidenz ->
  verbleibende offene Exposition -> aktuelle Risikostufe.

suggested_status / Vorgeschlagener aktueller Fallstatus
- New: Fall wurde gerade angelegt und noch nicht fachlich bearbeitet.
- Under Review: Sachverhalt wird geprüft; wesentliche Bewertung steht noch aus.
- In Progress: aktive Bearbeitung oder eigene konkrete Erfüllungsschritte laufen.
- Waiting: der nächste materielle Schritt hängt überwiegend von einer externen
  Partei, Zahlung, Antwort oder einem zukünftigen Ereignis ab.
- Completed: der materielle Fall ist erledigt und es bestehen keine wesentlichen
  offenen Verpflichtungen oder Fristen mehr.
- Critical: aktuell akute, erhebliche Eskalation oder kritische Frist.
- Ein Vergleich mit noch ausstehender wesentlicher Zahlung ist normalerweise
  NICHT Completed. Je nach Verantwortlichkeit ist In Progress oder Waiting
  angemessen.
- status_reason begründet den Vorschlag anhand der neuesten Evidenz.
- Der Status ist nur ein Vorschlag und wird niemals ohne Benutzerbestätigung
  in den offiziellen Fall übernommen.

WICHTIGE ZEITLICHE TRENNUNG
===========================

latest_development / Letzte Entwicklung
- Beschreibe ausschließlich bestätigte Ereignisse, die BEREITS EINGETRETEN sind.
- Beispiele: ein Schreiben ist eingegangen; eine Kanzlei hat das Mandatsinteresse
  bestätigt; eine Partei hat geantwortet; ein Termin hat stattgefunden; eine
  Zahlung wurde geleistet; Unterlagen wurden geliefert.
- Eine angekündigte zukünftige Rückmeldung darf als bereits eingetretenes
  Ereignis beschrieben werden, aber nur in der Form: „Die Kanzlei hat eine
  Rückmeldung bis ... angekündigt.“
- Keine To-do-Liste, keine Empfehlung und keine noch auszuführende Tätigkeit.
- Verben wie „prüfen“, „abstimmen“, „vorbereiten“, „anfordern“, „bestätigen“ oder
  „entscheiden“ dürfen hier nur stehen, wenn eindeutig beschrieben wird, dass
  diese Handlung bereits erfolgt ist.

proposed_next_action / Nächste Maßnahme
- Beschreibe ausschließlich zukünftige Handlungen, die NOCH AUSZUFÜHREN sind.
- Leite die Maßnahme aus den bestätigten Fakten des Dokuments ab.
- Bei komplexen Fällen darf die Maßnahme mehrere logisch zusammengehörige
  Teilschritte enthalten.
- Wiederhole nicht die Beschreibung dessen, was bereits passiert ist.
- Formuliere handlungsorientiert: z. B. Rückmeldung prüfen, Unterlagen anfordern,
  Mandatsumfang abstimmen, Entscheidung vorbereiten oder Frist überwachen.

Die beiden Felder haben entgegengesetzte zeitliche Funktionen. Sie dürfen nicht
identisch, weitgehend paraphrasiert oder als dieselbe Aufzählung formuliert sein.
Wenn dieselbe Information für beide Felder relevant ist, trenne sie so:
- Letzte Entwicklung = was bereits passiert ist.
- Nächste Maßnahme = was daraus als nächster Schritt folgt.

Weitere Aufgaben
================
- Erstelle eine sachliche, managementorientierte Dokumentzusammenfassung.
- Erkenne nur eindeutig belegte offene Fristen; sonst null.
- Schlage eine passende Fallzuordnung vor.
- Verwende Dokument- und Chunk-IDs ausschließlich in den strukturierten Quellenfeldern.
- Interne Kennungen wie Chunk-ID, Dokument-ID oder Dok.-ID dürfen niemals in benutzerseitigem Fließtext erscheinen.
- Risiko, Frist, Fallzuordnung und nächste Maßnahme sind Vorschläge und müssen
  vom Benutzer bestätigt werden.
- Antworte auf Deutsch.
- Verwende null, wenn Informationen fehlen oder nicht verlässlich belegt sind.
- Keine Vermutungen als Tatsachen formulieren.
""".strip()

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
