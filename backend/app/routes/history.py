from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.services.case_access import require_case_view

router = APIRouter(
    prefix="/cases",
    tags=["History"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/{case_id}/history",
    response_model=list[schemas.HistoryResponse],
)
def get_case_history(
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

    return (
        db.query(models.History)
        .filter(models.History.case_id == case_id)
        .order_by(models.History.created_at.desc())
        .all()
    )