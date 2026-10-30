import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT


class Phase2ReasoningRulesTests(unittest.TestCase):
    def test_distinguishes_revisions_conflicts_and_missing_evidence(self):
        prompt = CHAT_CONVERSATIONAL_PROMPT
        for phrase in ("KOMPAKTE FALLLOGIK", "echter Widerspruch", "aufeinanderfolgende Stände", "fehlende Bestätigung", "technischer Vorfall"):
            self.assertIn(phrase, prompt)


if __name__ == "__main__":
    unittest.main()
