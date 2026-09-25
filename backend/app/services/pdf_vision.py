from __future__ import annotations

import base64
import logging
import time

from openai import (
    APIConnectionError,
    APIError,
    RateLimitError,
)
from pydantic import BaseModel, Field

from app.services.ai_provider import get_ai_provider
from app.prompts.extraction import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class VisionPdfPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str


class VisionPdfExtraction(BaseModel):
    pages: list[VisionPdfPage]




def extract_scanned_pdf_with_openai(
    pdf_bytes: bytes,
    *,
    file_name: str = "document.pdf",
) -> VisionPdfExtraction:

    if not pdf_bytes:
        raise ValueError("Die PDF-Datei ist leer.")

    if len(pdf_bytes) > 49 * 1024 * 1024:
        raise ValueError(
            "Das PDF überschreitet die maximale Größe von 49 MB."
        )

    encoded = base64.b64encode(pdf_bytes).decode()

    response = None

    for attempt in range(3):

        try:

            response = get_ai_provider().structured_parse(

                
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_file",
                                "filename": file_name,
                                "file_data": f"data:application/pdf;base64,{encoded}",
                                "detail": "high",
                            },
                            {
                                "type": "input_text",
                                "text": """
Extrahiere den vollständigen lesbaren Text.

Für jede Seite:

- Seitennummer beibehalten
- Reihenfolge beibehalten
- Tabellen möglichst strukturiert übernehmen
- Nur lesbaren Text
- Keine Interpretation
- Keine Zusammenfassung
""",
                            },
                        ],
                    },
                ],

                text_format=VisionPdfExtraction,
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
            "OpenAI konnte keinen PDF-Text extrahieren."
        )

    result = response.output_parsed

    pages = {}

    for page in result.pages:

        if not page.text.strip():
            continue

        existing = pages.get(page.page_number)

        if existing is None or len(page.text) > len(existing.text):
            pages[page.page_number] = page

    result.pages = sorted(
        pages.values(),
        key=lambda page: page.page_number,
    )

    total_text = "\n".join(
        page.text
        for page in result.pages
    )

    if len(total_text.strip()) < 50:
        raise ValueError(
            "Kein lesbarer Text erkannt."
        )

    logger.info(
        "PDF Vision completed",
        extra={
            "file": file_name,
            "pages": len(result.pages),
            "characters": len(total_text),
            "model": get_ai_provider().analysis_model(),
        },
    )

    return result