from dataclasses import dataclass
from datetime import date, timedelta

from app import models


@dataclass(frozen=True)
class RiskSuggestion:
    level: str
    reason: str


def calculate_case_risk(case: models.Case) -> RiskSuggestion:
    """Return a transparent, rule-based risk recommendation."""
    today = date.today()
    reasons: list[str] = []
    score = 0

    if case.status == "Completed":
        return RiskSuggestion(
            level="Low",
            reason="Der Fall ist abgeschlossen.",
        )

    if case.primary_deadline and case.primary_deadline < today:
        score += 100
        reasons.append("Die Hauptfrist ist überschritten.")
    elif (
        case.primary_deadline
        and case.primary_deadline <= today + timedelta(days=7)
    ):
        score += 30
        reasons.append(
            "Die Hauptfrist liegt innerhalb der nächsten sieben Tage."
        )

    if case.status == "Critical":
        score += 60
        reasons.append("Der Fall hat den Status „Kritisch“.")

    if not (case.next_action or "").strip():
        score += 25
        reasons.append("Es ist keine nächste Maßnahme definiert.")

    if not (case.responsible_person or "").strip():
        score += 20
        reasons.append("Es ist keine verantwortliche Person zugewiesen.")

    overdue_tasks = [
        task
        for task in case.tasks
        if (
            task.status != "Completed"
            and task.due_date is not None
            and task.due_date < today
        )
    ]

    if overdue_tasks:
        score += 50
        reasons.append(
            f"{len(overdue_tasks)} offene Aufgabe(n) sind überfällig."
        )

    if score >= 60:
        level = "High"
    elif score >= 20:
        level = "Medium"
    else:
        level = "Low"

    if not reasons:
        reasons.append(
            "Keine kritischen oder überfälligen Merkmale wurden erkannt."
        )

    return RiskSuggestion(level=level, reason=" ".join(reasons))


def refresh_risk_suggestion(case: models.Case) -> None:
    suggestion = calculate_case_risk(case)
    case.suggested_risk = suggestion.level
    case.suggested_risk_reason = suggestion.reason
