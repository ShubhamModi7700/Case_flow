from datetime import date, datetime
from enum import Enum

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

    company: str = Field(
        min_length=1,
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
    description: str | None = None
    next_action: str | None = None

    primary_deadline: date | None = None
    follow_up_date: date | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_case_title(cls, value: str) -> str:
        return clean_required_text(value, "Title")

    @field_validator("company", mode="before")
    @classmethod
    def normalize_company(cls, value: str) -> str:
        return clean_required_text(value, "Company")

    @field_validator(
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


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    company: str | None = Field(
        default=None,
        min_length=1,
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
    description: str | None = None
    next_action: str | None = None

    primary_deadline: date | None = None
    follow_up_date: date | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_optional_case_title(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return clean_required_text(value, "Title")

    @field_validator("company", mode="before")
    @classmethod
    def normalize_optional_company(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return clean_required_text(value, "Company")

    @field_validator(
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

    responsible_person: str | None = Field(
        default=None,
        max_length=255,
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

    responsible_person: str | None = Field(
        default=None,
        max_length=255,
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

        if normalized_role not in {"Admin", "User"}:
            raise ValueError("Role must be Admin or User")

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

        if normalized_role not in {"Admin", "User"}:
            raise ValueError("Role must be Admin or User")

        return normalized_role