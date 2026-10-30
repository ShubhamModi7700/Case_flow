import unittest

from app import schemas
from app.services.case_qa import build_sources, build_task_request_text, validate_answer_sources
from app.services.ai_audit import referenced_source_ids


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


class Phase5DAuditTests(unittest.TestCase):
    def test_referenced_source_ids_collects_only_sources_present_in_validated_output(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Antwort [S1].",
            claims=[
                schemas.AssistantEvidenceStatement(text="Belegt", source_ids=["S2"]),
            ],
            chronology=[
                schemas.AssistantChronologyEvent(
                    date="18.09.2025",
                    event="Übergabe",
                    source_ids=["S3"],
                )
            ],
        )

        self.assertEqual(referenced_source_ids(result), {"S1", "S2", "S3"})


class Phase5FBriefEvidenceTests(unittest.TestCase):
    def test_brief_context_is_included_in_task_request(self):
        context = schemas.AssistantBriefContext(
            client="MVI Proplant Nord GmbH",
            role="Mandantin",
            recipient="Amtsgericht Wolfsburg",
            document_type="Schriftsatz",
            objective="Fehlenden Erkenntnisgewinn der Zeugenvernehmung darstellen",
            additional_instructions="Nur freigegebene Belege verwenden.",
        )
        text = build_task_request_text(
            question="Stelle ein Beweispaket zusammen.",
            task_type="brief_evidence",
            brief_context=context,
        )
        self.assertIn("MVI Proplant Nord GmbH", text)
        self.assertIn("Amtsgericht Wolfsburg", text)
        self.assertIn("Fehlenden Erkenntnisgewinn", text)

    def test_invalid_brief_package_sources_are_removed(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Beweispaket [S1].",
            brief_evidence_package=schemas.AssistantBriefEvidencePackage(
                task_summary="Test",
                established_facts=[
                    schemas.AssistantEvidenceStatement(text="Belegt", source_ids=["S1"]),
                    schemas.AssistantEvidenceStatement(text="Erfunden", source_ids=["S99"]),
                ],
                key_evidence=[
                    schemas.AssistantEvidenceLink(claim="Beleg", relevance="Relevant", source_ids=["S1"])
                ],
            ),
        )
        validated = validate_answer_sources(
            result,
            [{"source_id": "S1", "chunk_id": 1, "document_id": 1, "filename": "a.pdf", "content": "x"}],
        )
        self.assertEqual(
            [item.text for item in validated.brief_evidence_package.established_facts],
            ["Belegt"],
        )
        self.assertIn("Erfunden", validated.unsupported_statements)

    def test_audit_collects_brief_package_source_ids(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="",
            brief_evidence_package=schemas.AssistantBriefEvidencePackage(
                established_facts=[
                    schemas.AssistantEvidenceStatement(text="Belegt", source_ids=["S4"])
                ],
                key_evidence=[
                    schemas.AssistantEvidenceLink(claim="Beleg", source_ids=["S5"])
                ],
            ),
        )
        self.assertEqual(referenced_source_ids(result), {"S4", "S5"})


class Phase5GBriefOutlineTests(unittest.TestCase):
    def test_brief_outline_context_is_included_in_task_request(self):
        context = schemas.AssistantBriefContext(
            client="MVI Proplant Nord GmbH",
            recipient="Amtsgericht Wolfsburg",
            objective="Übergabe der Buchhaltungsunterlagen darstellen",
        )
        text = build_task_request_text(
            question="Erstelle eine Gliederung.",
            task_type="brief_outline",
            brief_context=context,
        )
        self.assertIn("MVI Proplant Nord GmbH", text)
        self.assertIn("Amtsgericht Wolfsburg", text)

    def test_invalid_outline_sources_are_removed(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Gliederung [S1].",
            brief_outline=schemas.AssistantBriefOutline(
                title="Schriftsatzgliederung",
                sections=[
                    schemas.AssistantBriefOutlineSection(
                        heading="Sachverhalt",
                        factual_basis=[
                            schemas.AssistantEvidenceStatement(text="Belegt", source_ids=["S1"]),
                            schemas.AssistantEvidenceStatement(text="Erfunden", source_ids=["S99"]),
                        ],
                        evidence_notes=[
                            schemas.AssistantEvidenceLink(claim="Nachweis", source_ids=["S1"])
                        ],
                    )
                ],
            ),
        )
        validated = validate_answer_sources(
            result,
            [{"source_id": "S1", "chunk_id": 1, "document_id": 1, "filename": "a.pdf", "content": "x"}],
        )
        section = validated.brief_outline.sections[0]
        self.assertEqual([item.text for item in section.factual_basis], ["Belegt"])
        self.assertIn("Erfunden", validated.unsupported_statements)

    def test_audit_collects_outline_source_ids(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="",
            brief_outline=schemas.AssistantBriefOutline(
                title="Gliederung",
                sections=[
                    schemas.AssistantBriefOutlineSection(
                        heading="Sachverhalt",
                        factual_basis=[schemas.AssistantEvidenceStatement(text="Fakt", source_ids=["S6"])],
                        evidence_notes=[schemas.AssistantEvidenceLink(claim="Beleg", source_ids=["S7"])],
                    )
                ],
            ),
        )
        self.assertEqual(referenced_source_ids(result), {"S6", "S7"})


