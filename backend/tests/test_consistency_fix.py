import unittest

from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT
from app.services.case_qa import retrieval_question


class Phase2ConsistencyFixTests(unittest.TestCase):
    def test_retrieval_scope_is_not_equated_with_case_inventory(self):
        self.assertIn("im gesamten Fall nicht vorhanden", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("in den aktuell ausgewerteten Auszügen nicht enthalten", CHAT_CONVERSATIONAL_PROMPT)

    def test_bold_section_labels_and_lists_are_optional(self):
        self.assertIn("**Dokumentierter Stand:**", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("nur für echte Listen", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("fortlaufende Nummerierung", CHAT_CONVERSATIONAL_PROMPT)

    def test_followup_question_is_preserved(self):
        self.assertEqual(
            retrieval_question("Aktuelle Frage: Welche Nachweise fehlen?", "question"),
            "Welche Nachweise fehlen?",
        )


if __name__ == "__main__":
    unittest.main()
