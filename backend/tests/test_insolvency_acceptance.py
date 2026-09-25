"""Step 16 acceptance coverage for the manager's insolvency scenario.

These tests are deterministic and do not call OpenAI or a live database. They
exercise the evidence/source contract that the live acceptance run depends on:
September/October 2025 accounting-record deliveries, email/attachment
provenance, relevance to witness examination, exact citations, and explicit
uncertainty for unsupported facts.
"""

from app import schemas
from app.services.ai_audit import referenced_source_ids
from app.services.case_qa import build_sources, public_sources, validate_answer_sources


def _acceptance_chunks():
    return [
        {
            "chunk_id": 1601,
            "document_id": 201,
            "file_name": "Mail_26-09-2025.eml",
            "content": "Anbei übersenden wir die Buchhaltungsunterlagen, insbesondere Kontenblätter und Buchungsjournal.",
            "page_number": None,
            "sheet_name": None,
            "email_section": "body",
            "metadata": {
                "source_filename": "Mail_26-09-2025.eml",
                "sender": "kanzlei@example.com",
                "document_date": "Fri, 26 Sep 2025 10:30:00 +0200",
            },
        },
        {
            "chunk_id": 1602,
            "document_id": 202,
            "file_name": "Mail_17-10-2025.eml",
            "content": "Die ergänzenden Buchhaltungsunterlagen für Oktober wurden heute übermittelt.",
            "page_number": None,
            "sheet_name": None,
            "email_section": "body",
            "metadata": {
                "source_filename": "Mail_17-10-2025.eml",
                "sender": "steuerbuero@example.com",
                "document_date": "Fri, 17 Oct 2025 14:15:00 +0200",
            },
        },
        {
            "chunk_id": 1603,
            "document_id": 202,
            "file_name": "Mail_17-10-2025.eml",
            "content": "Kontenblätter September/Oktober 2025; Buchungsjournal; OP-Liste.",
            "page_number": None,
            "sheet_name": None,
            "email_section": None,
            "metadata": {
                "source_filename": "Buchhaltung_Sep_Okt_2025.docx",
                "is_attachment": True,
                "parent_filename": "Mail_17-10-2025.eml",
                "root_email_filename": "Mail_17-10-2025.eml",
                "attachment_depth": 1,
                "sender": "steuerbuero@example.com",
                "document_date": "Fri, 17 Oct 2025 14:15:00 +0200",
            },
        },
        {
            "chunk_id": 1604,
            "document_id": 203,
            "file_name": "Zeugenvernehmung_Themen.pdf",
            "content": "Für die Zeugenvernehmung ist zu klären, wann und in welchem Umfang die Buchhaltungsunterlagen übergeben wurden.",
            "page_number": 2,
            "sheet_name": None,
            "email_section": None,
            "metadata": {"source_filename": "Zeugenvernehmung_Themen.pdf", "document_date": "2026-09-20"},
        },
    ]


def test_acceptance_sources_preserve_exact_delivery_and_attachment_provenance():
    sources = build_sources(_acceptance_chunks())

    assert [source["source_id"] for source in sources] == ["S1", "S2", "S3", "S4"]
    assert sources[0]["filename"] == "Mail_26-09-2025.eml"
    assert "26 Sep 2025" in sources[0]["document_date"]
    assert sources[1]["sender"] == "steuerbuero@example.com"
    assert sources[2]["filename"] == "Buchhaltung_Sep_Okt_2025.docx"
    assert sources[2]["is_attachment"] is True
    assert sources[2]["parent_filename"] == "Mail_17-10-2025.eml"
    assert sources[3]["page_number"] == 2

    public = public_sources(sources)
    assert public[2].root_email_filename == "Mail_17-10-2025.eml"
    assert public[3].page_number == 2


