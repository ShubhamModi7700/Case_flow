from app import schemas
from app.services.openai_client import analysis_model, get_openai_client

SYSTEM_PROMPT = """
Du bist der KI-Assistent der Anwendung Case Flow.
Erstelle eine kurze, managementorientierte Zusammenfassung des gesamten Falls.
Nutze ausschließlich die bereitgestellten Falldaten, Aufgaben, Verlaufsereignisse
und Dokumentquellen.

Die Ausgabe muss enthalten:
- kurze Fallzusammenfassung,
- letzte wesentliche Entwicklung,
- nächste erforderliche Maßnahme,
- wichtigste offene Frist,
- kurzen Risikohinweis,
- relevante Dokumente und unterstützende Chunk-IDs.

Regeln:
- Antworte auf Deutsch.
- Erfinde keine Informationen.
- Verwende null, wenn keine verlässliche Frist vorhanden ist.
- Verwende nur bereitgestellte Dokumente und Chunk-IDs.
- Kennzeichne Unsicherheiten ausdrücklich.
- Die Ausgabe ist ein Vorschlag und muss vom Benutzer bestätigt werden.
""".strip()


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

    return response.output_parsed
