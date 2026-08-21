import os
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app import models


DEFAULT_HIGH_FINANCIAL_THRESHOLD = Decimal("50000")


@dataclass(frozen=True)
class RiskSuggestion:
    level: str
    reason: str


HIGH_RISK_KEYWORDS = (
    "kündigung",
    "klage",
    "gericht",
    "anwalt",
    "anwaltsschreiben",
    "rechtsstreit",
    "arbeitsrecht",
    "haftung",
    "schaden",
    "eskalation",
    "fristversäumnis",
    "vertragsstrafe",
    "abmahnung",
    "insolvenz",
    "betrug",
    "datenschutzverletzung",
)

MEDIUM_RISK_KEYWORDS = (
    "beschwerde",
    "verzug",
    "streit",
    "warnung",
    "mahnung",
    "ungeklärt",
    "offen",
)


def get_high_financial_threshold() -> Decimal:
    """
    Return the configurable amount from which
    financial exposure is considered high.
    """
    raw_value = os.getenv(
        "HIGH_FINANCIAL_AMOUNT",
        str(DEFAULT_HIGH_FINANCIAL_THRESHOLD),
    )

    try:
        threshold = Decimal(raw_value)
    except (InvalidOperation, TypeError, ValueError):
        return DEFAULT_HIGH_FINANCIAL_THRESHOLD

    if threshold <= 0:
        return DEFAULT_HIGH_FINANCIAL_THRESHOLD

    return threshold


def normalize_financial_amount(
    value: object,
) -> Decimal | None:
    """
    Convert a database value into Decimal.

    Return None when the value is missing, invalid,
    negative, NaN, or infinite.
    """
    if value is None:
        return None

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if not amount.is_finite():
        return None

    if amount < 0:
        return None

    return amount


def format_euro(amount: Decimal) -> str:
    """
    Format a decimal value using German-style separators.

    Example:
    50000 -> 50.000,00 EUR
    """
    formatted = f"{amount:,.2f}"

    return (
        formatted
        .replace(",", "_")
        .replace(".", ",")
        .replace("_", ".")
        + " EUR"
    )


def add_reason(
    reasons: list[str],
    reason: str,
) -> None:
    """
    Add a reason only once.
    """
    if reason not in reasons:
        reasons.append(reason)


def build_case_text(
    case: models.Case,
) -> str:
    """
    Build one searchable text value from the main case fields.
    """
    values = [
        case.title,
        case.description,
        case.management_summary,
        case.risk_reason,
        case.next_action,
    ]

    return " ".join(
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    ).lower()


