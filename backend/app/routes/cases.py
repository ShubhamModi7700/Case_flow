from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.auth import get_current_user

router = APIRouter(
    prefix="/cases",
    tags=["Cases"],
    dependencies=[
        Depends(get_current_user),
    ],
)

@router.post(
    "/",
    response_model=schemas.CaseResponse,
    status_code=201,
)
def create_case(
    case_data: schemas.CaseCreate,
    db: Session = Depends(get_db),
):
    new_case = models.Case(**case_data.model_dump())

    db.add(new_case)
    db.flush()

    history = models.History(
        case_id=new_case.id,
        change="Case created",
        responsible_person=case_data.responsible_person,
        note="The case was created.",
    )

    db.add(history)
    db.commit()
    db.refresh(new_case)

    return new_case


@router.get(
    "/",
    response_model=list[schemas.CaseResponse],
)
def list_cases(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    category: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    query = db.query(models.Case)

    if not include_archived:
        query = query.filter(models.Case.is_archived.is_(False))

    if search:
        normalized_search = search.strip()
        search_value = f"%{normalized_search}%"
        case_number_value = normalized_search.upper()
        if case_number_value.startswith("CF-"):
            case_number_value = case_number_value[3:]

        filters = [
            models.Case.title.ilike(search_value),
            models.Case.company.ilike(search_value),
            models.Case.department.ilike(search_value),
            models.Case.external_contact.ilike(search_value),
            models.Case.responsible_person.ilike(search_value),
        ]

        if case_number_value.isdigit():
            filters.append(models.Case.id == int(case_number_value))

        query = query.filter(or_(*filters))

    if status:
        query = query.filter(models.Case.status == status)

    if risk:
        query = query.filter(models.Case.risk == risk)

    if category:
        query = query.filter(models.Case.category == category)

    return query.order_by(models.Case.id.asc()).all()


@router.get(
    "/{case_id}",
    response_model=schemas.CaseResponse,
)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    return case


@router.patch(
    "/{case_id}",
    response_model=schemas.CaseResponse,
)
def update_case(
    case_id: int,
    case_data: schemas.CaseUpdate,
    db: Session = Depends(get_db),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    update_values = case_data.model_dump(exclude_unset=True)
    changes: list[str] = []

    for field, new_value in update_values.items():
        old_value = getattr(case, field)

        if old_value != new_value:
            setattr(case, field, new_value)
            changes.append(
                f"{field}: {old_value!s} → {new_value!s}"
            )

    if changes:
        history = models.History(
            case_id=case.id,
            change="Case updated",
            responsible_person=case.responsible_person,
            note="; ".join(changes),
        )
        db.add(history)

    db.commit()
    db.refresh(case)

    return case


@router.delete("/{case_id}")
def archive_case(
    case_id: int,
    db: Session = Depends(get_db),
):
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    case.is_archived = True

    db.add(
        models.History(
            case_id=case.id,
            change="Case archived",
            responsible_person=case.responsible_person,
            note="The case was archived.",
        )
    )

    db.commit()

    return {"message": "Case archived successfully"}