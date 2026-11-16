"""Consolidated regression tests; original test functions preserved.

Sources: test_case_intelligence.py, test_case_intelligence_persistence.py, test_case_work_status.py
"""


# ---- From test_case_intelligence.py ----
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


# ---- From test_case_intelligence_persistence.py ----
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.case_intelligence_persistence import build_input_fingerprint, snapshot_is_current


def _case(**changes):
    values = dict(
        id=2, title="Testfall", company="Example GmbH", department=None,
        category="Legal", external_contact=None, responsible_person="A",
        status="Open", risk="Medium", description="Test", next_action="Prüfen",
        primary_deadline=date(2026, 9, 30), follow_up_date=None,
        updated_at=datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc),
    )
    values.update(changes)
    return SimpleNamespace(**values)


def _task(**changes):
    values = dict(
        id=7, title="Unterlagen prüfen", description=None, category="Prüfung",
        responsible_person="A", due_date=date(2026, 9, 28), priority="Medium",
        status="Open", created_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
    )
    values.update(changes)
    return SimpleNamespace(**values)


def _document(**changes):
    values = dict(
        id=3, file_name="mail.msg", processing_status="Ready", embedding_status="Ready",
        chunk_count=3, uploaded_at=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc),
        processed_at=datetime(2026, 9, 20, 9, 5, tzinfo=timezone.utc),
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_fingerprint_is_stable_for_same_authoritative_state():
    first = build_input_fingerprint(case=_case(), tasks=[_task()], documents=[_document()])
    second = build_input_fingerprint(case=_case(), tasks=[_task()], documents=[_document()])
    assert first == second
    assert len(first) == 64


def test_fingerprint_changes_when_task_or_document_state_changes():
    original = build_input_fingerprint(case=_case(), tasks=[_task()], documents=[_document()])
    task_changed = build_input_fingerprint(case=_case(), tasks=[_task(status="Completed")], documents=[_document()])
    document_changed = build_input_fingerprint(case=_case(), tasks=[_task()], documents=[_document(chunk_count=4)])
    assert task_changed != original
    assert document_changed != original


def test_snapshot_currentness_uses_exact_fingerprint():
    snapshot = SimpleNamespace(input_fingerprint="abc")
    assert snapshot_is_current(snapshot, fingerprint="abc") is True
    assert snapshot_is_current(snapshot, fingerprint="def") is False


# ---- From test_case_work_status.py ----
from datetime import date
from types import SimpleNamespace

from app.services.case_work_status import build_case_work_status, is_explicit_decision_task


def task(**overrides):
    data = dict(
        id=1,
        title="Unterlagen prüfen",
        description=None,
        category=None,
        responsible_person=None,
        due_date=None,
        priority="Medium",
        status="Open",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_work_status_only_returns_open_tasks_and_marks_overdue():
    case = SimpleNamespace(
        primary_deadline=date(2026, 9, 10),
        follow_up_date=date(2026, 9, 20),
        next_action="Rückmeldung einholen",
    )
    result = build_case_work_status(
        case=case,
        tasks=[
            task(id=1, due_date=date(2026, 9, 16)),
            task(id=2, status="Completed", due_date=date(2026, 9, 1)),
        ],
        today=date(2026, 9, 17),
    )
    assert result.primary_deadline_is_overdue is True
    assert [item.id for item in result.open_tasks] == [1]
    assert result.open_tasks[0].is_overdue is True


def test_open_decisions_require_explicit_category():
    case = SimpleNamespace(primary_deadline=None, follow_up_date=None, next_action=None)
    result = build_case_work_status(
        case=case,
        tasks=[
            task(id=1, title="Freigabe entscheiden", category=None),
            task(id=2, title="Vergleich freigeben", category="Entscheidung"),
        ],
        today=date(2026, 9, 17),
    )
    assert [item.task_id for item in result.open_decisions] == [2]
    assert is_explicit_decision_task(task(category="Decision")) is True



def test_documented_obligations_require_valid_sources():
    result = schemas.CaseAssistantModelAnswer(
        answer="Überblick",
        intelligence=schemas.AssistantCaseIntelligence(
            documented_obligations=[
                schemas.AssistantEvidenceStatement(text="Vereinbarte Leistung", source_ids=["S1"]),
                schemas.AssistantEvidenceStatement(text="Unbelegte Pflicht", source_ids=["S99"]),
            ]
        ),
    )
    validated = validate_answer_sources(result, _sources())
    assert [x.text for x in validated.intelligence.documented_obligations] == ["Vereinbarte Leistung"]
    assert "Unbelegte Pflicht" in validated.unsupported_statements
    assert "S1" in referenced_source_ids(validated)


def test_completed_tasks_are_excluded_regardless_of_case_or_language():
    case = SimpleNamespace(primary_deadline=None, follow_up_date=None, next_action=None)
    result = build_case_work_status(
        case=case,
        tasks=[task(id=1, status="completed"), task(id=2, status="Erledigt"),
               task(id=3, status="Open")],
        today=date(2026, 9, 17),
    )
    assert [item.id for item in result.open_tasks] == [3]
