import os

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app import models
from app.auth import hash_password
from app.database import SessionLocal

load_dotenv()


def get_users() -> list[dict[str, str]]:
    users: list[dict[str, str]] = []

    for number in range(1, 15):
        prefix = f"USER_{number}"
        full_name = os.getenv(f"{prefix}_NAME", "").strip()
        email = os.getenv(f"{prefix}_EMAIL", "").strip().lower()
        password = os.getenv(f"{prefix}_PASSWORD", "")
        role = os.getenv(f"{prefix}_ROLE", "User").strip().title()

        if not any((full_name, email, password)):
            continue

        if not all((full_name, email, password)):
            raise RuntimeError(
                f"{prefix} is incomplete. Name, email, and password are required."
            )

        if role == "Admin":
            role = "Manager"

        if role not in {"Manager", "User", "Viewer"}:
            raise RuntimeError(f"{prefix}_ROLE must be Manager, User or Viewer.")

        users.append(
            {
                "full_name": full_name,
                "email": email,
                "password": password,
                "role": role,
            }
        )

    return users


def create_users() -> None:
    users = get_users()

    if not users:
        print("No users are configured in backend/.env.")
        return

    db: Session = SessionLocal()

    try:
        created = 0
        updated = 0

        for user_data in users:
            user = (
                db.query(models.User)
                .filter(models.User.email == user_data["email"])
                .first()
            )

            if user is None:
                user = models.User(
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=hash_password(user_data["password"]),
                    role=user_data["role"],
                    is_active=True,
                )
                db.add(user)
                created += 1
            else:
                user.full_name = user_data["full_name"]
                user.role = user_data["role"]
                user.is_active = True
                updated += 1

        db.commit()
        print(f"User setup complete. Created: {created}, updated: {updated}.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_users()
