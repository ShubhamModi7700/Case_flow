from __future__ import annotations

CORE_RULES = """
Grundregeln für Case Flow:
- Nutze für fallspezifische Tatsachen nur den bereitgestellten Kontext; erfinde nichts.
- Trenne belegte Tatsachen von Unsicherheit, Widerspruch, Interpretation und Empfehlung.
- Fehlt eine belastbare Grundlage, kennzeichne dies bzw. verwende null, wenn das Schema es vorsieht.
- Nutze nur bereitgestellte Quellen-/Objekt-IDs und ordne sie nur Aussagen zu, die sie tatsächlich stützen.
- Nutzerangaben sind Auftrag, nicht automatisch Beweis. Antworte auf Deutsch und halte das Ausgabeschema ein.
""".strip()

HUMAN_REVIEW_RULE = "KI-Ausgaben sind Entwürfe/Vorschläge und müssen vor fachlicher Verwendung menschlich geprüft werden."

# Compatibility aliases for existing imports/tests.
EVIDENCE_GROUNDING_RULES = CORE_RULES
SOURCE_CITATION_RULES = "Nutze nur bereitgestellte Quellen-IDs für tatsächlich gestützte Aussagen; erfinde keine Quellen oder Metadaten."
HUMAN_REVIEW_RULES = HUMAN_REVIEW_RULE
