from __future__ import annotations

EXTRACTION_PROMPT_VERSION = "pdf-extraction-v3-verbatim"

SYSTEM_PROMPT = """
Extrahiere den sichtbaren Text des PDF möglichst originalgetreu in Seiten/Lesereihenfolge.
Nicht zusammenfassen, interpretieren, übersetzen, korrigieren oder fehlenden Text ergänzen.
Erhalte Überschriften, Listen, sinnvolle Zeilen-/Tabellenstruktur sowie Namen, Daten, Beträge und Referenzen exakt; leere Seiten überspringen.
""".strip()
