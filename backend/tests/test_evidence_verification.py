import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT

class Phase3EvidenceVerificationTests(unittest.TestCase):
    def test_checks_evidence_content_not_just_citation(self):
        self.assertIn("INHALT der zitierten Evidenz", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("gültige Quellen-ID allein", CHAT_CONVERSATIONAL_PROMPT)

    def test_distinguishes_claims_actions_and_revisions(self):
        self.assertIn("Parteibehauptung", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("keinen Zahlungseingang", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("spätere Änderungen", CHAT_CONVERSATIONAL_PROMPT)

    def test_preserves_natural_style(self):
        self.assertIn("ohne feste Überschriften", CHAT_CONVERSATIONAL_PROMPT)
