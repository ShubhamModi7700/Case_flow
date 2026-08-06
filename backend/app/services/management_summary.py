import re

from app import schemas
from app.services.openai_client import analysis_model, get_openai_client

SYSTEM_PROMPT = """
Du bist der KI-Assistent der Anwendung Case Flow.
Erstelle eine kurze, managementorientierte Zusammenfassung des gesamten Falls.
Nutze ausschließlich die bereitgestellten Falldaten, Aufgaben, fachlichen
Verlaufsereignisse und Dokumentquellen.

Die Ausgabe muss enthalten:
- kurze Fallzusammenfassung,
- letzte wesentliche fachliche Entwicklung,
- nächste erforderliche Maßnahme,
- wichtigste offene Frist,
- kurzen Risikohinweis,
- relevante Dokumente und unterstützende Chunk-IDs.

Regeln für die kurze Fallzusammenfassung:
- Beschreibe den Sachverhalt in zwei bis vier klaren Sätzen.
- Konzentriere dich auf Gegenstand, Parteien, finanzielle oder rechtliche
  Bedeutung und den aktuellen Handlungsbedarf.
- Hänge keine technische Stammdatenliste wie „Status: … Verantwortlich: …
  Risiko: …“ an.
- Status, Verantwortliche und Risiko nur erwähnen, wenn dies zum Verständnis
  des Sachverhalts wirklich erforderlich ist.

Regeln für „Letzte Entwicklung“:
- Nenne die zuletzt eingetretene fachliche oder geschäftliche Entwicklung.
- Bevorzuge neue Schreiben, E-Mails, Dokumente, Antworten, Entscheidungen,
  Fristen oder wesentliche Sachverhaltsänderungen.
- Ignoriere technische Systemereignisse, reine Formularänderungen,
  KI-Erstellungen, KI-Bestätigungen und Audit-Einträge.
- Schreibe niemals, dass eine KI-Zusammenfassung erstellt oder bestätigt wurde.
- Wenn keine fachliche Entwicklung sicher ermittelbar ist, verwende null.

Weitere Regeln:
- Antworte auf Deutsch.
- Erfinde keine Informationen.
- Verwende null, wenn keine verlässliche Frist vorhanden ist.
- Verwende nur bereitgestellte Dokumente, Dokument-IDs und Chunk-IDs.
- Wenn Aussagen auf Dokumentquellen beruhen, führe die entsprechenden
  Dokument-IDs unter relevante Dokumente auf.
- Kennzeichne Unsicherheiten ausdrücklich.
- Die Ausgabe ist ein Vorschlag und muss vom Benutzer bestätigt werden.
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
)


def _clean_short_summary(value: str) -> str:
    cleaned = value.strip()
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _TECHNICAL_SUMMARY_SUFFIX.sub("", cleaned).strip()
    return cleaned


def _clean_latest_development(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    lowered = cleaned.casefold()
    if any(term in lowered for term in _TECHNICAL_DEVELOPMENT_TERMS):
        return None
    return cleaned or None


def generate_management_summary(
    context: str,
) -> schemas.ManagementSummaryAnalysis:
    response = get_openai_client().responses.parse(
        model=analysis_model(),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        text_format=schemas.ManagementSummaryAnalysis,
    )

    if response.output_parsed is None:
        raise RuntimeError(
            "Die strukturierte Management-Zusammenfassung konnte nicht gelesen werden."
        )

    result = response.output_parsed
    result.short_case_summary = _clean_short_summary(result.short_case_summary)
    result.latest_development = _clean_latest_development(
        result.latest_development
    )
    return result
