import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT

class Phase2NaturalChatStyleTests(unittest.TestCase):
    def test_no_fixed_heading_template(self):
        self.assertIn("Verwende KEINE routinemäßigen oder festen Abschnittsüberschriften", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("natürlich fließendem Deutsch", CHAT_CONVERSATIONAL_PROMPT)
        self.assertNotIn("Verwende für wenige zentrale Abschnitte kurze fett markierte Bezeichnungen", CHAT_CONVERSATIONAL_PROMPT)

    def test_depth_and_evidence_are_preserved(self):
        self.assertIn("kurze Faktenfragen knapp und direkt", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Belegprüfung, Gegenargumente", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("im gesamten Fall nicht vorhanden", CHAT_CONVERSATIONAL_PROMPT)
