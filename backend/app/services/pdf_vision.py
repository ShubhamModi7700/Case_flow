from __future__ import annotations

import base64
import os

from pydantic import BaseModel, Field

from app.services.openai_client import analysis_model, get_openai_client


class VisionPdfPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str


class VisionPdfExtraction(BaseModel):
    pages: list[VisionPdfPage]


_SYSTEM_PROMPT = """
Du extrahierst Text aus gescannten PDF-Dokumenten für Case Flow.

Regeln:
- Gib den lesbaren Inhalt seitenweise zurück.
- Behalte die tatsächliche PDF-Seitennummer bei (erste PDF-Seite = 1).
- Überspringe vollständig leere Seiten.
- Bewahre Namen, Datumsangaben, Geldbeträge, Aktenzeichen, E-Mail-Adressen,
  Fristen und juristische Fundstellen so exakt wie möglich.
- Bewahre bei E-Mail-Ausdrucken Absender, Empfänger, Betreff, Datum und den
  Nachrichtentext.
- Erfinde keinen Text und ergänze keine fehlenden Informationen.
- Keine Zusammenfassung und keine Interpretation: nur Texttranskription.
""".strip()


def pdf_vision_model() -> str:
    """Model used for scanned-PDF extraction.

    Defaults to the normal analysis model so deployments only need one model
    setting. A separate model can be configured with OPENAI_PDF_VISION_MODEL.
    """
    return os.getenv("OPENAI_PDF_VISION_MODEL", "").strip() or analysis_model()


def pdf_vision_detail() -> str:
    value = os.getenv("OPENAI_PDF_VISION_DETAIL", "high").strip().lower()
    if value not in {"auto", "low", "high"}:
        raise RuntimeError(
            "OPENAI_PDF_VISION_DETAIL muss 'auto', 'low' oder 'high' sein."
        )
    return value


def extract_scanned_pdf_with_openai(
    pdf_bytes: bytes,
    *,
    file_name: str = "document.pdf",
) -> VisionPdfExtraction:
    if not pdf_bytes:
        raise ValueError("Die PDF-Datei ist leer.")

    # OpenAI file inputs require each file to be under 50 MB. Keep a small
    # safety margin so the request fails with a useful Case Flow message.
    max_bytes = 49 * 1024 * 1024
    if len(pdf_bytes) > max_bytes:
        raise ValueError(
            "Das gescannte PDF ist für die KI-Texterkennung zu groß "
            "(maximal ca. 49 MB)."
        )

    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    file_data = f"data:application/pdf;base64,{encoded}"

    try:
        response = get_openai_client().responses.parse(
            model=pdf_vision_model(),
            input=[
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": file_name or "document.pdf",
                            "file_data": file_data,
                            "detail": pdf_vision_detail(),
                        },
                        {
                            "type": "input_text",
                            "text": (
                                "Extrahiere jetzt den lesbaren Text aus allen "
                                "nicht-leeren Seiten dieses PDFs."
                            ),
                        },
                    ],
                },
            ],
            text_format=VisionPdfExtraction,
        )
    except Exception as exc:
        raise RuntimeError(
            "Die KI-Texterkennung für das gescannte PDF ist fehlgeschlagen: "
            f"{exc}"
        ) from exc

    if response.output_parsed is None:
        raise RuntimeError(
            "Die KI-Texterkennung lieferte keine strukturierte Antwort."
        )

    result = response.output_parsed
    result.pages = [
        page
        for page in result.pages
        if page.text and page.text.strip()
    ]

    if not result.pages:
        raise ValueError(
            "Die KI-Texterkennung konnte keinen lesbaren Text im PDF erkennen."
        )

    return result
