import unittest

from app import schemas
from app.services.case_qa import build_sources, validate_answer_sources


class CaseQATests(unittest.TestCase):
    def test_build_sources_uses_server_owned_ids_and_metadata(self):
        sources = build_sources(
            [
                {
                    "chunk_id": 10,
                    "document_id": 20,
                    "file_name": "mail.eml",
                    "content": "Beleg",
                    "page_number": None,
                    "sheet_name": None,
                    "email_section": "message",
                    "metadata": {
                        "document_date": "18.09.2025",
                        "sender": "Max Mustermann",
                    },
                }
            ]
        )
        self.assertEqual(sources[0]["source_id"], "S1")
        self.assertEqual(sources[0]["filename"], "mail.eml")
        self.assertEqual(sources[0]["sender"], "Max Mustermann")
        self.assertEqual(sources[0]["document_date"], "18.09.2025")

    def test_invalid_model_citations_are_not_returned_as_supported_claims(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Belegt [S1], erfunden [S99].",
            claims=[
                schemas.AssistantEvidenceStatement(text="Belegt", source_ids=["S1"]),
                schemas.AssistantEvidenceStatement(text="Nicht belegt", source_ids=["S99"]),
            ],
        )
        validated = validate_answer_sources(
            result,
            [
                {
                    "source_id": "S1",
                    "chunk_id": 1,
                    "document_id": 1,
                    "filename": "a.pdf",
                    "content": "x",
                }
            ],
        )
        self.assertEqual([claim.text for claim in validated.claims], ["Belegt"])
        self.assertIn("Nicht belegt", validated.unsupported_statements)
        self.assertNotIn("S99", validated.answer)


class Phase5CStructuredAnalysisTests(unittest.TestCase):
    def test_invalid_specialized_source_ids_are_removed(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Chronologie [S1] und erfunden [S99].",
            chronology=[
                schemas.AssistantChronologyEvent(
                    date="18.09.2025",
                    event="Unterlagen wurden übermittelt.",
                    source_ids=["S1"],
                ),
                schemas.AssistantChronologyEvent(
                    date="19.09.2025",
                    event="Unbelegtes Ereignis.",
                    source_ids=["S99"],
                ),
            ],
            evidence=[
                schemas.AssistantEvidenceLink(
                    claim="Übergabe belegt",
                    relevance="Bestätigt die Übersendung.",
                    source_ids=["S1"],
                )
            ],
            entities=[
                schemas.AssistantEntity(
                    name="Max Mustermann",
                    entity_type="Person",
                    role="Absender",
                    role_is_explicit=True,
                    source_ids=["S1"],
                )
            ],
        )
        validated = validate_answer_sources(
            result,
            [
                {
                    "source_id": "S1",
                    "chunk_id": 1,
                    "document_id": 1,
                    "filename": "mail.eml",
                    "content": "x",
                }
            ],
        )
        self.assertEqual(len(validated.chronology), 1)
        self.assertEqual(len(validated.evidence), 1)
        self.assertEqual(len(validated.entities), 1)
        self.assertIn("Unbelegtes Ereignis.", validated.unsupported_statements)
        self.assertNotIn("S99", validated.answer)


if __name__ == "__main__":
    unittest.main()
