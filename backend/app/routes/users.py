from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, hash_password
from app.database import get_db

router = APIRouter(prefix="/users", tags=["Users"])


def require_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user


@router.get("/", response_model=list[schemas.UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    return db.query(models.User).order_by(models.User.full_name.asc()).all()


@router.post(
    "/",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    email = str(user_data.email).strip().lower()

    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = models.User(
        email=email,
        full_name=user_data.full_name.strip(),
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        is_active=user_data.is_active,
    )
    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    return user


@router.patch("/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int,
    user_data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    changes = user_data.model_dump(exclude_unset=True)

    if "email" in changes:
        email = str(changes["email"]).strip().lower()
        duplicate = (
            db.query(models.User)
            .filter(models.User.email == email, models.User.id != user_id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Email already in use")
        user.email = email

    if "full_name" in changes:
        user.full_name = changes["full_name"].strip()

    if "role" in changes:
        if user.id == current_admin.id and changes["role"] != "Admin":
            raise HTTPException(
                status_code=400,
                detail="You cannot remove your own administrator role",
            )
        user.role = changes["role"]

    if "is_active" in changes:
        if user.id == current_admin.id and changes["is_active"] is False:
            raise HTTPException(
                status_code=400,
                detail="You cannot disable your own account",
            )
        user.is_active = changes["is_active"]

    if changes.get("password"):
        user.hashed_password = hash_password(changes["password"])

    db.commit()
    db.refresh(user)
    return user