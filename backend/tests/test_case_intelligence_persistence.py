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
