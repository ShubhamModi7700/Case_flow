from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


def get_user_by_email(
    db: Session,
    email: str,
) -> models.User | None:
    normalized_email = email.strip().lower()

    return (
        db.query(models.User)
        .filter(models.User.email == normalized_email)
        .first()
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> models.User | None:
    user = get_user_by_email(db, email)

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.hashed_password,
    ):
        return None

    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    user_id = request.session.get("user_id")

    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentifizierung erforderlich",
        )

    user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if user is None or not user.is_active:
        request.session.clear()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültige oder abgelaufene Sitzung",
        )

    return user