from __future__ import annotations

from datetime import date

from app import models, schemas


DECISION_CATEGORIES = {"decision", "entscheidung", "freigabe"}


def is_explicit_decision_task(task: models.Task) -> bool:
    """Only classify tasks explicitly categorized as a decision.

    Step 12 deliberately avoids asking the model to infer workflow state from
    prose. The database remains authoritative.
    """
    category = (task.category or "").strip().casefold()
    return category in DECISION_CATEGORIES


def build_case_work_status(
    *,
    case: models.Case,
    tasks: list[models.Task],
    today: date | None = None,
) -> schemas.AssistantCaseWorkStatus:
    current_date = today or date.today()
    open_tasks = [task for task in tasks if task.status != "Completed"]

    task_items = [
        schemas.AssistantOpenTask(
            id=task.id,
            title=task.title,
            description=task.description,
            category=task.category,
            responsible_person=task.responsible_person,
            due_date=task.due_date,
            priority=task.priority,
            status=task.status,
            is_overdue=bool(task.due_date and task.due_date < current_date),
        )
        for task in open_tasks
    ]

    decision_items = [
        schemas.AssistantOpenDecision(
            task_id=task.id,
            title=task.title,
            description=task.description,
            responsible_person=task.responsible_person,
            due_date=task.due_date,
        )
        for task in open_tasks
        if is_explicit_decision_task(task)
    ]

    return schemas.AssistantCaseWorkStatus(
        primary_deadline=case.primary_deadline,
        primary_deadline_is_overdue=bool(
            case.primary_deadline and case.primary_deadline < current_date
        ),
        follow_up_date=case.follow_up_date,
        next_action=case.next_action,
        open_tasks=task_items,
        open_decisions=decision_items,
        note=(
            "Offene Entscheidungen werden nur aus offenen Aufgaben mit der "
            "Kategorie Entscheidung/Decision/Freigabe übernommen; es findet "
            "keine KI-Ableitung statt."
        ),
    )
