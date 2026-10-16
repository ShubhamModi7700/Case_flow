from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case as sql_case, exists, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, require_editor, require_manager
from app.database import get_db
from app.services.case_access import (
    ensure_responsible_access,
    has_global_case_access,
    replace_case_access,
    can_edit_case,
    require_case_edit,
    require_case_view,
    scope_case_query,
)
from app.services.risk import refresh_risk_suggestion


router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
    dependencies=[Depends(get_current_user)],
)


SortOption = Literal[
    "priority",
    "caseAsc",
    "caseDesc",
    "newest",
    "oldest",
]


def _serialize_case(
    case: models.Case,
    current_user: models.User,
    db: Session,
) -> schemas.CaseResponse:
    data = {
        column.name: getattr(case, column.name)
        for column in models.Case.__table__.columns
    }
    data["user_can_edit"] = can_edit_case(db, current_user, case.id)
    data["access"] = [
        {
            "user_id": entry.user_id,
            "full_name": entry.user.full_name,
            "email": entry.user.email,
            "can_edit": entry.can_edit,
        }
        for entry in case.access_entries
        if entry.user is not None and entry.user.is_active
    ]
    return schemas.CaseResponse.model_validate(data)


@router.post(
    "/",
    response_model=schemas.CaseResponse,
    status_code=201,
)
def create_case(
    case_data: schemas.CaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    values = case_data.model_dump(exclude={"access"})
    new_case = models.Case(**values)

    db.add(new_case)
    db.flush()

    if has_global_case_access(current_user):
        replace_case_access(db, new_case.id, case_data.access)
    else:
        db.add(
            models.CaseAccess(
                case_id=new_case.id,
                user_id=current_user.id,
                can_edit=True,
            )
        )

    ensure_responsible_access(
        db,
        new_case.id,
        new_case.responsible_person,
    )
    refresh_risk_suggestion(new_case)

    db.add(
        models.History(
            case_id=new_case.id,
            change="Fall erstellt",
            responsible_person=case_data.responsible_person,
            note="Der Fall wurde erstellt.",
        ),
    )

    db.commit()
    db.refresh(new_case)

    return _serialize_case(new_case, current_user, db)


@router.get(
    "/",
    response_model=list[schemas.CaseResponse],
)
def list_cases(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    status_group: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    category: str | None = Query(default=None),
    sort: SortOption = Query(default="priority"),
    overdue: bool = Query(default=False),
    upcoming: bool = Query(default=False),
    missing_owner: bool = Query(default=False),
    missing_next_action: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    today = date.today()
    next_seven_days = today + timedelta(days=7)

    query = scope_case_query(db.query(models.Case), current_user)

    if not include_archived:
        query = query.filter(
            models.Case.is_archived.is_(False),
        )

    if search:
        normalized_search = search.strip()
        search_value = f"%{normalized_search}%"

        case_number_value = normalized_search.upper()

        if case_number_value.startswith("CF-"):
            case_number_value = case_number_value[3:]

        search_filters = [
            models.Case.title.ilike(search_value),
            models.Case.company.ilike(search_value),
            models.Case.department.ilike(search_value),
            models.Case.external_contact.ilike(
                search_value,
            ),
            models.Case.responsible_person.ilike(
                search_value,
            ),
        ]

        if case_number_value.isdigit():
            search_filters.append(
                models.Case.id
                == int(case_number_value),
            )

        query = query.filter(
            or_(*search_filters),
        )

    if status:
        query = query.filter(
            models.Case.status == status,
        )

    if status_group == "open":
        query = query.filter(
            models.Case.status != "Completed",
        )
    elif status_group == "completed":
        query = query.filter(
            models.Case.status == "Completed",
        )

    if risk:
        query = query.filter(
            models.Case.risk == risk,
        )

    if category:
        query = query.filter(
            models.Case.category == category,
        )

    if missing_owner:
        query = query.filter(
            or_(
                models.Case.responsible_person.is_(
                    None,
                ),
                models.Case.responsible_person
                == "",
            ),
        )

    if missing_next_action:
        query = query.filter(
            or_(
                models.Case.next_action.is_(None),
                models.Case.next_action == "",
            ),
        )

    overdue_task_exists = exists().where(
        and_(
            models.Task.case_id
            == models.Case.id,
            models.Task.due_date.isnot(None),
            models.Task.due_date < today,
            models.Task.status != "Completed",
        ),
    )

    upcoming_task_exists = exists().where(
        and_(
            models.Task.case_id
            == models.Case.id,
            models.Task.due_date.isnot(None),
            models.Task.due_date >= today,
            models.Task.due_date
            <= next_seven_days,
            models.Task.status != "Completed",
        ),
    )

    case_deadline_overdue = and_(
        models.Case.primary_deadline.isnot(None),
        models.Case.primary_deadline < today,
        models.Case.status != "Completed",
    )

    case_deadline_upcoming = and_(
        models.Case.primary_deadline.isnot(None),
        models.Case.primary_deadline >= today,
        models.Case.primary_deadline
        <= next_seven_days,
        models.Case.status != "Completed",
    )

    if overdue:
        query = query.filter(
            or_(
                case_deadline_overdue,
                overdue_task_exists,
            ),
        )

    if upcoming:
        query = query.filter(
            or_(
                case_deadline_upcoming,
                upcoming_task_exists,
            ),
        )

    priority_score = (
        sql_case(
            (
                or_(
                    case_deadline_overdue,
                    overdue_task_exists,
                ),
                100,
            ),
            else_=0,
        )
        + sql_case(
            (
                models.Case.risk == "High",
                50,
            ),
            else_=0,
        )
        + sql_case(
            (
                models.Case.status
                == "Critical",
                40,
            ),
            else_=0,
        )
        + sql_case(
            (
                or_(
                    models.Case.next_action.is_(
                        None,
                    ),
                    models.Case.next_action
                    == "",
                ),
                20,
            ),
            else_=0,
        )
        + sql_case(
            (
                or_(
                    models.Case.responsible_person.is_(
                        None,
                    ),
                    models.Case.responsible_person
                    == "",
                ),
                15,
            ),
            else_=0,
        )
        + sql_case(
            (
                models.Case.risk
                == "Medium",
                10,
            ),
            else_=0,
        )
    )

    if sort == "caseAsc":
        query = query.order_by(
            models.Case.id.asc(),
        )

    elif sort == "caseDesc":
        query = query.order_by(
            models.Case.id.desc(),
        )

    elif sort == "newest":
        query = query.order_by(
            models.Case.created_at.desc(),
            models.Case.id.desc(),
        )

    elif sort == "oldest":
        query = query.order_by(
            models.Case.created_at.asc(),
            models.Case.id.asc(),
        )

    else:
        query = query.order_by(
            priority_score.desc(),
            models.Case.primary_deadline
            .asc()
            .nullslast(),
            models.Case.updated_at.desc(),
            models.Case.id.asc(),
        )

    return [_serialize_case(item, current_user, db) for item in query.all()]


@router.get(
    "/{case_id}",
    response_model=schemas.CaseResponse,
)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Fall nicht gefunden",
        )

    require_case_view(db, current_user, case_id)
    return _serialize_case(case, current_user, db)


@router.patch(
    "/{case_id}",
    response_model=schemas.CaseResponse,
)
def update_case(
    case_id: int,
    case_data: schemas.CaseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Fall nicht gefunden",
        )

    require_case_edit(db, current_user, case_id)

    update_values = case_data.model_dump(
        exclude_unset=True,
    )
    access_values = update_values.pop("access", None)

    manager_only_fields = {
        "responsible_person",
        "status",
        "risk",
        "risk_reason",
        "risk_is_manual",
        "primary_deadline",
        "follow_up_date",
        "next_action",
    }
    current_role = (current_user.role or "").strip().title()
    if current_role == "Admin":
        current_role = "Manager"

    forbidden_fields = manager_only_fields.intersection(update_values)
    if current_role != "Manager" and forbidden_fields:
        raise HTTPException(
            status_code=403,
            detail=(
                "Nur Manager dürfen Status, Risiko, Fristen, "
                "verantwortliche Person oder nächste Maßnahme ändern"
            ),
        )

    if update_values.get("status") == "Completed":
        update_values["next_action"] = None
        update_values["primary_deadline"] = None
        update_values["follow_up_date"] = None

    changes: list[str] = []

    for field, new_value in update_values.items():
        old_value = getattr(case, field)

        if old_value != new_value:
            setattr(case, field, new_value)

            changes.append(
                f"{field}: {old_value!s} → "
                f"{new_value!s}",
            )

    if changes:
        if "risk" in update_values:
            case.risk_is_manual = update_values.get(
                "risk_is_manual",
                True,
            )

        refresh_risk_suggestion(case)

        db.add(
            models.History(
                case_id=case.id,
                change="Fall aktualisiert",
                responsible_person=(
                    case.responsible_person
                ),
                note="; ".join(changes),
            ),
        )

    if access_values is not None:
        if (current_user.role or "").strip().title() != "Manager":
            raise HTTPException(
                status_code=403,
                detail="Nur die Geschäftsführung darf Fallzugriffe ändern",
            )
        replace_case_access(db, case.id, case_data.access or [])

    ensure_responsible_access(
        db,
        case.id,
        case.responsible_person,
    )

    db.commit()
    db.refresh(case)

    return _serialize_case(case, current_user, db)


@router.post(
    "/{case_id}/confirm-risk",
    response_model=schemas.CaseResponse,
)
def confirm_suggested_risk(
    case_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_manager),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Fall nicht gefunden",
        )

    refresh_risk_suggestion(case)

    if not case.suggested_risk:
        raise HTTPException(
            status_code=400,
            detail="Keine Risikoeinschätzung vorhanden",
        )

    case.risk = case.suggested_risk
    case.risk_reason = case.suggested_risk_reason
    case.risk_is_manual = False

    db.add(
        models.History(
            case_id=case.id,
            change="Risikoeinschätzung übernommen",
            responsible_person=case.responsible_person,
            note=case.risk_reason,
        )
    )

    db.commit()
    db.refresh(case)
    return case


@router.delete("/{case_id}")
def archive_case(
    case_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_manager),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Fall nicht gefunden",
        )

    case.is_archived = True

    db.add(
        models.History(
            case_id=case.id,
            change="Fall archiviert",
            responsible_person=(
                case.responsible_person
            ),
            note="Der Fall wurde archiviert.",
        ),
    )

    db.commit()
    return {
        "message": "Fall erfolgreich archiviert",
    }