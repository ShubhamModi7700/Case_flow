from collections.abc import Generator
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool


# database.py is inside backend/app/
# Therefore parent.parent is backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

print(f"Loading environment from: {ENV_FILE}")
print(f".env exists: {ENV_FILE.exists()}")

# override=True ensures values from this file replace any old/empty
# DATABASE_URL already present in the process environment.
loaded = load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)

print(f".env loaded: {loaded}")


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise RuntimeError(
            f"DATABASE_URL is missing or empty.\n"
            f"Expected file: {ENV_FILE}\n"
            "Add a line beginning with DATABASE_URL= to that file."
        )

    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1,
        )

    try:
        parsed_url = make_url(database_url)
    except Exception as exc:
        raise RuntimeError(
            "DATABASE_URL is not a valid SQLAlchemy PostgreSQL URL."
        ) from exc

    if not parsed_url.host:
        raise RuntimeError(
            "DATABASE_URL does not contain a database hostname."
        )

    # Safe diagnostic: does not print the password.
    print(
        "Database configuration loaded:",
        f"driver={parsed_url.drivername}, "
        f"host={parsed_url.host}, "
        f"port={parsed_url.port or 5432}, "
        f"database={parsed_url.database}",
    )

    return database_url


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    poolclass=NullPool,
    connect_args={
        "sslmode": "require",
        "connect_timeout": 10,
    },
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()