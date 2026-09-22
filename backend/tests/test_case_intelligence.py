from app import schemas
from app.services.ai_audit import referenced_source_ids
from app.services.case_qa import validate_answer_sources


def _sources():
    return [
        {"source_id": "S1", "chunk_id": 1, "document_id": 10, "filename": "beleg.pdf"},
        {"source_id": "S2", "chunk_id": 2, "document_id": 11, "filename": "mail.msg"},
    ]


def test_intelligence_removes_invalid_source_ids():
    result = schemas.CaseAssistantModelAnswer(
        answer="Fallübersicht [S1] [S99]",
        intelligence=schemas.AssistantCaseIntelligence(
            key_facts=[
                schemas.AssistantEvidenceStatement(text="Belegt", source_ids=["S1"]),
                schemas.AssistantEvidenceStatement(text="Nicht belegt", source_ids=["S99"]),
            ],
            key_events=[schemas.AssistantChronologyEvent(date="2025-09", event="Übergabe", source_ids=["S2", "S99"])],
        ),
    )
    validated = validate_answer_sources(result, _sources())
    assert validated.intelligence is not None
    assert len(validated.intelligence.key_facts) == 1
    assert validated.intelligence.key_events[0].source_ids == ["S2"]
    assert "[S99]" not in validated.answer
    assert "Nicht belegt" in validated.unsupported_statements


def test_intelligence_sources_are_audited():
    result = schemas.CaseAssistantModelAnswer(
        answer="Übersicht",
        intelligence=schemas.AssistantCaseIntelligence(
            key_facts=[schemas.AssistantEvidenceStatement(text="Fakt", source_ids=["S1"])],
            evidence_map=[schemas.AssistantEvidenceLink(claim="Beleg", source_ids=["S2"])],
        ),
    )
    assert referenced_source_ids(result) == {"S1", "S2"}
