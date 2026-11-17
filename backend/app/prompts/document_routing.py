from __future__ import annotations

from app.prompts.common import CORE_RULES, HUMAN_REVIEW_RULE

DOCUMENT_ROUTING_PROMPT_VERSION = "document-routing-v6-existing-cases-only"

DRAFT_SYSTEM_PROMPT = f"""
Erstelle aus dem hochgeladenen Dokument einen strukturierten Case-Flow-Fallentwurf.
{CORE_RULES}
Ermittle Titel, Unternehmen, Abteilung, externen Kontakt, Kategorie (Customer/Contract/Supplier/Employee/Project/Other), Sachverhalt, Management-Zusammenfassung, nächste Maßnahme sowie nur eindeutig belegte offene Frist (YYYY-MM-DD) und Betrag. Nicht belegbare Werte = null.
Bei Tabellen nur vorhandene Zellwerte; bei E-Mails Absender, Empfänger, Betreff, Datum und Nachrichtentext berücksichtigen. Interne RAG-Kennungen nie in benutzerseitigen Text schreiben.
""".strip()

ROUTING_SYSTEM_PROMPT = f"""
Prüfe ausschließlich die Zuordnung zu bereitgestellten bestehenden Fällen. Erstelle keinen neuen Fall.
{CORE_RULES}
Entscheidung: `existing_case` oder `uncertain` (niemals `new_case`). Vergleiche insbesondere Unternehmen, Personen, Betreff, Referenzen und Sachverhalt; Vektorähnlichkeit ist nur ein Hinweis. Gleiche Firmennamen oder allgemeine Schlagwörter allein reichen nicht für eine Zuordnung. Achte auf eindeutige Projektbezeichnungen, Vorgangsnummern, konkrete Beteiligte und den zeitlichen Sachzusammenhang. Bei widersprüchlichen Referenzen oder mehreren plausiblen Fällen wähle `uncertain`, auch wenn ein Kandidat eine hohe Vektorähnlichkeit hat. Erfinde keine Belege oder Fallverbindungen. Nutze nur Kandidaten-Case-IDs. Bei `existing_case` ist `suggested_case_id` Pflicht, bei `new_case` null; `confidence` beschreibt fachliche Sicherheit 0..1. Interne RAG-Kennungen nicht in Begründungstext schreiben. {HUMAN_REVIEW_RULE}
""".strip()
