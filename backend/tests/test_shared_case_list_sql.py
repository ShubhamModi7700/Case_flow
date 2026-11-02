"""Regression checks for shared-case listing and document case selection."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app import models
from app.services.case_access import scope_case_query


def test_assigned_user_scope_uses_exists_without_distinct():
    user = models.User(id=7, role="Employee")
    query = scope_case_query(Session().query(models.Case), user)
    # The real case listing orders by a computed expression. This previously
    # generated invalid PostgreSQL SQL when DISTINCT was applied by scoping.
    query = query.order_by((models.Case.id + 1).desc())
    sql = str(query.statement.compile(dialect=postgresql.dialect()))
    assert "SELECT DISTINCT" not in sql.upper()
    assert "EXISTS" in sql.upper()
    assert "case_access" in sql
    assert "ORDER BY" in sql.upper()


def test_global_role_does_not_apply_case_access_filter():
    user = models.User(id=8, role="Manager")
    query = scope_case_query(Session().query(models.Case), user)
    sql = str(query.statement.compile(dialect=postgresql.dialect()))
    assert "case_access" not in sql
