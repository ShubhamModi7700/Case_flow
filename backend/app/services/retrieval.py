from app import schemas
from app.services.openai_client import analysis_model, get_openai_client

SYSTEM_PROMPT = """
Du bist der KI-Assistent der Anwendung Case Flow.
Analysiere ausschließlich die bereitgestellten Falldaten und Dokumentquellen.
Antworte auf Deutsch. Erfinde keine Informationen. Verwende null, wenn keine
verlässliche Frist vorliegt. Fallzuordnung, Frist, nächste Maßnahme und Risiko
sind nur Vorschläge und müssen vom Benutzer bestätigt werden. Verwende nur
bereitgestellte Fall-, Dokument- und Chunk-IDs. Halte die Zusammenfassung kurz
und managementorientiert.
""".strip()


def analyze_document_context(context: str) -> schemas.DocumentAIAnalysis:
    response = get_openai_client().responses.parse(
        model=analysis_model(),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        text_format=schemas.DocumentAIAnalysis,
    )
    if response.output_parsed is None:
        raise RuntimeError("Die strukturierte KI-Antwort konnte nicht gelesen werden.")
    return response.output_parsed
