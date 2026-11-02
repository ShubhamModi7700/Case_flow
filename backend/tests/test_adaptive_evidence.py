import unittest
from unittest.mock import patch
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT
from app.services.case_qa import retrieve_case_evidence

class Phase34Tests(unittest.TestCase):
    def test_phase3_money_and_format_rules(self):
        self.assertIn("netto/brutto", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("kein Buchungs- oder Zahlungsbeleg", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Keine mehrfachen", CHAT_CONVERSATIONAL_PROMPT)

    def test_phase4_adaptive_rules(self):
        self.assertIn("PHASE 4 – ADAPTIVE ANTWORTTIEFE", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Punktuelle Faktenfrage", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("komplexe Untersuchungen", CHAT_CONVERSATIONAL_PROMPT)

    def test_why_question_gets_broad_evidence_angles(self):
        with patch("app.services.case_qa.create_query_embedding", side_effect=lambda s: s), patch("app.services.case_qa.retrieve_chunks", return_value=[]) as retrieval:
            retrieve_case_evidence(db=None, user=None, case_id=1, question="Warum hat sich das Projekt verzögert?")
            self.assertEqual(retrieval.call_count, 3)

    def test_specific_date_question_stays_focused(self):
        with patch("app.services.case_qa.create_query_embedding", side_effect=lambda s: s), patch("app.services.case_qa.retrieve_chunks", return_value=[]) as retrieval:
            retrieve_case_evidence(db=None, user=None, case_id=1, question="Wann wurde die Rechnung erstellt?")
            self.assertEqual(retrieval.call_count, 1)
