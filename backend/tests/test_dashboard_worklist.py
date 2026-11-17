from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.routes import dashboard
from app.services.dashboard_worklist import berlin_today, build_worklist, preparation_lead_days


TODAY = date(2026, 11, 17)


def case(**changes):
    values = dict(id=1, title="Fall A", status="In Progress", is_archived=False,
                  risk="Low", responsible_person="Anna", next_action="Antwort prüfen",
                  primary_deadline=None, follow_up_date=None)
    values.update(changes)
    return SimpleNamespace(**values)


def task(**changes):
    values = dict(id=1, case_id=1, title="Unterlagen prüfen", status="Open",
                  priority="Medium", responsible_person="Ben", due_date=None)
    values.update(changes)
    return SimpleNamespace(**values)


def worklist(cases=None, tasks=None, lead=3):
    return build_worklist(cases=cases or [case()], tasks=tasks or [], today=TODAY, lead_days=lead)


@pytest.mark.parametrize("offset,in_today,in_week", [(-1, True, True), (0, True, True),
    (3, True, True), (4, False, True), (7, False, True), (8, False, True),
    (10, False, True), (11, False, False)])
def test_deadline_and_preparation_boundaries(offset, in_today, in_week):
    deadline = TODAY + timedelta(days=offset)
    result = worklist(tasks=[task(due_date=deadline)])
    assert bool(result.today_items) is in_today
    assert bool(result.next_seven_days_items) is in_week
    if in_week:
        item = result.next_seven_days_items[0]
        assert item.deadline == deadline
        assert item.preparation_date == deadline - timedelta(days=3)


def test_overdue_then_urgent_then_normal_with_stable_ties():
    tasks = [task(id=5, due_date=TODAY), task(id=3, priority="High"),
             task(id=2, due_date=TODAY - timedelta(days=1)),
             task(id=1, due_date=TODAY - timedelta(days=2)),
             task(id=4, due_date=TODAY)]
    first = worklist(tasks=tasks)
    assert [item.task_id for item in first.today_items] == [1, 2, 3, 4, 5]
    assert first == worklist(tasks=list(reversed(tasks)))


def test_cross_case_tasks_and_case_actions_remain_distinct():
    cases = [case(primary_deadline=TODAY), case(id=2, title="Fall B", follow_up_date=TODAY)]
    result = worklist(cases, [task(due_date=TODAY), task(id=2, case_id=2, due_date=TODAY)])
    assert {item.key for item in result.today_items} == {"case:1", "case:2", "task:1", "task:2"}
    assert next(item for item in result.today_items if item.key == "task:2").case_title == "Fall B"


@pytest.mark.parametrize("changes", [{"is_archived": True}, {"status": "Completed"}])
def test_inactive_cases_and_their_tasks_are_excluded(changes):
    assert not worklist([case(primary_deadline=TODAY, **changes)], [task(due_date=TODAY)]).today_items


@pytest.mark.parametrize("status", ["Completed", "completed", "Erledigt", "Unknown"])
def test_only_open_tasks_are_included(status):
    assert not worklist(tasks=[task(status=status, due_date=TODAY)]).today_items


def test_missing_case_information_is_actionable_without_invented_dates():
    item = worklist([case(responsible_person="  ", next_action=None)]).today_items[0]
    assert item.responsible_person is None
    assert item.deadline is None and item.preparation_date is None
    assert item.next_action == "Nächste Maßnahme festlegen"
    assert item.reasons == ["Verantwortung offen", "Nächste Maßnahme offen"]


def test_task_does_not_inherit_case_deadline_owner_or_action():
    items = worklist([case(primary_deadline=TODAY)], [task(responsible_person=None)]).today_items
    item = next(item for item in items if item.kind == "task")
    assert item.deadline is None and item.preparation_date is None
    assert item.responsible_person is None
    assert item.next_action == "Unterlagen prüfen"


@pytest.mark.parametrize("changes,reason", [({"risk": "High"}, "Hohes Fallrisiko"),
    ({"status": "Critical"}, "Kritischer Fallstatus")])
def test_urgent_cases_with_later_deadline(changes, reason):
    item = worklist([case(primary_deadline=TODAY + timedelta(days=30), **changes)]).today_items[0]
    assert item.priority == "urgent" and reason in item.reasons


def test_urgent_undated_task():
    item = worklist(tasks=[task(priority="High")]).today_items[0]
    assert item.deadline is None
    assert "Hohe Aufgabenpriorität" in item.reasons


@pytest.mark.parametrize("offset,in_today,in_week", [(-1, True, True), (0, True, True),
    (7, False, True), (8, False, False)])
def test_explicit_follow_up_with_later_final_deadline(offset, in_today, in_week):
    result = worklist([case(primary_deadline=TODAY + timedelta(days=30),
                            follow_up_date=TODAY + timedelta(days=offset))])
    assert bool(result.today_items) is in_today
    assert bool(result.next_seven_days_items) is in_week


