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