def test_acceptance_answer_connects_sep_oct_delivery_to_witness_issue_with_citations():
    sources = build_sources(_acceptance_chunks())
    model_answer = schemas.CaseAssistantModelAnswer(
        answer=(
            "Die Evidenz dokumentiert Übergaben von Buchhaltungsunterlagen im September [S1] "
            "und Oktober 2025 [S2][S3]. Die aktuelle Zeugenvernehmung betrifft Zeitpunkt und "
            "Umfang dieser Übergabe [S4]. Ein behaupteter vollständiger Zugang beim Insolvenzverwalter "
            "ist durch die vorliegenden Quellen nicht belegt [S99]."
        ),
        intelligence=schemas.AssistantCaseIntelligence(
            key_facts=[
                schemas.AssistantEvidenceStatement(text="Buchhaltungsunterlagen wurden am 26.09.2025 übersandt.", source_ids=["S1"]),
                schemas.AssistantEvidenceStatement(text="Ergänzende Buchhaltungsunterlagen wurden am 17.10.2025 übermittelt.", source_ids=["S2", "S3"]),
            ],
            key_events=[
                schemas.AssistantChronologyEvent(date="2025-09-26", event="Übersendung von Buchhaltungsunterlagen", source_ids=["S1"]),
                schemas.AssistantChronologyEvent(date="2025-10-17", event="Ergänzende Übermittlung einschließlich Kontenblättern/Buchungsjournal", source_ids=["S2", "S3"]),
            ],
            evidence_map=[
                schemas.AssistantEvidenceLink(
                    claim="Die September-/Oktober-Übergaben sind für die aktuelle Zeugenvernehmung relevant.",
                    relevance="Die Zeugenvernehmung soll Zeitpunkt und Umfang der Übergabe klären.",
                    source_ids=["S1", "S2", "S3", "S4"],
                )
            ],
            information_gaps=["Aus den vorliegenden Quellen folgt nicht sicher, ob sämtliche Unterlagen vollständig beim Insolvenzverwalter eingegangen sind."],
            unresolved_issues=["Vollständigkeit und tatsächlicher Zugang der übermittelten Unterlagen sind anhand weiterer Empfangsnachweise zu prüfen."],
        ),
        unsupported_statements=["Vollständiger Zugang beim Insolvenzverwalter ist nicht belegt."],
    )

    validated = validate_answer_sources(model_answer, sources)
    assert validated.intelligence is not None
    assert len(validated.intelligence.key_events) == 2
    assert validated.intelligence.evidence_map[0].source_ids == ["S1", "S2", "S3", "S4"]
    assert "[S99]" not in validated.answer
    assert validated.intelligence.information_gaps
    assert validated.intelligence.unresolved_issues
    assert referenced_source_ids(validated) == {"S1", "S2", "S3", "S4"}


def test_acceptance_rejects_invented_supporting_source():
    sources = build_sources(_acceptance_chunks())
    model_answer = schemas.CaseAssistantModelAnswer(
        answer="Eine Empfangsbestätigung belegt den vollständigen Zugang [S99].",
        claims=[schemas.AssistantEvidenceStatement(text="Vollständiger Zugang ist bestätigt.", source_ids=["S99"])],
    )

    validated = validate_answer_sources(model_answer, sources)
    assert validated.claims == []
    assert "[S99]" not in validated.answer
    assert "Vollständiger Zugang ist bestätigt." in validated.unsupported_statements


def test_acceptance_retrieval_query_is_not_date_spoon_fed():
    """The acceptance prompt must require discovery, not reveal Sep/Oct dates."""
    from scripts.run_insolvency_acceptance import DEFAULT_QUESTION

    normalized = DEFAULT_QUESTION.casefold()
    assert "september" not in normalized
    assert "oktober" not in normalized
    assert "2025-09" not in normalized
    assert "2025-10" not in normalized
    assert "buchhaltungsunterlagen" in normalized
    assert "ermittle selbständig" in normalized


def test_acceptance_month_detection_requires_accounting_context():
    """A random September document must not satisfy the accounting handover gate."""
    from scripts.run_insolvency_acceptance import (
        ACCOUNTING_TERMS,
        SEPTEMBER_PATTERNS,
        _matches_any,
    )

    unrelated = "Besprechung am 26.09.2025 über eine allgemeine Frist".casefold()
    accounting = "Am 26.09.2025 wurden Buchhaltungsunterlagen übergeben".casefold()

    assert _matches_any(unrelated, SEPTEMBER_PATTERNS)
    assert not any(term in unrelated for term in ACCOUNTING_TERMS)
    assert _matches_any(accounting, SEPTEMBER_PATTERNS)
    assert any(term in accounting for term in ACCOUNTING_TERMS)