def test_zero_preparation_lead_and_no_silent_truncation():
    tasks = [task(id=index, due_date=TODAY + timedelta(days=7)) for index in range(1, 26)]
    result = worklist(tasks=tasks, lead=0)
    assert not result.today_items
    assert len(result.next_seven_days_items) == 25
    assert all(item.preparation_date == item.deadline for item in result.next_seven_days_items)


@pytest.mark.parametrize("raw,expected", [("0", 0), ("5", 5), ("bad", 3), ("-1", 3), ("999999", 3)])
def test_configuration(monkeypatch, raw, expected):
    monkeypatch.setenv("DASHBOARD_PREPARATION_LEAD_DAYS", raw)
    assert preparation_lead_days() == expected


@pytest.mark.parametrize("instant,expected", [
    (datetime(2026, 11, 16, 23, 30, tzinfo=timezone.utc), TODAY),
    (datetime(2026, 7, 1, 22, 30, tzinfo=timezone.utc), date(2026, 7, 2)),
    (datetime(2026, 11, 16, 22, 30, tzinfo=timezone.utc), date(2026, 11, 16)),
])
def test_berlin_midnight_including_daylight_saving(instant, expected):
    assert berlin_today(instant) == expected


@pytest.mark.parametrize("instant,deadline,preparation", [
    # Three calendar days across each DST transition, not 72 elapsed hours.
    (datetime(2026, 3, 28, 23, 30, tzinfo=timezone.utc), date(2026, 4, 1), date(2026, 3, 29)),
    (datetime(2026, 10, 24, 22, 30, tzinfo=timezone.utc), date(2026, 10, 28), date(2026, 10, 25)),
    # Year boundary and leap day.
    (datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc), date(2027, 1, 4), date(2027, 1, 1)),
    (datetime(2028, 2, 28, 23, 30, tzinfo=timezone.utc), date(2028, 3, 3), date(2028, 2, 29)),
])
def test_preparation_uses_berlin_calendar_across_dst_and_calendar_boundaries(instant, deadline, preparation):
    today = berlin_today(instant)
    result = build_worklist(cases=[case()], tasks=[task(due_date=deadline)], today=today, lead_days=3)
    assert result.today == preparation
    assert result.today_items[0].preparation_date == preparation
    assert result.today_items[0].deadline == deadline
    assert result.through == today + timedelta(days=7)


def test_default_preparation_policy(monkeypatch):
    monkeypatch.delenv("DASHBOARD_PREPARATION_LEAD_DAYS", raising=False)
    assert preparation_lead_days() == 3


def test_ai_proposals_are_ignored_and_inputs_unchanged():
    source = case(next_action=None, suggested_next_action="AI action", suggested_deadline=TODAY)
    before = deepcopy(vars(source))
    item = worklist([source]).today_items[0]
    assert item.deadline is None and item.next_action == "Nächste Maßnahme festlegen"
    assert vars(source) == before


def test_endpoint_contract_scoping_and_no_writes(monkeypatch):
    app = FastAPI()
    app.include_router(dashboard.router)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [[case()], [task(due_date=TODAY)]]
    user = models.User(id=7, role="Viewer")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    scope = MagicMock(side_effect=lambda query, current: query)
    monkeypatch.setattr(dashboard, "scope_case_query", scope)
    monkeypatch.setattr(dashboard, "berlin_today", lambda: TODAY)
    monkeypatch.setenv("DASHBOARD_PREPARATION_LEAD_DAYS", "3")
    response = TestClient(app).get("/dashboard/worklist")
    assert response.status_code == 200
    body = response.json()
    assert body["today"] == "2026-11-17" and body["through"] == "2026-11-24"
    assert body["timezone"] == "Europe/Berlin"
    assert body["today_items"][0]["task_id"] == 1
    scope.assert_called_once_with(db.query.return_value, user)
    assert db.query.call_count == 2
    assert {call.args[0] for call in db.query.call_args_list} == {models.Case, models.Task}
    for method in (db.add, db.delete, db.commit, db.flush):
        method.assert_not_called()


def test_endpoint_requires_authentication():
    app = FastAPI()
    app.include_router(dashboard.router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    # Match the application's session middleware without importing its startup.
    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key="test-only")
    assert TestClient(app).get("/dashboard/worklist").status_code == 401


def test_database_queries_filter_tasks_through_visible_active_cases(monkeypatch):
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Query, Session

    statements = []

    def read(query):
        statements.append(str(query.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True},
        )))
        return []

    monkeypatch.setattr(Query, "all", read)
    # A narrower scope must propagate to both queries if the access policy changes.
    monkeypatch.setattr(dashboard, "scope_case_query", lambda query, user: query.filter(models.Case.id == 42))
    result = dashboard.dashboard_worklist(db=Session(), current_user=models.User(id=7, role="User"))
    assert not result.today_items
    assert len(statements) == 2
    for sql in statements:
        assert "cases.id = 42" in sql
        assert "cases.status != 'Completed'" in sql
        assert "cases.is_archived IS false" in sql
    assert "tasks.status = 'Open'" in statements[1]
    assert "tasks.case_id IN (SELECT cases.id" in statements[1]
