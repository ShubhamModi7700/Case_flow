"""Consolidated regression tests; original test functions preserved.

Sources: test_consistency_fix.py, test_cross_domain.py, test_payment_consistency.py, test_shared_case_list_sql.py, test_risk_ownership_regression.py
"""


# ---- From test_consistency_fix.py ----
import unittest

from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT
from app.services.case_qa import retrieval_question


class Phase2ConsistencyFixTests(unittest.TestCase):
    def test_retrieval_scope_is_not_equated_with_case_inventory(self):
        self.assertIn("im gesamten Fall nicht vorhanden", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("in den aktuell ausgewerteten Auszügen nicht enthalten", CHAT_CONVERSATIONAL_PROMPT)

    def test_bold_section_labels_and_lists_are_optional(self):
        self.assertIn("Überschriften oder Fettdruck nur bei ausdrücklich gewünschtem Bericht", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Listen nur bei ausdrücklichem Wunsch oder echtem Verständlichkeitsgewinn", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Nummerierung dann einheitlich und fortlaufend", CHAT_CONVERSATIONAL_PROMPT)

    def test_followup_question_is_preserved(self):
        self.assertEqual(
            retrieval_question("Aktuelle Frage: Welche Nachweise fehlen?", "question"),
            "Welche Nachweise fehlen?",
        )


if __name__ == "__main__":
    unittest.main()


# ---- From test_cross_domain.py ----
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


# ---- From test_payment_consistency.py ----
import unittest

from app.services.case_qa import _correct_unproven_payment_wording


class PaymentConsistencyTests(unittest.TestCase):
    def test_speculative_payment_contradicting_missing_proof_is_corrected(self):
        answer = (
            "Die Quartalsrate wurde offenbar nicht storniert, sondern separat bezahlt "
            "und vom Ablösebetrag abgezogen. "
            "Ein tatsächlicher Zahlungseingang ist nicht nachgewiesen."
        )
        fixed = _correct_unproven_payment_wording(answer)
        self.assertIn("separat abgerechnet", fixed)
        self.assertNotIn("separat bezahlt", fixed)
        self.assertIn("nicht nachgewiesen", fixed)

    def test_payment_statement_without_explicit_contradiction_is_preserved(self):
        answer = "Die Rechnung wurde offenbar nicht storniert, sondern separat bezahlt."
        self.assertEqual(_correct_unproven_payment_wording(answer), answer)

    def test_unrelated_payment_status_remains_unchanged(self):
        answer = "Eine Zahlung ist nicht belegt. Die Rechnung wurde erstellt."
        self.assertEqual(_correct_unproven_payment_wording(answer), answer)


# ---- From test_shared_case_list_sql.py ----
"""Shared dashboard and restricted editing regression tests."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from app import models
from app.services.case_access import scope_case_query, can_view_case, can_edit_case


def test_regular_user_sees_all_cases_without_distinct_or_access_join():
    user = models.User(id=7, role="User")
    query = scope_case_query(Session().query(models.Case), user)
    query = query.order_by((models.Case.id + 1).desc())
    sql = str(query.statement.compile(dialect=postgresql.dialect())).upper()
    assert "DISTINCT" not in sql
    assert "CASE_ACCESS" not in sql
    assert "ORDER BY" in sql


def test_regular_user_can_view_unassigned_case():
    assert can_view_case(Session(), models.User(id=7, role="User"), 123)


def test_manager_can_edit_any_case():
    assert can_edit_case(Session(), models.User(id=1, role="Manager"), 123)


def test_regular_user_without_assignment_cannot_edit():
    class NoAccessQuery:
        def filter(self, *args): return self
        def first(self): return None
    class NoAccessSession:
        def query(self, *args): return NoAccessQuery()
    assert not can_edit_case(NoAccessSession(), models.User(id=7, role="User"), 123)


# ---- From test_risk_ownership_regression.py ----
from types import SimpleNamespace
from app.services.risk import calculate_case_risk


def _case(**overrides):
    values = dict(title='Umfirmierung', description='', management_summary='',
                  risk_reason='', next_action='Anschreiben prüfen', status='New',
                  primary_deadline=None, category='Other', responsible_person='',
                  financial_amount=None, tasks=[])
    values.update(overrides)
    return SimpleNamespace(**values)


def test_missing_owner_alone_not_high():
    result = calculate_case_risk(_case())
    assert result.level != 'High'
    assert 'Fallverantwortung' in result.reason


def test_actual_deadline_still_high():
    from datetime import date, timedelta
    result = calculate_case_risk(_case(primary_deadline=date.today() - timedelta(days=1)))
    assert result.level == 'High'


def test_owner_does_not_override_manual_risk():
    case = _case(risk='Low')
    from app.services.risk import refresh_risk_suggestion
    refresh_risk_suggestion(case)
    assert case.risk == 'Low'

