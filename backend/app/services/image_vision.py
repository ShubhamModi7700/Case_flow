from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

from openai import APIConnectionError, APIError, RateLimitError
from pydantic import BaseModel

from app.services.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)


class VisionImageExtraction(BaseModel):
    text: str


IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def extract_image_with_openai(image_bytes: bytes, *, file_name: str) -> str:
    """Extract visible text from a case-relevant image attachment.

    Decorative/inline-image filtering belongs in document_indexing.py so this
    function can stay focused on OCR/vision extraction.
    """
    if not image_bytes:
        raise ValueError("Die Bilddatei ist leer.")

    extension = Path(file_name).suffix.lower()
    mime_type = IMAGE_MIME_TYPES.get(extension)
    if not mime_type:
        raise ValueError(f"Bildformat {extension or 'unbekannt'} wird nicht unterstützt.")

    if len(image_bytes) > 10 * 1024 * 1024:
        raise ValueError("Das Bild überschreitet die maximale Größe von 10 MB.")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    response = None

    for attempt in range(3):
        try:
            response = get_ai_provider().structured_parse(
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Extrahiere ausschließlich den tatsächlich sichtbaren Text "
                            "aus dem Dokumentbild. Nicht zusammenfassen, interpretieren, "
                            "übersetzen oder fehlenden Text ergänzen. Erhalte Namen, Daten, "
                            "Beträge, Aktenzeichen, Überschriften, Listen und Tabellen "
                            "möglichst originalgetreu."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_image",
                                "image_url": f"data:{mime_type};base64,{encoded}",
                                "detail": "high",
                            },
                            {
                                "type": "input_text",
                                "text": "Extrahiere den vollständigen lesbaren Text dieses Dokuments.",
                            },
                        ],
                    },
                ],
                text_format=VisionImageExtraction,
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
        raise RuntimeError("OpenAI konnte keinen Bildtext extrahieren.")

    text = response.output_parsed.text.strip()
    if len(text) < 10:
        raise ValueError("Im Bild wurde kein ausreichender lesbarer Text erkannt.")

    logger.info(
        "Image Vision completed",
        extra={
            "file": file_name,
            "characters": len(text),
            "model": get_ai_provider().analysis_model(),
        },
    )
    return text
