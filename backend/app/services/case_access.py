from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from app import models


GLOBAL_CASE_ROLES = {"Manager", "Shareholder"}
GLOBAL_CASE_EDIT_ROLES = {"Manager"}


def normalized_role(user: models.User) -> str:
    role = (user.role or "").strip().title()
    return "Manager" if role == "Admin" else role


def has_global_case_access(user: models.User) -> bool:
    return normalized_role(user) in GLOBAL_CASE_ROLES


def scope_case_query(query: Query, user: models.User) -> Query:
    """Limit a Case query to cases visible to the current user."""
    if has_global_case_access(user):
        return query

    return (
        query.join(
            models.CaseAccess,
            models.CaseAccess.case_id == models.Case.id,
        )
        .filter(models.CaseAccess.user_id == user.id)
        .distinct()
    )


def can_view_case(db: Session, user: models.User, case_id: int) -> bool:
    if has_global_case_access(user):
        return True

    return (
        db.query(models.CaseAccess.id)
        .filter(
            models.CaseAccess.case_id == case_id,
            models.CaseAccess.user_id == user.id,
        )
        .first()
        is not None
    )


def can_edit_case(db: Session, user: models.User, case_id: int) -> bool:
    if normalized_role(user) in GLOBAL_CASE_EDIT_ROLES:
        return True

    access = (
        db.query(models.CaseAccess)
        .filter(
            models.CaseAccess.case_id == case_id,
            models.CaseAccess.user_id == user.id,
        )
        .first()
    )
    return bool(access and access.can_edit)


def require_case_view(db: Session, user: models.User, case_id: int) -> None:
    if not can_view_case(db, user, case_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sie haben keinen Zugriff auf diesen Fall",
        )


def require_case_edit(db: Session, user: models.User, case_id: int) -> None:
    if not can_edit_case(db, user, case_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sie haben keine Bearbeitungsberechtigung für diesen Fall",
        )


def replace_case_access(
    db: Session,
    case_id: int,
    entries: list,
) -> None:
    """Replace explicit employee access for a case."""
    db.query(models.CaseAccess).filter(
        models.CaseAccess.case_id == case_id
    ).delete(synchronize_session=False)

    seen: set[int] = set()
    for entry in entries:
        user_id = int(entry.user_id)
        if user_id in seen:
            continue
        seen.add(user_id)

        user = (
            db.query(models.User)
            .filter(
                models.User.id == user_id,
                models.User.is_active.is_(True),
            )
            .first()
        )
        if user is None:
            raise HTTPException(
                status_code=422,
                detail=f"Benutzer {user_id} ist nicht verfügbar",
            )

        # Global roles do not need explicit rows.
        if has_global_case_access(user):
            continue

        db.add(
            models.CaseAccess(
                case_id=case_id,
                user_id=user_id,
                can_edit=bool(entry.can_edit),
            )
        )


def ensure_responsible_access(
    db: Session,
    case_id: int,
    responsible_person: str | None,
) -> None:
    """Grant edit access when a responsible person's name matches a user.

    The existing project stores responsible people as text. This keeps that
    model intact for the presentation while making assignment grant access.
    Multiple comma/semicolon-separated names are supported.
    """
    if not responsible_person:
        return

    names = {
        part.strip().casefold()
        for part in responsible_person.replace(";", ",").split(",")
        if part.strip()
    }
    if not names:
        return

    users = db.query(models.User).filter(models.User.is_active.is_(True)).all()
    for user in users:
        if user.full_name.strip().casefold() not in names:
            continue
        if has_global_case_access(user):
            continue

        access = (
            db.query(models.CaseAccess)
            .filter(
                models.CaseAccess.case_id == case_id,
                models.CaseAccess.user_id == user.id,
            )
            .first()
        )
        if access is None:
            db.add(
                models.CaseAccess(
                    case_id=case_id,
                    user_id=user.id,
                    can_edit=True,
                )
            )
        else:
            access.can_edit = True
