from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class CaseStatus(str, Enum):
    NEW = "New"
    UNDER_REVIEW = "Under Review"
    IN_PROGRESS = "In Progress"
    WAITING = "Waiting"
    COMPLETED = "Completed"
    CRITICAL = "Critical"


class CaseCategory(str, Enum):
    CUSTOMER = "Customer"
    CONTRACT = "Contract"
    SUPPLIER = "Supplier"
    EMPLOYEE = "Employee"
    PROJECT = "Project"
    OTHER = "Other"


class TaskPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TaskStatus(str, Enum):
    OPEN = "Open"
    COMPLETED = "Completed"


class TimelineEventType(str, Enum):
    NOTE = "Note"
    UPDATE = "Update"
    MILESTONE = "Milestone"


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    cleaned_value = value.strip()

    return cleaned_value or None


def clean_required_text(value: str, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")

    if not isinstance(value, str):
        return value

    cleaned_value = value.strip()

    if not cleaned_value:
        raise ValueError(f"{field_name} is required")

    return cleaned_value


class CaseBase(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )

    company: str | None = Field(
        default=None,
        max_length=255,
    )

    department: str | None = Field(
        default=None,
        max_length=255,
    )

    category: CaseCategory

    external_contact: str | None = Field(
        default=None,
        max_length=255,
    )

    responsible_person: str | None = Field(
        default=None,
        max_length=255,
    )

    status: CaseStatus = CaseStatus.NEW
    risk: RiskLevel = RiskLevel.LOW
    risk_reason: str | None = None
    suggested_risk: RiskLevel | None = None
    suggested_risk_reason: str | None = None
    risk_is_manual: bool = False

    management_summary: str | None = None
    financial_amount: float | None = Field(default=None, ge=0)
    description: str | None = None
    next_action: str | None = None

    primary_deadline: date | None = None
    follow_up_date: date | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_case_title(cls, value: str) -> str:
        return clean_required_text(value, "Title")

    @field_validator(
        "company",
        "department",
        "external_contact",
        "responsible_person",
        "risk_reason",
        "suggested_risk_reason",
        "management_summary",
        "description",
        "next_action",
        mode="before",
    )
    @classmethod
    def normalize_optional_fields(
        cls,
        value: str | None,
    ) -> str | None:
        return clean_optional_text(value)


class CaseAccessInput(BaseModel):
    user_id: int = Field(gt=0)
    can_edit: bool = False


class CaseAccessResponse(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    can_edit: bool


class CaseCreate(CaseBase):
    access: list[CaseAccessInput] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    company: str | None = Field(
        default=None,
        max_length=255,
    )

    department: str | None = Field(
        default=None,
        max_length=255,
    )

    category: CaseCategory | None = None

    external_contact: str | None = Field(
        default=None,
        max_length=255,
    )

    responsible_person: str | None = Field(
        default=None,
        max_length=255,
    )

    status: CaseStatus | None = None
    risk: RiskLevel | None = None
    risk_reason: str | None = None
    risk_is_manual: bool | None = None

    management_summary: str | None = None
    financial_amount: float | None = Field(default=None, ge=0)
    description: str | None = None
    next_action: str | None = None

    primary_deadline: date | None = None
    follow_up_date: date | None = None
    access: list[CaseAccessInput] | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_optional_case_title(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return clean_required_text(value, "Title")

    @field_validator(
        "company",
        "department",
        "external_contact",
        "responsible_person",
        "risk_reason",
        "management_summary",
        "description",
        "next_action",
        mode="before",
    )
    @classmethod
    def normalize_optional_fields(
        cls,
        value: str | None,
    ) -> str | None:
        return clean_optional_text(value)


class CaseResponse(CaseBase):
    id: int
    is_archived: bool
    access: list[CaseAccessResponse] = Field(default_factory=list)
    user_can_edit: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )



class TaskCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    category: str | None = Field(default=None, max_length=120)

    responsible_person: str | None = Field(
        default=None,
        max_length=500,
    )

    due_date: date | None = None

    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.OPEN

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return clean_required_text(value, "Task title")

    @field_validator(
        "description",
        "category",
        "responsible_person",
        mode="before",
    )
    @classmethod
    def normalize_optional_fields(
        cls,
        value: str | None,
    ) -> str | None:
        return clean_optional_text(value)


class TaskUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    category: str | None = Field(default=None, max_length=120)

    responsible_person: str | None = Field(
        default=None,
        max_length=500,
    )

    due_date: date | None = None

    priority: TaskPriority | None = None
    status: TaskStatus | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_optional_title(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return clean_required_text(value, "Task title")

    @field_validator(
        "description",
        "category",
        "responsible_person",
        mode="before",
    )
    @classmethod
    def normalize_optional_fields(
        cls,
        value: str | None,
    ) -> str | None:
        return clean_optional_text(value)


class TaskResponse(TaskCreate):
    id: int
    case_id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )




class HistoryResponse(BaseModel):
    id: int
    case_id: int
    change: str
    note: str | None = None
    responsible_person: str | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )



class DocumentResponse(BaseModel):
    id: int
    case_id: int | None = None
    file_name: str
    content_type: str
    file_size: int
    description: str | None = None
    uploaded_by: str | None = None
    uploaded_at: datetime
    processing_status: str = "Uploaded"
    processing_error: str | None = None
    embedding_status: str = "Pending"
    chunk_count: int = 0
    processed_at: datetime | None = None
    company: str | None = None
    department: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class DocumentDownloadResponse(BaseModel):
    download_url: str
    file_name: str
    expires_in: int


class DocumentCaseUpdate(BaseModel):
    case_id: int | None = None


class TimelineEventCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    event_type: TimelineEventType = TimelineEventType.NOTE

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return clean_required_text(value, "Timeline title")

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(
        cls,
        value: str | None,
    ) -> str | None:
        return clean_optional_text(value)


class TimelineEventResponse(BaseModel):
    id: str
    case_id: int
    event_type: str
    title: str
    description: str | None = None
    person: str | None = None
    occurred_at: datetime
    is_future: bool = False

    model_config = ConfigDict(
        from_attributes=True,
    )



class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=1,
    )


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str

    model_config = ConfigDict(
        from_attributes=True,
    )


