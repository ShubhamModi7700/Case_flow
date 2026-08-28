from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, require_editor
from app.database import get_db
from app.services.risk import refresh_risk_suggestion
from app.services.case_access import require_case_edit, require_case_view

router = APIRouter(
    tags=["Tasks"],
    dependencies=[
        Depends(get_current_user),
    ],
)


def get_case_or_404(
    case_id: int,
    db: Session,
) -> models.Case:
    case = (
        db.query(models.Case)
        .filter(models.Case.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fall nicht gefunden",
        )

    return case


def get_task_or_404(
    task_id: int,
    db: Session,
) -> models.Task:
    task = (
        db.query(models.Task)
        .filter(models.Task.id == task_id)
        .first()
    )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aufgabe nicht gefunden",
        )

    return task


@router.post(
    "/cases/{case_id}/tasks",
    response_model=schemas.TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    case_id: int,
    task_data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    case = get_case_or_404(
        case_id=case_id,
        db=db,
    )
    require_case_edit(db, current_user, case_id)

    try:
        task = models.Task(
            case_id=case.id,
            **task_data.model_dump(),
        )

        db.add(task)
        db.flush()

        history = models.History(
            case_id=case.id,
            change="Aufgabe erstellt",
            responsible_person=(
                task.responsible_person
                or case.responsible_person
            ),
            note=f"Task '{task.title}' was created.",
        )

        db.add(history)
        refresh_risk_suggestion(case)
        db.commit()
        db.refresh(task)

        return task

    except SQLAlchemyError as exc:
        db.rollback()

        print("DATABASE ERROR WHILE CREATING TASK:")
        print(repr(exc))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Die Aufgabe konnte nicht erstellt werden.",
        ) from exc


@router.get(
    "/cases/{case_id}/tasks",
    response_model=list[schemas.TaskResponse],
)
def list_tasks(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_case_or_404(
        case_id=case_id,
        db=db,
    )
    require_case_view(db, current_user, case_id)

    return (
        db.query(models.Task)
        .filter(models.Task.case_id == case_id)
        .order_by(
            models.Task.status.asc(),
            models.Task.due_date.asc(),
            models.Task.created_at.desc(),
        )
        .all()
    )


@router.patch(
    "/tasks/{task_id}/complete",
    response_model=schemas.TaskResponse,
)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    task = get_task_or_404(
        task_id=task_id,
        db=db,
    )
    require_case_edit(db, current_user, task.case_id)

    if task.status == "Completed":
        return task

    try:
        task.status = "Completed"

        history = models.History(
            case_id=task.case_id,
            change="Aufgabe abgeschlossen",
            responsible_person=task.responsible_person,
            note=f"Task '{task.title}' was completed.",
        )

        db.add(history)
        case = get_case_or_404(task.case_id, db)
        refresh_risk_suggestion(case)
        db.commit()
        db.refresh(task)

        return task

    except SQLAlchemyError as exc:
        db.rollback()

        print("DATABASE ERROR WHILE COMPLETING TASK:")
        print(repr(exc))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Die Aufgabe konnte nicht abgeschlossen werden.",
        ) from exc

@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    task = get_task_or_404(
        task_id=task_id,
        db=db,
    )
    require_case_edit(db, current_user, task.case_id)

    case_id = task.case_id
    task_title = task.title
    responsible_person = task.responsible_person

    try:
        db.delete(task)

        history = models.History(
            case_id=case_id,
            change="Aufgabe gelöscht",
            responsible_person=responsible_person,
            note=f"Task '{task_title}' was deleted.",
        )
        db.add(history)

        case = get_case_or_404(case_id, db)
        refresh_risk_suggestion(case)

        db.commit()
        return None

    except SQLAlchemyError as exc:
        db.rollback()

        print("DATABASE ERROR WHILE DELETING TASK:")
        print(repr(exc))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Die Aufgabe konnte nicht gelöscht werden.",
        ) from exc