class Phase5HBriefDraftTests(unittest.TestCase):
    def test_brief_draft_context_is_included_in_task_request(self):
        context = schemas.AssistantBriefContext(
            client="MVI Proplant Nord GmbH",
            recipient="Amtsgericht Wolfsburg",
            objective="Übergabe der Buchhaltungsunterlagen darstellen",
        )
        text = build_task_request_text(
            question="Erstelle einen KI-Entwurf.",
            task_type="brief_draft",
            brief_context=context,
        )
        self.assertIn("MVI Proplant Nord GmbH", text)
        self.assertIn("Amtsgericht Wolfsburg", text)

    def test_invalid_draft_sources_are_removed(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Entwurf erstellt [S1].",
            brief_draft=schemas.AssistantBriefDraft(
                title="KI-Entwurf",
                introduction=[schemas.AssistantEvidenceStatement(text="Belegt", source_ids=["S1"])],
                sections=[
                    schemas.AssistantBriefDraftSection(
                        heading="Sachverhalt",
                        paragraphs=[
                            schemas.AssistantEvidenceStatement(text="Erfunden", source_ids=["S99"]),
                            schemas.AssistantEvidenceStatement(text="Belegt 2", source_ids=["S1"]),
                        ],
                    )
                ],
            ),
        )
        validated = validate_answer_sources(
            result,
            [{"source_id": "S1", "chunk_id": 1, "document_id": 1, "filename": "a.pdf", "content": "x"}],
        )
        self.assertEqual(validated.brief_draft.draft_label, "KI-ENTWURF")
        self.assertEqual([x.text for x in validated.brief_draft.sections[0].paragraphs], ["Belegt 2"])
        self.assertIn("Erfunden", validated.unsupported_statements)

    def test_audit_collects_draft_source_ids(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="",
            brief_draft=schemas.AssistantBriefDraft(
                title="Entwurf",
                introduction=[schemas.AssistantEvidenceStatement(text="Intro", source_ids=["S8"])],
                sections=[schemas.AssistantBriefDraftSection(
                    heading="Sachverhalt",
                    paragraphs=[schemas.AssistantEvidenceStatement(text="Absatz", source_ids=["S9"])],
                )],
                conclusion=[schemas.AssistantEvidenceStatement(text="Schluss", source_ids=["S10"])],
            ),
        )
        self.assertEqual(referenced_source_ids(result), {"S8", "S9", "S10"})



