import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT

class Phase34FinalRefinementsTests(unittest.TestCase):
    def test_natural_paragraphs_not_repeated_numbering(self):
        self.assertIn("KEINE nummerierte Chronologie", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Nummern korrekt fortlaufend", CHAT_CONVERSATIONAL_PROMPT)

    def test_arithmetic_pattern_not_documented_cause(self):
        self.assertIn("beweist weder die zugrunde liegende Kalkulationsmethode", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("keine unbelegten Ursachen", CHAT_CONVERSATIONAL_PROMPT)

    def test_financial_comparability_and_payment_proof(self):
        self.assertIn("dieselbe Netto-/Bruttobasis", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Eine Zahlungszusage oder Rechnung ist kein Zahlungsnachweis", CHAT_CONVERSATIONAL_PROMPT)

    def test_adaptive_depth_preserved(self):
        self.assertIn("PHASE 4 – ADAPTIVE ANTWORTTIEFE", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Punktuelle Faktenfrage", CHAT_CONVERSATIONAL_PROMPT)
