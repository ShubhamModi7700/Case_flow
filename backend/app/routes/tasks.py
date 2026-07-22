from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db

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
            detail="Case not found",
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
            detail="Task not found",
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
):
    case = get_case_or_404(
        case_id=case_id,
        db=db,
    )

    try:
        task = models.Task(
            case_id=case.id,
            **task_data.model_dump(),
        )

        db.add(task)
        db.flush()

        history = models.History(
            case_id=case.id,
            change="Task created",
            responsible_person=(
                task.responsible_person
                or case.responsible_person
            ),
            note=f"Task '{task.title}' was created.",
        )

        db.add(history)
        db.commit()
        db.refresh(task)

        return task

    except SQLAlchemyError as exc:
        db.rollback()

        print("DATABASE ERROR WHILE CREATING TASK:")
        print(repr(exc))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The task could not be created.",
        ) from exc


@router.get(
    "/cases/{case_id}/tasks",
    response_model=list[schemas.TaskResponse],
)
def list_tasks(
    case_id: int,
    db: Session = Depends(get_db),
):
    get_case_or_404(
        case_id=case_id,
        db=db,
    )

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
):
    task = get_task_or_404(
        task_id=task_id,
        db=db,
    )

    if task.status == "Completed":
        return task

    try:
        task.status = "Completed"

        history = models.History(
            case_id=task.case_id,
            change="Task completed",
            responsible_person=task.responsible_person,
            note=f"Task '{task.title}' was completed.",
        )

        db.add(history)
        db.commit()
        db.refresh(task)

        return task

    except SQLAlchemyError as exc:
        db.rollback()

        print("DATABASE ERROR WHILE COMPLETING TASK:")
        print(repr(exc))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The task could not be completed.",
        ) from exc