import logging
import time

from openai import APIConnectionError, APIError, RateLimitError

from app import schemas
from app.services.openai_client import (
    analysis_model,
    get_openai_client,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Du bist der KI-Assistent der Anwendung Case Flow.

Case Flow unterstützt Unternehmen beim Management von Geschäfts-, Personal-,
Vertrags-, Finanz- und Rechtsfällen.

Analysiere ausschließlich die bereitgestellten Informationen.

Deine Aufgaben:

- Erstelle eine kurze Management-Zusammenfassung.
- Erkenne die neueste relevante Entwicklung.
- Erkenne offene Fristen.
- Schlage die nächste Maßnahme vor.
- Schlage eine Risikoeinstufung vor.
- Schlage die passende Fallzuordnung vor.
- Verweise ausschließlich auf bereitgestellte Dokumente und Chunks.

Regeln:

- Antworte ausschließlich auf Deutsch.
- Erfinde keine Informationen.
- Nutze ausschließlich bereitgestellte Daten.
- Verwende null, wenn Informationen fehlen.
- Risiko, Frist, Fallzuordnung und nächste Maßnahme sind nur Vorschläge.
- Alle Vorschläge müssen vom Benutzer bestätigt werden.
- Verwende nur vorhandene Fall-, Dokument- und Chunk-IDs.
- Schreibe kurz, präzise und managementorientiert.
""".strip()


def analyze_document_context(
    context: str,
) -> schemas.DocumentAIAnalysis:

    response = None

    for attempt in range(3):

        try:

            response = get_openai_client().responses.parse(
                model=analysis_model(),
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": context,
                    },
                ],
                text_format=schemas.DocumentAIAnalysis,
            )

            break

        except RateLimitError:

            if attempt == 2:
                raise RuntimeError(
                    "OpenAI-Ratenlimit erreicht."
                )

            time.sleep(2 ** attempt)

        except APIConnectionError as exc:

            raise RuntimeError(
                "Keine Verbindung zum OpenAI-Dienst."
            ) from exc

        except APIError as exc:

            raise RuntimeError(
                f"OpenAI API Fehler: {exc}"
            ) from exc

    if response is None:

        raise RuntimeError(
            "Keine Antwort von OpenAI erhalten."
        )

    if response.output_parsed is None:

        raise RuntimeError(
            "Die strukturierte KI-Antwort konnte nicht gelesen werden."
        )

    logger.info(
        "AI analysis completed",
        extra={
            "model": analysis_model(),
            "context_length": len(context),
        },
    )

    return response.output_parsed