class LoginResponse(BaseModel):
    message: str
    user: CurrentUserResponse




class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class UserCreate(BaseModel):
    email: EmailStr

    full_name: str = Field(
        min_length=2,
        max_length=200,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    role: str = "User"
    is_active: bool = True

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return clean_required_text(value, "Full name")

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        normalized_role = value.strip().title()

        if normalized_role == "Admin":
            normalized_role = "Manager"

        if normalized_role not in {"Manager", "Shareholder", "User", "Viewer"}:
            raise ValueError("Role must be Manager, Shareholder, User or Viewer")

        return normalized_role


class UserUpdate(BaseModel):
    email: EmailStr | None = None

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
    )

    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

    role: str | None = None
    is_active: bool | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_optional_full_name(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return clean_required_text(value, "Full name")

    @field_validator("role", mode="before")
    @classmethod
    def validate_optional_role(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        normalized_role = value.strip().title()

        if normalized_role == "Admin":
            normalized_role = "Manager"

        if normalized_role not in {"Manager", "Shareholder", "User", "Viewer"}:
            raise ValueError("Role must be Manager, Shareholder, User or Viewer")

        return normalized_role
class AssistantBriefContext(BaseModel):
    client: str = Field(min_length=1, max_length=500)
    role: str | None = Field(default=None, max_length=500)
    recipient: str | None = Field(default=None, max_length=500)
    document_type: str = Field(default="Schriftsatz", min_length=1, max_length=200)
    objective: str = Field(min_length=2, max_length=3000)
    additional_instructions: str | None = Field(default=None, max_length=3000)


class CaseAssistantQueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=5000)
    task_type: Literal["question", "chronology", "evidence", "entities", "brief_evidence", "brief_outline"] = "question"
    brief_context: AssistantBriefContext | None = None


class AssistantEvidenceStatement(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)


class AssistantChronologyEvent(BaseModel):
    date: str | None = None
    event: str
    source_ids: list[str] = Field(default_factory=list)


class AssistantEvidenceLink(BaseModel):
    claim: str
    relevance: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class AssistantEntity(BaseModel):
    name: str
    entity_type: Literal["Person", "Unternehmen", "Organisation", "Unbekannt"] = "Unbekannt"
    role: str | None = None
    role_is_explicit: bool = False
    source_ids: list[str] = Field(default_factory=list)


class AssistantBriefEvidencePackage(BaseModel):
    task_summary: str | None = None
    established_facts: list[AssistantEvidenceStatement] = Field(default_factory=list)
    key_evidence: list[AssistantEvidenceLink] = Field(default_factory=list)
    relevant_events: list[AssistantChronologyEvent] = Field(default_factory=list)
    relevant_entities: list[AssistantEntity] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)


