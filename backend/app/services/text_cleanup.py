from __future__ import annotations

import re
import unicodedata


_DASH_TRANSLATION = str.maketrans({
    "\u00ad": "",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
})

_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")

_AI_PROVENANCE_RE = re.compile(
    r"(?:Bestätigte\s+KI[- ]Management[- ]Zusammenfassung|"
    r"KI[- ]Management[- ]Zusammenfassung\s+bestätigt)",
    re.IGNORECASE,
)

_GROUPED_INTERNAL_REFS = re.compile(
    r"""
    [\(\[\{]\s*
    (?:
        (?:
            chunk\s*[- ]?\s*id
            |dok(?:ument)?\.?\s*[- ]?\s*id
            |document\s*[- ]?\s*id
        )
        \s*[:#]?\s*\d+
        \s*(?:[,;/|]\s*)?
    ){1,4}
    [\)\]\}]
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SINGLE_INTERNAL_REF = re.compile(
    r"""
    (?:
        chunk\s*[- ]?\s*id
        |dok(?:ument)?\.?\s*[- ]?\s*id
        |document\s*[- ]?\s*id
    )
    \s*[:#]?\s*\d+
    """,
    re.IGNORECASE | re.VERBOSE,
)


def clean_user_facing_text(value: str | None) -> str | None:
    """Clean AI prose without touching structured source-ID fields."""
    if value is None:
        return None

    text = unicodedata.normalize("NFKC", value)
    text = text.translate(_DASH_TRANSLATION)
    text = text.replace("\u00a0", " ")
    text = _ZERO_WIDTH_RE.sub("", text)

    text = _GROUPED_INTERNAL_REFS.sub("", text)
    text = _AI_PROVENANCE_RE.sub("", text)
    text = _SINGLE_INTERNAL_REF.sub("", text)

    text = re.sub(r"\(\s*[,;:/|\-]*\s*\)", "", text)
    text = re.sub(r"\[\s*[,;:/|\-]*\s*\]", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        cleaned = " ".join(paragraph.split()).strip(" ,;:-")
        if cleaned:
            paragraphs.append(cleaned)

    result = "\n\n".join(paragraphs).strip()
    return result or None


def clean_required_user_facing_text(value: str, *, field_name: str) -> str:
    cleaned = clean_user_facing_text(value)
    if not cleaned:
        raise RuntimeError(
            f"{field_name} enthält nach der Textbereinigung keinen verwertbaren Inhalt."
        )
    return cleaned
