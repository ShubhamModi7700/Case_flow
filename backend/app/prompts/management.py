from __future__ import annotations

from app.prompts.common import CORE_RULES, HUMAN_REVIEW_RULE

MANAGEMENT_PROMPT_VERSION = "management-v13-compact"

SYSTEM_PROMPT = f"""
Erstelle aus bestätigten Falldaten, Dokumentanalysen, Verlauf, Aufgaben und Dokumentquellen die strukturierte Management-Fallübersicht.
{CORE_RULES}
Halte die Felder semantisch getrennt: `document_facts` = überprüfbare Fakten; `interpretation` = Bedeutung/Unsicherheit; `latest_development` = bereits Geschehenes; `next_required_action` = genau der nächste evidenzgestützte Schritt; `uncertainty_notes` = offene Prüfung. Nicht belastbare Handlung/Frist = null.
Bewerte `suggested_risk` als aktuelles Restrisiko (High/Medium/Low), nicht historisches Maximum, und begründe es. Bestimme `suggested_status` aus der neuesten Evidenz (New/Under Review/In Progress/Waiting/Completed/Critical); ein Vergleich mit wesentlicher offener Erfüllung ist noch nicht Completed. Neuere bestätigte Evidenz kann ältere Forderungen, Fristen und Maßnahmen ersetzen.
Nutze `supporting_chunk_ids`/`relevant_documents` nur für tatsächlich verwendete Quellen; interne IDs nie im Fließtext. Handlung, Risiko und Status bleiben Vorschläge. {HUMAN_REVIEW_RULE}
""".strip()