class AssistantBriefOutlineSection(BaseModel):
    heading: str
    purpose: str | None = None
    factual_basis: list[AssistantEvidenceStatement] = Field(default_factory=list)
    evidence_notes: list[AssistantEvidenceLink] = Field(default_factory=list)


class AssistantBriefOutline(BaseModel):
    title: str
    objective: str | None = None
    sections: list[AssistantBriefOutlineSection] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)
    drafting_notes: list[str] = Field(default_factory=list)


class AssistantSource(BaseModel):
    source_id: str
    chunk_id: int
    document_id: int
    filename: str
    document_date: str | None = None
    sender: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None
    email_section: str | None = None
    is_attachment: bool = False
    parent_filename: str | None = None
    root_email_filename: str | None = None
    attachment_depth: int = 0


class CaseAssistantModelAnswer(BaseModel):
    answer: str
    claims: list[AssistantEvidenceStatement] = Field(default_factory=list)
    contradictions: list[AssistantEvidenceStatement] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    unsupported_statements: list[str] = Field(default_factory=list)
    chronology: list[AssistantChronologyEvent] = Field(default_factory=list)
    evidence: list[AssistantEvidenceLink] = Field(default_factory=list)
    entities: list[AssistantEntity] = Field(default_factory=list)
    brief_evidence_package: AssistantBriefEvidencePackage | None = None
    brief_outline: AssistantBriefOutline | None = None


class CaseAssistantResponse(CaseAssistantModelAnswer):
    task_type: Literal["question", "chronology", "evidence", "entities", "brief_evidence", "brief_outline"] = "question"
    sources: list[AssistantSource] = Field(default_factory=list)


class DocumentProcessingResponse(BaseModel):
    document_id: int
    processing_status: str
    embedding_status: str
    chunk_count: int
    processing_error: str | None = None


class SuggestedCaseMatch(BaseModel):
    case_id: int | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    reason: str | None = None


class RelevantDocumentResult(BaseModel):
    document_id: int
    reason: str


class DocumentAIAnalysis(BaseModel):
    suggested_summary: str
    latest_development: str | None = None
    recognized_deadline: date | None = None
    deadline_source: str | None = None
    proposed_next_action: str | None = None
    suggested_risk: RiskLevel | None = None
    risk_reason: str | None = None
    suggested_status: CaseStatus | None = None
    status_reason: str | None = None
    document_is_lawyer_letter: bool = False
    document_is_labour_law: bool = False
    detected_financial_amount: float | None = None
    proposed_case: SuggestedCaseMatch
    relevant_documents: list[RelevantDocumentResult] = Field(default_factory=list)
    supporting_chunk_ids: list[int] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)




