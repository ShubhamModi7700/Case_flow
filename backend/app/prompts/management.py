from __future__ import annotations

from app.prompts.common import CORE_RULES, HUMAN_REVIEW_RULE


MANAGEMENT_PROMPT_VERSION = "management-v16-natural-german"


SYSTEM_PROMPT = f"""
Erstelle aus bestätigten Falldaten, Dokumentanalysen, Verlauf, Aufgaben und Dokumentquellen die strukturierte Management-Fallübersicht.

{CORE_RULES}

Halte die Felder semantisch strikt getrennt:

`document_facts`
= überprüfbare, durch die bereitgestellte Evidenz belegte Tatsachen.

`document_fact_citations`
= Quellenzuordnung für jeden Eintrag in `document_facts`. Für jeden Fakt verwende dessen nullbasierten `fact_index` und ausschließlich die Chunk-IDs der QUELLE-Blöcke, die genau diesen Fakt belegen. Mindestens eine konkrete Chunk-ID pro Fakt, wenn der Fakt als belegt ausgegeben wird. Keine bloß thematisch ähnlichen Quellen zuordnen.

`interpretation`
= fachliche Einordnung, Bedeutung und Unsicherheit der belegten Fakten.

`latest_development`
= die zeitlich jüngste relevante, bereits eingetretene und belegte Entwicklung des Falls.

Für `latest_development`:
- Bestimme zuerst den aktuellsten belegten fachlichen Ereignisstand.
- Maßgeblich ist das Datum des Ereignisses, nicht Upload-, Analyse-, Indexierungs- oder Erstellungszeitpunkt eines KI-Eintrags.
- Ein neueres Dokument kann ein älteres Ereignis beschreiben; behandle es dann nicht automatisch als jüngste Entwicklung.
- Beschreibe nur bereits Geschehenes.
- Keine Empfehlung oder zukünftige Handlung aufnehmen.
- Berücksichtige, ob neuere bestätigte Evidenz einen älteren Stand ersetzt, erledigt oder verändert.
- Wenn keine jüngste Entwicklung belastbar bestimmbar ist, verwende null.

`next_required_action`
= genau der unmittelbar nächste noch auszuführende, evidenzgestützte Schritt aus dem aktuellen Fallstand.

Für `next_required_action`:
- Prüfe zuerst bestehende offene Aufgaben, dokumentierte Anforderungen, ausstehende Antworten, fehlende Unterlagen und bestätigte Dokumentanalysen.
- Bevorzuge einen ausdrücklich dokumentierten nächsten Schritt.
- Falls kein Schritt ausdrücklich vorgegeben ist, darf ein sinnvoller Schritt aus der Evidenz abgeleitet werden; er bleibt jedoch ein KI-Vorschlag und keine bereits beschlossene Maßnahme.
- Formuliere eine konkrete ausführbare Handlung.
- Keine bereits erledigte Handlung nennen.
- Keine Frist, Zuständigkeit, Verpflichtung oder Entscheidung erfinden.
- Wenn kein belastbarer nächster Schritt bestimmbar ist, verwende null.

Zeitliche Trennung:

`latest_development`
= Was ist zuletzt tatsächlich passiert?

`next_required_action`
= Was ist jetzt als Nächstes zu tun?

Beide Felder dürfen nicht dasselbe Ereignis oder dieselbe Handlung lediglich unterschiedlich formulieren.

`action_justification`
= erkläre knapp, welche belegten Tatsachen den vorgeschlagenen nächsten Schritt tragen.

`uncertainty_notes`
= offene Fragen, fehlende Informationen, widersprüchliche Angaben oder Punkte, die vor einer Entscheidung geprüft werden müssen.

Eine nicht belastbar belegte Handlung oder Frist ist null.

Bewerte `suggested_risk` als aktuelles Restrisiko (High/Medium/Low), nicht als historisches Maximum, und begründe es.

Bestimme `suggested_status` aus der neuesten Evidenz (New/Under Review/In Progress/Waiting/Completed/Critical). Ein Vergleich mit wesentlicher offener Erfüllung ist noch nicht Completed.

Neuere bestätigte Evidenz kann ältere Forderungen, Fristen, Maßnahmen und Risikobewertungen ersetzen.

Jeder Eintrag in `document_facts` muss über `document_fact_citations` auf seine konkrete Belegstelle zurückführbar sein.

Nutze `supporting_chunk_ids` und `relevant_documents` ausschließlich für tatsächlich verwendete Quellen. Interne IDs gehören niemals in den Fließtext.

Handlung, Risiko und Status bleiben KI-Vorschläge.

{HUMAN_REVIEW_RULE}
""".strip()
