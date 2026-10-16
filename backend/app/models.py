from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
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

    title = Column(String(255), nullable=False)
    company = Column(String(200), nullable=True)
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

    risk_reason = Column(Text, nullable=True)
    suggested_risk = Column(String(20), nullable=True)
    suggested_risk_reason = Column(Text, nullable=True)
    risk_is_manual = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    management_summary = Column(Text, nullable=True)
    financial_amount = Column(Numeric(14, 2), nullable=True)
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
        passive_deletes=True,
    )

    history_entries = relationship(
        "History",
        back_populates="case",
        cascade="all, delete-orphan",
    )

    access_entries = relationship(
        "CaseAccess",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class CaseAccess(Base):
    __tablename__ = "case_access"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_case_access_case_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    can_edit = Column(Boolean, nullable=False, default=False)

    case = relationship("Case", back_populates="access_entries")
    user = relationship("User")


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
    category = Column(String(120), nullable=True, index=True)
    responsible_person = Column(String(500), nullable=True)

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
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    file_name = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    content_type = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    uploaded_by = Column(String(200), nullable=True)

    uploaded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    processing_status = Column(String(40), nullable=False, default="Uploaded")
    processing_error = Column(Text, nullable=True)
    embedding_status = Column(String(40), nullable=False, default="Pending")
    chunk_count = Column(Integer, nullable=False, default=0)
    processed_at = Column(DateTime(timezone=True), nullable=True)

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

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(String(30), nullable=False)
    page_number = Column(Integer, nullable=True)
    sheet_name = Column(String(255), nullable=True)
    email_section = Column(String(100), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    token_count = Column(Integer, nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    embedding_model = Column(String(100), nullable=False)
    embedding_version = Column(String(30), nullable=False, default="v1")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AIQueryLog(Base):
    """Audit record for every Case Assistant request.

    The request is persisted before semantic retrieval starts. This makes it
    possible to prove who asked what, for which case, with which task/model,
    even when retrieval or the OpenAI request later fails.
    """

    __tablename__ = "ai_queries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    case_id = Column(
        Integer,
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_type = Column(String(40), nullable=False)
    question = Column(Text, nullable=False)
    provider = Column(String(40), nullable=False, default="openai")
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False, default="Started", index=True)
    source_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    output_json = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    sources = relationship(
        "AIQuerySourceLog",
        back_populates="query",
        cascade="all, delete-orphan",
    )


class AIQuerySourceLog(Base):
    """Snapshot of every evidence chunk supplied to the model for a query.

    Snapshot fields intentionally remain even if a source document/chunk is
    later deleted, while the foreign-key IDs are cleared with SET NULL.
    """

    __tablename__ = "ai_query_sources"
    __table_args__ = (
        UniqueConstraint(
            "ai_query_id",
            "chunk_id",
            name="uq_ai_query_sources_query_chunk",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    ai_query_id = Column(
        Integer,
        ForeignKey("ai_queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_id = Column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_id = Column(String(20), nullable=False)
    filename = Column(String(500), nullable=False)
    document_date = Column(String(100), nullable=True)
    sender = Column(String(500), nullable=True)
    page_number = Column(Integer, nullable=True)
    sheet_name = Column(String(255), nullable=True)
    email_section = Column(String(100), nullable=True)
    similarity = Column(Float, nullable=True)
    used_in_output = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    query = relationship("AIQueryLog", back_populates="sources")


class CaseEmbedding(Base):
    __tablename__ = "case_embeddings"

    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    searchable_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    embedding_model = Column(String(100), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AIDocumentSuggestion(Base):
    __tablename__ = "ai_document_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    current_case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    suggested_case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    case_match_confidence = Column(Numeric(5, 4), nullable=True)
    suggested_summary = Column(Text, nullable=True)
    suggested_latest_development = Column(Text, nullable=True)
    suggested_deadline = Column(Date, nullable=True)
    deadline_source = Column(Text, nullable=True)
    suggested_next_action = Column(Text, nullable=True)
    suggested_risk = Column(String(20), nullable=True)
    suggested_risk_reason = Column(Text, nullable=True)
    relevant_chunk_ids = Column(JSONB, nullable=False, default=list)
    relevant_document_ids = Column(JSONB, nullable=False, default=list)
    status = Column(String(40), nullable=False, default="Pending")
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    raw_response = Column(JSONB, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class CaseIntelligenceSnapshot(Base):
    """Persisted Step 14 Case-Intelligence snapshot.

    Freshness is determined from an input fingerprint of authoritative case,
    task and processed-document state. Original documents remain untouched.
    """

    __tablename__ = "case_intelligence_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    generated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ai_query_id = Column(Integer, ForeignKey("ai_queries.id", ondelete="SET NULL"), nullable=True)
    input_fingerprint = Column(String(64), nullable=False, index=True)
    intelligence_json = Column(JSONB, nullable=False)
    work_status_json = Column(JSONB, nullable=False)
    sources_json = Column(JSONB, nullable=False, default=list)
    source_document_ids = Column(JSONB, nullable=False, default=list)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)



class CaseAISummary(Base):
    __tablename__ = "case_ai_summaries"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    short_case_summary = Column(Text, nullable=True)
    document_facts = Column(JSONB, nullable=False, default=list)
    document_fact_sources = Column(JSONB, nullable=False, default=list)
    interpretation = Column(Text, nullable=True)
    responsible_role = Column(String(200), nullable=True)
    action_justification = Column(Text, nullable=True)
    uncertainty_notes = Column(JSONB, nullable=False, default=list)
    latest_development = Column(Text, nullable=True)
    next_required_action = Column(Text, nullable=True)
    open_deadline = Column(Date, nullable=True)
    deadline_comment = Column(Text, nullable=True)
    suggested_risk = Column(String(20), nullable=True)
    risk_comment = Column(Text, nullable=True)
    suggested_status = Column(String(30), nullable=True)
    status_reason = Column(Text, nullable=True)
    relevant_document_ids = Column(JSONB, nullable=False, default=list)
    relevant_chunk_ids = Column(JSONB, nullable=False, default=list)
    status = Column(String(30), nullable=False, default="Pending")
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class AssistantChatMessage(Base):
    """Private per-user, per-case conversation messages. Never share across users."""
    __tablename__ = "assistant_chat_messages"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    response_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
