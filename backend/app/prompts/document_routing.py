from __future__ import annotations

from app.prompts.common import CORE_RULES, HUMAN_REVIEW_RULE

DOCUMENT_ROUTING_PROMPT_VERSION = "document-routing-v4-natural-german"

DRAFT_SYSTEM_PROMPT = f"""
Erstelle aus dem hochgeladenen Dokument einen strukturierten Case-Flow-Fallentwurf.
{CORE_RULES}
Ermittle Titel, Unternehmen, Abteilung, externen Kontakt, Kategorie (Customer/Contract/Supplier/Employee/Project/Other), Sachverhalt, Management-Zusammenfassung, nächste Maßnahme sowie nur eindeutig belegte offene Frist (YYYY-MM-DD) und Betrag. Nicht belegbare Werte = null.
Bei Tabellen nur vorhandene Zellwerte; bei E-Mails Absender, Empfänger, Betreff, Datum und Nachrichtentext berücksichtigen. Interne RAG-Kennungen nie in benutzerseitigen Text schreiben.
""".strip()

ROUTING_SYSTEM_PROMPT = f"""
Ordne das Dokument einem bereitgestellten bestehenden Fall zu oder schlage einen neuen Fall vor.
{CORE_RULES}
Entscheidung: `existing_case`, `new_case` oder `uncertain`. Vergleiche insbesondere Unternehmen, Personen, Betreff, Referenzen und Sachverhalt; Vektorähnlichkeit ist nur ein Hinweis. Nutze nur Kandidaten-Case-IDs. Bei `existing_case` ist `suggested_case_id` Pflicht, bei `new_case` null; `confidence` beschreibt fachliche Sicherheit 0..1. Interne RAG-Kennungen nicht in Begründungstext schreiben. {HUMAN_REVIEW_RULE}
""".strip()