def calculate_case_risk(
    case: models.Case,
) -> RiskSuggestion:
    """
    Return a transparent, rule-based risk recommendation.

    The recommendation does not automatically replace
    the manually confirmed risk.
    """
    today = date.today()

    high_reasons: list[str] = []
    medium_reasons: list[str] = []

    if case.status == "Completed":
        return RiskSuggestion(
            level="Low",
            reason="Der Fall ist abgeschlossen.",
        )

    # Deadline rules
    if (
        case.primary_deadline
        and case.primary_deadline < today
    ):
        add_reason(
            high_reasons,
            "Die Hauptfrist ist überschritten.",
        )

    elif (
        case.primary_deadline
        and case.primary_deadline
        <= today + timedelta(days=3)
    ):
        add_reason(
            high_reasons,
            "Die Hauptfrist läuft innerhalb der nächsten drei Tage ab.",
        )

    elif (
        case.primary_deadline
        and case.primary_deadline
        <= today + timedelta(days=7)
    ):
        add_reason(
            medium_reasons,
            "Die Hauptfrist liegt innerhalb der nächsten sieben Tage.",
        )

    # Critical status
    if case.status == "Critical":
        add_reason(
            high_reasons,
            "Der Fall hat den Status „Kritisch“.",
        )

    # Text-based rules
    case_text = build_case_text(case)

    resolution_terms = (
        "vergleich",
        "einigung",
        "erledigt",
        "abgeschlossen",
        "beendet",
        "vollständig erfüllt",
        "zahlung erfolgt",
    )
    live_escalation_terms = (
        "nicht gezahlt",
        "zahlung ausstehend",
        "vergleichsbruch",
        "verstoß gegen den vergleich",
        "klage eingereicht",
        "klage anhängig",
        "vollstreckung",
        "frist überschritten",
        "überfällig",
    )
    has_resolution_signal = any(term in case_text for term in resolution_terms)
    has_live_escalation = any(term in case_text for term in live_escalation_terms)

    matched_high_keywords = [
        keyword
        for keyword in HIGH_RISK_KEYWORDS
        if keyword in case_text
    ]

    matched_medium_keywords = [
        keyword
        for keyword in MEDIUM_RISK_KEYWORDS
        if keyword in case_text
    ]

    if matched_high_keywords:
        if has_resolution_signal and not has_live_escalation:
            add_reason(
                medium_reasons,
                (
                    "Der Fall hatte einen rechtlich kritischen Ausgangssachverhalt, "
                    "neuere Angaben deuten jedoch auf Vergleich, Erledigung oder "
                    "wesentliche Risikoreduktion hin."
                ),
            )
        else:
            add_reason(
                high_reasons,
                (
                    "Der Fall enthält aktuell Hinweise auf einen rechtlichen, "
                    "arbeitsrechtlichen oder sonstigen kritischen Sachverhalt."
                ),
            )

    elif matched_medium_keywords:
        add_reason(
            medium_reasons,
            "Der Fall enthält Hinweise auf möglichen Handlungsbedarf.",
        )

    # Employment-law category alone is not a High-risk signal.
    # It can justify additional attention, but current exposure must come from
    # deadlines, active disputes, non-performance or other live evidence.
    if case.category == "Employee":
        add_reason(
            medium_reasons,
            "Der Fall betrifft einen Mitarbeiter- bzw. arbeitsrechtlichen Sachverhalt.",
        )

    # Responsible person
    if not (
        case.responsible_person or ""
    ).strip():
        add_reason(
            high_reasons,
            "Es ist keine verantwortliche Person zugewiesen.",
        )

    # Next action
    if (
        case.primary_deadline
        and not (
            case.next_action or ""
        ).strip()
    ):
        add_reason(
            high_reasons,
            (
                "Es besteht eine Frist, aber keine "
                "nächste Maßnahme ist definiert."
            ),
        )

    elif not (
        case.next_action or ""
    ).strip():
        add_reason(
            medium_reasons,
            "Es ist keine nächste Maßnahme definiert.",
        )

    # Overdue tasks
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
        add_reason(
            high_reasons,
            (
                f"{len(overdue_tasks)} offene Aufgabe(n) "
                "sind überfällig."
            ),
        )

    # Financial exposure
    financial_amount = normalize_financial_amount(
        getattr(
            case,
            "financial_amount",
            None,
        ),
    )

    if financial_amount is not None:
        high_threshold = (
            get_high_financial_threshold()
        )

        medium_threshold = (
            high_threshold / Decimal("2")
        )

        if financial_amount >= high_threshold:
            if has_resolution_signal and not has_live_escalation:
                add_reason(
                    medium_reasons,
                    (
                        "Der historische finanzielle Betrag ist erheblich, wurde "
                        "durch neuere Vergleichs-/Erledigungsangaben jedoch in der "
                        "aktuellen Risikowirkung reduziert."
                    ),
                )
            else:
                add_reason(
                    high_reasons,
                    (
                        "Der finanzielle Betrag von "
                        f"{format_euro(financial_amount)} "
                        "erreicht oder überschreitet den "
                        f"hohen Schwellenwert von "
                        f"{format_euro(high_threshold)}."
                    ),
                )

        elif financial_amount >= medium_threshold:
            add_reason(
                medium_reasons,
                (
                    "Der finanzielle Betrag von "
                    f"{format_euro(financial_amount)} "
                    "ist erhöht und erreicht mindestens "
                    f"{format_euro(medium_threshold)}."
                ),
            )

    if high_reasons:
        return RiskSuggestion(
            level="High",
            reason=" ".join(high_reasons),
        )

    if medium_reasons:
        return RiskSuggestion(
            level="Medium",
            reason=" ".join(medium_reasons),
        )

    return RiskSuggestion(
        level="Low",
        reason=(
            "Keine kritischen, kurzfristigen oder "
            "finanziellen Risikomerkmale wurden erkannt."
        ),
    )


def refresh_risk_suggestion(
    case: models.Case,
) -> None:
    """
    Update the system recommendation on the case.

    This does not modify the manually confirmed risk.
    """
    suggestion = calculate_case_risk(case)

    case.suggested_risk = suggestion.level
    case.suggested_risk_reason = (
        suggestion.reason
    )