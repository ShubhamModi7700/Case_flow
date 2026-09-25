from __future__ import annotations

from app.prompts.common import CORE_RULES, HUMAN_REVIEW_RULE


DOCUMENT_ANALYSIS_PROMPT_VERSION = "document-analysis-v7-compact"


SYSTEM_PROMPT = f"""
Analysiere das neue Dokument im Kontext des Falls und fülle das vorgegebene strukturierte Schema.
{CORE_RULES}
Das neue Dokument ist die neueste Evidenz: trenne historische von aktuell noch gültigen Forderungen, Fristen, Beträgen und Risiken; neuere bestätigte Erledigungen/Vergleiche/Zahlungen können ältere Angaben ersetzen.
`latest_development` beschreibt nur bereits Eingetretenes; `proposed_next_action` nur noch auszuführende, evidenzgestützte Schritte. Beide dürfen nicht dasselbe ausdrücken.
Bewerte `suggested_risk` als aktuelles Restrisiko (High/Medium/Low) und `suggested_status` nach aktuellem Arbeitsstand (New/Under Review/In Progress/Waiting/Completed/Critical), jeweils mit Begründung. Nur eindeutig noch offene Fristen übernehmen; sonst null. Interne Dokument-/Chunk-IDs nur in strukturierten Quellenfeldern, nie im Fließtext. {HUMAN_REVIEW_RULE}
""".strip()