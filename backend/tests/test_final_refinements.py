import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT

class Phase34FinalRefinementsTests(unittest.TestCase):
    def test_natural_paragraphs_not_repeated_numbering(self):
        self.assertIn("nicht als nummerierte Chronologie", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Nummerierung dann einheitlich und fortlaufend", CHAT_CONVERSATIONAL_PROMPT)

    def test_arithmetic_pattern_not_documented_cause(self):
        self.assertIn("beweist weder die Kalkulationsmethode", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("keine unbelegten Ursachen", CHAT_CONVERSATIONAL_PROMPT)

    def test_financial_comparability_and_payment_proof(self):
        self.assertIn("Netto-/Bruttobasis", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Eine Rechnung oder rechnerisch passende Differenz ist kein Zahlungs-, Buchungs- oder Verrechnungsnachweis", CHAT_CONVERSATIONAL_PROMPT)

    def test_adaptive_depth_preserved(self):
        self.assertIn("ADAPTIVE ANTWORTTIEFE", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("punktuelle Faktenfragen direkt und knapp", CHAT_CONVERSATIONAL_PROMPT)
