from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.services.case_access import scope_case_query

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[
        Depends(get_current_user),
    ],
)


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    today = date.today()
    next_seven_days = today + timedelta(days=7)

    active_case_filters = (
        models.Case.status != "Completed",
        models.Case.is_archived.is_(False),
    )

    def visible_cases():
        return scope_case_query(db.query(models.Case), current_user)


    open_cases = (
        visible_cases()
        .filter(*active_case_filters)
        .count()
    )

    completed_cases = (
        visible_cases()
        .filter(
            models.Case.status == "Completed",
            models.Case.is_archived.is_(False),
        )
        .count()
    )

    low_risk_cases = (
        visible_cases()
        .filter(
            models.Case.risk == "Low",
            *active_case_filters,
        )
        .count()
    )

    medium_risk_cases = (
        visible_cases()
        .filter(
            models.Case.risk == "Medium",
            *active_case_filters,
        )
        .count()
    )

    high_risk_cases = (
        visible_cases()
        .filter(
            models.Case.risk == "High",
            *active_case_filters,
        )
        .count()
    )

    visible_case_ids = visible_cases().with_entities(models.Case.id).subquery()

    overdue_deadlines = (
        db.query(models.Task)
        .join(
            models.Case,
            models.Task.case_id == models.Case.id,
        )
        .filter(
            models.Task.due_date.isnot(None),
            models.Task.due_date < today,
            models.Task.status != "Completed",
            models.Case.id.in_(visible_case_ids),
            *active_case_filters,
        )
        .count()
    )

    upcoming_deadlines = (
        db.query(models.Task)
        .join(
            models.Case,
            models.Task.case_id == models.Case.id,
        )
        .filter(
            models.Task.due_date.isnot(None),
            models.Task.due_date >= today,
            models.Task.due_date <= next_seven_days,
            models.Task.status != "Completed",
            models.Case.id.in_(visible_case_ids),
            *active_case_filters,
        )
        .count()
    )

    cases_without_responsible = (
        visible_cases()
        .filter(
            *active_case_filters,
            or_(
                models.Case.responsible_person.is_(None),
                models.Case.responsible_person == "",
            ),
        )
        .count()
    )

    cases_without_next_action = (
        visible_cases()
        .filter(
            *active_case_filters,
            or_(
                models.Case.next_action.is_(None),
                models.Case.next_action == "",
            ),
        )
        .count()
    )

    pending_ai_suggestions = (
        db.query(models.AIDocumentSuggestion)
        .filter(
            models.AIDocumentSuggestion.status == "Pending",
            models.AIDocumentSuggestion.current_case_id.in_(visible_case_ids),
        )
        .count()
    )

    pending_management_summaries = (
        db.query(models.CaseAISummary)
        .filter(
            models.CaseAISummary.status == "Pending",
            models.CaseAISummary.case_id.in_(visible_case_ids),
        )
        .count()
    )

    documents_ready_for_ai = (
        db.query(models.Document)
        .filter(
            models.Document.embedding_status == "Ready",
            models.Document.case_id.in_(visible_case_ids),
        )
        .count()
    )

    next_actions = (
        visible_cases()
        .filter(
            *active_case_filters,
            models.Case.primary_deadline.isnot(None),
            models.Case.primary_deadline >= today,
            models.Case.primary_deadline <= next_seven_days,
            models.Case.next_action.isnot(None),
            models.Case.next_action != "",
        )
        .order_by(models.Case.primary_deadline.asc())
        .limit(5)
        .all()
    )

    return {
        "open_cases": open_cases,
        "completed_cases": completed_cases,
        "low_risk_cases": low_risk_cases,
        "medium_risk_cases": medium_risk_cases,
        "high_risk_cases": high_risk_cases,
        "overdue_deadlines": overdue_deadlines,
        "upcoming_deadlines": upcoming_deadlines,
        "cases_without_responsible": cases_without_responsible,
        "cases_without_next_action": cases_without_next_action,
        "pending_ai_suggestions": pending_ai_suggestions,
        "pending_management_summaries": pending_management_summaries,
        "documents_ready_for_ai": documents_ready_for_ai,
        "next_due_actions": [
            {
                "case_id": item.id,
                "title": item.title,
                "next_action": item.next_action,
                "deadline": item.primary_deadline,
            }
            for item in next_actions
        ],
    }