class ManagementSummaryAnalysis(BaseModel):
    short_case_summary: str
    document_facts: list[str] = Field(default_factory=list)
    interpretation: str | None = None
    responsible_role: str | None = None
    action_justification: str | None = None
    latest_development: str | None = None
    next_required_action: str | None = None
    open_deadline: date | None = None
    deadline_comment: str | None = None
    # Current-state fields are mandatory so a management generation can never
    # silently fall back to the historical case risk/status.
    suggested_risk: RiskLevel
    risk_comment: str
    suggested_status: CaseStatus
    status_reason: str
    relevant_documents: list[RelevantDocumentResult] = Field(default_factory=list)
    supporting_chunk_ids: list[int] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


class CaseAISummaryApproval(BaseModel):
    short_case_summary: str | None = None
    document_facts: list[str] = Field(default_factory=list)
    interpretation: str | None = None
    responsible_role: str | None = None
    action_justification: str | None = None
    uncertainty_notes: list[str] = Field(default_factory=list)
    latest_development: str | None = None
    next_required_action: str | None = None
    open_deadline: date | None = None
    deadline_comment: str | None = None

    risk: RiskLevel | None = None
    risk_comment: str | None = None
    status: CaseStatus | None = None
    status_reason: str | None = None

    relevant_document_ids: list[int] = Field(default_factory=list)

class AISuggestionResponse(BaseModel):
    id: int
    document_id: int
    current_case_id: int | None = None
    suggested_case_id: int | None = None
    case_match_confidence: float | None = None
    suggested_summary: str | None = None
    suggested_latest_development: str | None = None
    suggested_deadline: date | None = None
    deadline_source: str | None = None
    suggested_next_action: str | None = None
    suggested_risk: str | None = None
    suggested_risk_reason: str | None = None
    relevant_chunk_ids: list[int] = Field(default_factory=list)
    relevant_document_ids: list[int] = Field(default_factory=list)
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AISuggestionApproval(BaseModel):
    selected_case_id: int
    summary: str | None = None
    latest_development: str | None = None
    deadline: date | None = None
    next_action: str | None = None
    risk: RiskLevel | None = None
    risk_reason: str | None = None


class CaseAISummaryResponse(BaseModel):
    id: int
    case_id: int
    short_case_summary: str | None = None
    document_facts: list[str] = Field(default_factory=list)
    interpretation: str | None = None
    responsible_role: str | None = None
    action_justification: str | None = None
    uncertainty_notes: list[str] = Field(default_factory=list)
    latest_development: str | None = None
    next_required_action: str | None = None
    open_deadline: date | None = None
    deadline_comment: str | None = None
    suggested_risk: str | None = None
    risk_comment: str | None = None
    suggested_status: str | None = None
    status_reason: str | None = None
    relevant_document_ids: list[int] = Field(default_factory=list)
    relevant_chunk_ids: list[int] = Field(default_factory=list)
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentCaseDraftResponse(BaseModel):
    title: str
    company: str | None = None
    department: str | None = None
    category: CaseCategory
    external_contact: str | None = None
    description: str | None = None
    management_summary: str | None = None
    next_action: str | None = None
    primary_deadline: date | None = None
    financial_amount: float | None = None


class DocumentCaseCandidateResponse(BaseModel):
    case_id: int
    title: str
    company: str | None = None
    category: str | None = None
    similarity: float | None = None


class DocumentCaseRouteSuggestionResponse(BaseModel):
    document_id: int
    decision: str
    suggested_case_id: int | None = None
    confidence: float
    reason: str
    new_case: DocumentCaseDraftResponse | None = None
    candidates: list[DocumentCaseCandidateResponse] = Field(default_factory=list)


class DocumentCaseRouteConfirmation(BaseModel):
    action: str
    case_id: int | None = None
    new_case: DocumentCaseDraftResponse | None = None


class DocumentCaseRouteConfirmationResponse(BaseModel):
    document_id: int
    case_id: int
    action: str
    message: str