class Phase5IRedReviewTests(unittest.TestCase):
    def test_red_review_context_is_included_in_task_request(self):
        context = schemas.AssistantBriefContext(client="MVI Proplant Nord GmbH", objective="Übergabe der Unterlagen argumentieren")
        text = build_task_request_text(question="Red Review", task_type="brief_review", brief_context=context)
        self.assertIn("MVI Proplant Nord GmbH", text)
        self.assertIn("Übergabe der Unterlagen", text)

    def test_invalid_red_review_sources_are_removed(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Review [S1] [S99].",
            brief_review=schemas.AssistantBriefReview(
                counterarguments=[
                    schemas.AssistantBriefCounterargument(argument="Belegt", source_ids=["S1"]),
                    schemas.AssistantBriefCounterargument(argument="Erfunden", source_ids=["S99"]),
                ],
                factual_risks=[schemas.AssistantBriefRisk(risk="Risiko", source_ids=["S1"])],
            ),
        )
        validated = validate_answer_sources(result, [{"source_id":"S1","chunk_id":1,"document_id":1,"filename":"a.pdf","content":"x"}])
        self.assertEqual(len(validated.brief_review.counterarguments), 1)
        self.assertEqual(len(validated.brief_review.factual_risks), 1)
        self.assertIn("Erfunden", validated.unsupported_statements)
        self.assertNotIn("S99", validated.answer)

    def test_red_review_sources_are_audited(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Review.",
            brief_review=schemas.AssistantBriefReview(
                counterarguments=[schemas.AssistantBriefCounterargument(argument="Gegenargument", source_ids=["S2"])],
                factual_risks=[schemas.AssistantBriefRisk(risk="Risiko", source_ids=["S3"])],
                contradictions=[schemas.AssistantEvidenceStatement(text="Widerspruch", source_ids=["S4"])],
            ),
        )
        self.assertEqual(referenced_source_ids(result), {"S2", "S3", "S4"})

if __name__ == "__main__":
    unittest.main()


class ReportFinanceValidationTests(unittest.TestCase):
    def test_financial_items_require_valid_document_sources(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Finanzielle Positionen",
            report_finances=[
                schemas.AssistantReportFinancialItem(position="Rechnung", amount="100 EUR netto", status="Zahlung nicht belegt", source_ids=["S1"]),
                schemas.AssistantReportFinancialItem(position="Erfundene Zahlung", amount="100 EUR", status="bezahlt", source_ids=["S99"]),
            ],
        )
        validated = validate_answer_sources(result, [{"source_id": "S1", "chunk_id": 1, "document_id": 1, "filename": "invoice.pdf", "content": "Rechnung"}])
        self.assertEqual(len(validated.report_finances), 1)
        self.assertEqual(validated.report_finances[0].position, "Rechnung")
        self.assertIn("Erfundene Zahlung", validated.unsupported_statements)

class ReportClassificationTests(unittest.TestCase):
    def test_unexplained_deadline_status_becomes_unclear(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Beleg [S1]",
            report_deadlines=[schemas.AssistantReportDeadline(
                date="2026-10-31", description="Angebotsfrist",
                date_type="offer_expiry", status="historical", source_ids=["S1"]
            )],
        )
        validated = validate_answer_sources(result, [{
            "source_id": "S1", "chunk_id": 1, "document_id": 1,
            "filename": "angebot.pdf", "content": "Angebotsfrist",
        }])
        self.assertEqual(validated.report_deadlines[0].status, "unclear")
        self.assertTrue(validated.report_deadlines[0].status_reason)

    def test_finance_category_survives_source_validation(self):
        result = schemas.CaseAssistantModelAnswer(
            answer="Rechnung [S1]",
            report_finances=[schemas.AssistantReportFinancialItem(
                position="Rechnung", category="invoice", amount="100 EUR",
                status="Zahlung ungeklärt", source_ids=["S1"]
            )],
        )
        validated = validate_answer_sources(result, [{
            "source_id": "S1", "chunk_id": 1, "document_id": 1,
            "filename": "rechnung.pdf", "content": "Rechnung",
        }])
        self.assertEqual(validated.report_finances[0].category, "invoice")


class ChatConsistencyRetrievalTests(unittest.TestCase):
    def test_primary_evidence_anchors_survive_secondary_search(self):
        from unittest.mock import patch
        from app.services.case_qa import retrieve_case_evidence

        def chunk(chunk_id, document_id, similarity):
            return {"chunk_id": chunk_id, "document_id": document_id,
                    "similarity": similarity, "content": "evidence"}

        primary = [chunk(i, 1, 0.90 - i * 0.01) for i in range(1, 5)]
        secondary = [chunk(i, i, 0.99 - i * 0.01) for i in range(5, 17)]
        with patch("app.services.case_qa.create_query_embedding", return_value=[0.1]), \
             patch("app.services.case_qa.retrieve_chunks", side_effect=[primary, secondary]):
            result = retrieve_case_evidence(
                db=None, user=None, case_id=1, question="Was ist passiert?",
                task_type="question", limit=8,
            )
        self.assertEqual([item["chunk_id"] for item in result[:4]], [1, 2, 3, 4])
        self.assertEqual(len(result), 8)
