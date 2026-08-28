from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, require_editor
from app.database import get_db
from app.services.case_access import require_case_edit, require_case_view

router = APIRouter(prefix="/cases", tags=["Timeline"])


def get_case_or_404(case_id: int, db: Session) -> models.Case:
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden")
    return case


def event_type_for_change(change: str) -> str:
    value = (change or "").casefold()
    if value.startswith("ki-") or "ki-" in value:
        return "AI"
    if "created" in value or "erstellt" in value:
        return "Created"
    if "completed" in value or "abgeschlossen" in value:
        return "Completed"
    if "archived" in value or "archiviert" in value:
        return "Archived"
    if "task" in value or "aufgabe" in value:
        return "Task"
    if "note" in value or "notiz" in value:
        return "Note"
    return "Update"


@router.get("/{case_id}/timeline", response_model=list[schemas.TimelineEventResponse])
def get_case_timeline(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case = get_case_or_404(case_id, db)
    require_case_view(db, current_user, case_id)
    now = datetime.now(timezone.utc)
    events: list[schemas.TimelineEventResponse] = []

    history_entries = (
        db.query(models.History)
        .filter(models.History.case_id == case_id)
        .all()
    )
    for entry in history_entries:
        events.append(schemas.TimelineEventResponse(
            id=f"history-{entry.id}",
            case_id=case_id,
            event_type=event_type_for_change(entry.change),
            title=entry.change,
            description=entry.note,
            person=entry.responsible_person,
            occurred_at=entry.created_at,
            is_future=False,
        ))

    documents = (
        db.query(models.Document)
        .filter(models.Document.case_id == case_id)
        .all()
    )
    for document in documents:
        events.append(schemas.TimelineEventResponse(
            id=f"document-{document.id}",
            case_id=case_id,
            event_type="Document",
            title=f"Dokument hochgeladen: {document.file_name}",
            description=document.description,
            person=document.uploaded_by,
            occurred_at=document.uploaded_at,
            is_future=False,
        ))

    for task in case.tasks:
        if task.due_date:
            occurred_at = datetime.combine(task.due_date, time.min, tzinfo=timezone.utc)
            events.append(schemas.TimelineEventResponse(
                id=f"task-due-{task.id}",
                case_id=case_id,
                event_type="Task deadline",
                title=f"Aufgabe fällig: {task.title}",
                description=task.description,
                person=task.responsible_person,
                occurred_at=occurred_at,
                is_future=occurred_at > now and task.status != "Completed",
            ))

    # Deadlines are planning milestones, not business developments. Their
    # descriptions must not copy case.next_action, otherwise a future deadline
    # can look like the latest development in clients consuming the timeline.
    milestones = [
        ("primary-deadline", case.primary_deadline, "Hauptfrist", "Offene Hauptfrist des Falls."),
        ("follow-up", case.follow_up_date, "Wiedervorlagetermin", "Geplanter Wiedervorlagetermin des Falls."),
    ]
    for key, milestone_date, title, description in milestones:
        if milestone_date:
            occurred_at = datetime.combine(milestone_date, time.min, tzinfo=timezone.utc)
            events.append(schemas.TimelineEventResponse(
                id=f"{key}-{case.id}",
                case_id=case_id,
                event_type="Milestone",
                title=title,
                description=description,
                person=case.responsible_person,
                occurred_at=occurred_at,
                is_future=occurred_at > now,
            ))

    return sorted(events, key=lambda event: event.occurred_at, reverse=True)


@router.post(
    "/{case_id}/timeline",
    response_model=schemas.TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_timeline_event(
    case_id: int,
    event_data: schemas.TimelineEventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_editor),
):
    get_case_or_404(case_id, db)
    require_case_edit(db, current_user, case_id)

    entry = models.History(
        case_id=case_id,
        change=event_data.title,
        note=event_data.description,
        responsible_person=current_user.full_name,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return schemas.TimelineEventResponse(
        id=f"history-{entry.id}",
        case_id=case_id,
        event_type=event_data.event_type.value,
        title=entry.change,
        description=entry.note,
        person=entry.responsible_person,
        occurred_at=entry.created_at,
        is_future=False,
    )
