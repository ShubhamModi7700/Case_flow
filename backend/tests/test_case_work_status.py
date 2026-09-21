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
