"""Shared dashboard and restricted editing regression tests."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from app import models
from app.services.case_access import scope_case_query, can_view_case, can_edit_case


def test_regular_user_sees_all_cases_without_distinct_or_access_join():
    user = models.User(id=7, role="User")
    query = scope_case_query(Session().query(models.Case), user)
    query = query.order_by((models.Case.id + 1).desc())
    sql = str(query.statement.compile(dialect=postgresql.dialect())).upper()
    assert "DISTINCT" not in sql
    assert "CASE_ACCESS" not in sql
    assert "ORDER BY" in sql


def test_regular_user_can_view_unassigned_case():
    assert can_view_case(Session(), models.User(id=7, role="User"), 123)


def test_manager_can_edit_any_case():
    assert can_edit_case(Session(), models.User(id=1, role="Manager"), 123)


def test_regular_user_without_assignment_cannot_edit():
    class NoAccessQuery:
        def filter(self, *args): return self
        def first(self): return None
    class NoAccessSession:
        def query(self, *args): return NoAccessQuery()
    assert not can_edit_case(NoAccessSession(), models.User(id=7, role="User"), 123)
