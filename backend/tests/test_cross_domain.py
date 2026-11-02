import unittest
from unittest.mock import patch
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT
from app.services.case_qa import retrieve_case_evidence

class CrossDomainReliabilityTests(unittest.TestCase):
    def test_domain_neutral_evidence_rules(self):
        for phrase in ("technische Störungen", "Personalvorgänge", "Bauprojekte", "Versicherungsfälle", "beweisen keine Ursache", "nicht geschehen"):
            self.assertIn(phrase, CHAT_CONVERSATIONAL_PROMPT)

    def test_existing_adaptive_depth_preserved(self):
        self.assertIn("ADAPTIVE ANTWORTTIEFE", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("nicht als nummerierte Chronologie", CHAT_CONVERSATIONAL_PROMPT)

    def test_investigative_questions_get_three_angles(self):
        questions = (
            "Welche Ursachen hatte der technische Ausfall?",
            "Warum gab es einen Konflikt im Personalteam?",
            "Analysiere die Bauverzögerungen.",
            "Welche Schäden sind beim Versicherungsfall dokumentiert?",
            "Welche Widersprüche gab es im Projektverlauf?",
        )
        for question in questions:
            with self.subTest(question=question), patch("app.services.case_qa.create_query_embedding", side_effect=lambda x: x), patch("app.services.case_qa.retrieve_chunks", return_value=[]) as retrieve:
                retrieve_case_evidence(db=None, user=None, case_id=1, question=question)
                self.assertEqual(retrieve.call_count, 3)

    def test_simple_fact_question_gets_one_angle(self):
        with patch("app.services.case_qa.create_query_embedding", side_effect=lambda x: x), patch("app.services.case_qa.retrieve_chunks", return_value=[]) as retrieve:
            retrieve_case_evidence(db=None, user=None, case_id=1, question="Wann wurde die Rechnung erstellt?")
            self.assertEqual(retrieve.call_count, 1)
