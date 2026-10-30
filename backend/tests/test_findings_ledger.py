import unittest
from types import SimpleNamespace
from app.services.findings_ledger import build_findings_ledger


class FindingsLedgerTests(unittest.TestCase):
    def test_source_validation_and_deduplication(self):
        item = lambda text, ids: SimpleNamespace(text=text, source_ids=ids)
        answer = SimpleNamespace(
            claims=[item("  Delivery confirmed ", ["S1", "FAKE"]), item("Delivery confirmed", ["S1"])],
            contradictions=[item("Two different dates", ["S1", "S2"])],
            missing_information=["Payment receipt unavailable"],
        )
        sources = [{"source_id": "S1", "document_id": 10}, {"source_id": "S2", "document_id": 20}]
        findings = build_findings_ledger(answer, sources)
        self.assertEqual([f.kind for f in findings], ["documented", "conflict", "missing_evidence"])
        self.assertEqual(findings[0].source_ids, ("S1",))
        self.assertEqual(findings[1].document_ids, (10, 20))
        self.assertEqual(findings[2].source_ids, ())

    def test_domain_neutral_incident_findings(self):
        item = lambda text, ids: SimpleNamespace(text=text, source_ids=ids)
        answer = SimpleNamespace(
            claims=[item("Service unavailable at 09:00", ["S1"])],
            contradictions=[item("Monitoring and incident report disagree on recovery time", ["S1", "S2"])],
            missing_information=["Root cause not yet established"],
        )
        sources = [
            {"source_id": "S1", "document_id": 101},
            {"source_id": "S2", "document_id": 102},
        ]
        findings = build_findings_ledger(answer, sources)
        self.assertEqual([f.kind for f in findings], ["documented", "conflict", "missing_evidence"])
        self.assertEqual(findings[1].document_ids, (101, 102))

    def test_unsupported_claim_is_excluded(self):
        answer = SimpleNamespace(claims=[SimpleNamespace(text="Unsupported", source_ids=["S99"])], contradictions=[], missing_information=[])
        self.assertEqual(build_findings_ledger(answer, []), [])


if __name__ == "__main__":
    unittest.main()
