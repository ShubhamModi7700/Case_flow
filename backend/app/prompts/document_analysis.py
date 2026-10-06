from __future__ import annotations

from app.prompts.common import CORE_RULES, HUMAN_REVIEW_RULE


DOCUMENT_ANALYSIS_PROMPT_VERSION = "document-analysis-v8"


SYSTEM_PROMPT = f"""
Analysiere das neue Dokument im Kontext des Falls und fülle das vorgegebene strukturierte Schema.

{CORE_RULES}

Das neue Dokument ist die neueste bereitgestellte Evidenz. Unterscheide historische Angaben von dem aktuell durch die Evidenz belegten Stand. Neuere bestätigte Erledigungen, Vergleiche, Zahlungen oder Änderungen können ältere Forderungen, Fristen, Maßnahmen und Risiken ersetzen.

Für `latest_development` gelten folgende Regeln:
- Beschreibe ausschließlich ein bereits eingetretenes, fallspezifisches Ereignis oder eine bereits erfolgte relevante Änderung.
- Wähle die zeitlich jüngste relevante Entwicklung, die durch die bereitgestellte Evidenz tatsächlich belegt ist.
- Das Upload-, Verarbeitungs-, Analyse- oder Indexierungsdatum eines Dokuments ist keine fachliche Entwicklung des Falls.
- Das neueste Dokument ist nicht automatisch die neueste Entwicklung: maßgeblich ist das Datum des darin belegten Ereignisses.
- Formuliere knapp: Was ist passiert, wer war beteiligt und wann, soweit dies belegt ist.
- Keine Empfehlung, keine zukünftige Handlung und keine bloße Vermutung in `latest_development`.
- Ist keine konkrete jüngste Entwicklung belastbar feststellbar, verwende null.

Für `proposed_next_action` gelten folgende Regeln:
- Beschreibe ausschließlich eine noch auszuführende zukünftige Handlung.
- Bestimme den unmittelbar nächsten konkreten Schritt aus dem aktuell belegten Fallstand.
- Bevorzuge ausdrücklich dokumentierte Anforderungen, offene Antworten, ausstehende Unterlagen, Prüfungen oder bereits angelegte Aufgaben.
- Ist der Schritt nicht ausdrücklich angeordnet, sondern aus der Evidenz abgeleitet, behandle ihn als KI-Vorschlag und nicht als bereits beschlossene Maßnahme.
- Erfinde keine Verpflichtung, Frist, Zuständigkeit oder Entscheidung.
- Nenne nicht mehrere spätere Schritte, wenn ein unmittelbar nächster Schritt eindeutig bestimmbar ist.
- Ist kein belastbarer nächster Schritt ableitbar, verwende null.

`latest_development` und `proposed_next_action` haben unterschiedliche zeitliche Funktionen und dürfen nicht dasselbe ausdrücken:

latest_development = Was ist bereits passiert?
proposed_next_action = Was muss bzw. sollte als Nächstes passieren?

Bewerte `suggested_risk` als aktuelles Restrisiko (High/Medium/Low) und `suggested_status` nach aktuellem Arbeitsstand (New/Under Review/In Progress/Waiting/Completed/Critical), jeweils mit Begründung.

Nur eindeutig noch offene Fristen übernehmen; sonst null.

Interne Dokument-/Chunk-IDs nur in strukturierten Quellenfeldern, nie im Fließtext.

{HUMAN_REVIEW_RULE}
""".strip()
