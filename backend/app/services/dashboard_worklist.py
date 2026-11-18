"""Read-only planning from stored case/task data; never consume AI proposals."""

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import models, schemas


def format_calendar_date(value: date) -> str:
    # strftime('%Y') does not pad years below 1000 consistently across platforms.
    return f"{value.day:02d}.{value.month:02d}.{value.year:04d}"


def berlin_today(now: datetime | None = None) -> date:
    return (now or datetime.now(ZoneInfo("Europe/Berlin"))).astimezone(
        ZoneInfo("Europe/Berlin")
    ).date()


def preparation_lead_days() -> int:
    """Provisional calendar-day policy; invalid configuration uses three days."""
    try:
        value = int(os.getenv("DASHBOARD_PREPARATION_LEAD_DAYS", "3"))
    except ValueError:
        return 3
    return value if 0 <= value <= 3650 else 3


def build_worklist(
    *, cases: list[models.Case], tasks: list[models.Task],
    today: date, lead_days: int,
) -> schemas.DashboardWorklist:
    through = today + timedelta(days=7)
    active = {
        case.id: case for case in cases
        if not case.is_archived and case.status != "Completed"
    }
    items = []

    def add(case, task=None):
        deadline = task.due_date if task is not None else case.primary_deadline
        preparation = deadline - timedelta(days=lead_days) if deadline else None
        follow_up = case.follow_up_date if task is None else None
        owner = (task.responsible_person if task is not None else case.responsible_person)
        owner = (owner or "").strip() or None
        action = (task.title if task is not None else case.next_action) or ""
        action = action.strip()
        urgent = case.risk == "High" or case.status == "Critical"
        if task is not None:
            urgent = urgent or task.priority == "High"
        overdue = bool(deadline and deadline < today)
        dates = [value for value in (preparation, follow_up) if value is not None]
        # Missing case metadata is actionable now; an unassigned task also needs assignment.
        immediate = urgent or not owner or not action
        if immediate:
            dates.append(today)
        attention = min(dates) if dates else None
        if attention is None or attention > through:
            return
        reasons = []
        if overdue:
            reasons.append("Frist überfällig")
        elif deadline == today:
            reasons.append("Heute fällig")
        elif deadline and deadline <= through:
            reasons.append("Frist in den nächsten 7 Tagen")
        if task is not None and task.priority == "High":
            reasons.append("Hohe Aufgabenpriorität")
        if case.risk == "High":
            reasons.append("Hohes Fallrisiko")
        if case.status == "Critical":
            reasons.append("Kritischer Fallstatus")
        if preparation and preparation <= through:
            reasons.append(f"Vorbereitung ab {format_calendar_date(preparation)}")
        if follow_up and follow_up <= through:
            reasons.append("Wiedervorlage fällig" if follow_up <= today else "Wiedervorlage in den nächsten 7 Tagen")
        if not owner:
            reasons.append("Verantwortung offen")
        if not action:
            reasons.append("Nächste Maßnahme offen")
        # Explain only triggers that are active now (or on the future attention date).
        # A later final deadline must not obscure an independent due follow-up.
        attention_reasons = []
        trigger_date = max(today, attention)
        if deadline and deadline <= trigger_date:
            attention_reasons.append(
                "Frist überfällig" if overdue else "Heute fällig" if deadline == today
                else f"Frist am {format_calendar_date(deadline)}"
            )
        if preparation and preparation <= trigger_date:
            attention_reasons.append(f"Vorbereitung ab {format_calendar_date(preparation)}")
        if follow_up and follow_up <= trigger_date:
            attention_reasons.append(f"Wiedervorlage am {format_calendar_date(follow_up)}")
        if task is not None and task.priority == "High":
            attention_reasons.append("Hohe Aufgabenpriorität")
        if case.risk == "High":
            attention_reasons.append("Hohes Fallrisiko")
        if case.status == "Critical":
            attention_reasons.append("Kritischer Fallstatus")
        if not owner:
            attention_reasons.append("Verantwortung offen")
        if not action:
            attention_reasons.append("Nächste Maßnahme offen")
        items.append(schemas.DashboardWorkItem(
            key=f"task:{task.id}" if task is not None else f"case:{case.id}",
            kind="task" if task is not None else "case",
            case_id=case.id, case_title=case.title,
            task_id=task.id if task is not None else None,
            title=task.title if task is not None else "Fallmaßnahme / Wiedervorlage",
            responsible_person=owner, deadline=deadline, preparation_date=preparation,
            attention_date=attention, attention_reasons=attention_reasons,
            priority="overdue" if overdue else "urgent" if urgent else "normal",
            reasons=reasons, next_action=action or "Nächste Maßnahme festlegen",
        ))

    for case in active.values():
        add(case)
    for task in tasks:
        if task.case_id in active and task.status == "Open":
            add(active[task.case_id], task)
    items.sort(key=lambda item: (
        {"overdue": 0, "urgent": 1, "normal": 2}[item.priority],
        (item.deadline or date.max) if item.priority == "overdue" else (item.attention_date or date.max),
        item.deadline or date.max, item.case_id, item.task_id or 0,
    ))
    return schemas.DashboardWorklist(
        today=today, through=through, preparation_lead_days=lead_days,
        today_items=[item for item in items if item.attention_date <= today],
        next_seven_days_items=[item for item in items if today < item.attention_date <= through],
    )
