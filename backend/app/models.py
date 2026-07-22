from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name = Column(
        String(200),
        nullable=False,
    )

    hashed_password = Column(
        String(500),
        nullable=False,
    )

    role = Column(
        String(50),
        nullable=False,
        default="User",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)

    company = Column(String(200), nullable=False)
    department = Column(String(200), nullable=True)
    category = Column(String(50), nullable=False)

    external_contact = Column(String(200), nullable=True)
    responsible_person = Column(String(200), nullable=True)

    status = Column(
        String(50),
        nullable=False,
        default="New",
    )

    risk = Column(
        String(20),
        nullable=False,
        default="Low",
    )

    description = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)

    primary_deadline = Column(Date, nullable=True)
    follow_up_date = Column(Date, nullable=True)

    is_archived = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    ai_summary = Column(Text, nullable=True)
    suggested_next_action = Column(Text, nullable=True)
    risk_summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    tasks = relationship(
        "Task",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    documents = relationship(
        "Document",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    history_entries = relationship(
        "History",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    case_id = Column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    responsible_person = Column(String(200), nullable=True)

    due_date = Column(Date, nullable=True)

    priority = Column(
        String(20),
        nullable=False,
        default="Medium",
    )

    status = Column(
        String(20),
        nullable=False,
        default="Open",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    case = relationship(
        "Case",
        back_populates="tasks",
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    case_id = Column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    file_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=False)
    uploaded_by = Column(String(200), nullable=True)

    uploaded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    case = relationship(
        "Case",
        back_populates="documents",
    )


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)

    case_id = Column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    change = Column(String(255), nullable=False)
    note = Column(Text, nullable=True)
    responsible_person = Column(String(200), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    case = relationship(
        "Case",
        back_populates="history_entries",
    )