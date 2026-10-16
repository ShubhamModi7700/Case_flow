from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app import models, schemas


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _stable_payload(*, case: models.Case, tasks: Iterable[models.Task], documents: Iterable[models.Document]) -> dict[str, Any]:
    """Return only authoritative inputs whose changes can make intelligence stale."""
    case_fields = (
        "id", "title", "company", "department", "category", "external_contact",
        "responsible_person", "status", "risk", "description", "next_action",
        "primary_deadline", "follow_up_date", "updated_at",
    )
    task_fields = (
        "id", "title", "description", "category", "responsible_person", "due_date",
        "priority", "status", "created_at",
    )
    document_fields = (
        "id", "file_name", "processing_status", "embedding_status", "chunk_count",
        "uploaded_at", "processed_at",
    )

    return {
        "case": {name: _json_value(getattr(case, name, None)) for name in case_fields},
        "tasks": [
            {name: _json_value(getattr(task, name, None)) for name in task_fields}
            for task in sorted(tasks, key=lambda item: getattr(item, "id", 0) or 0)
        ],
        "documents": [
            {name: _json_value(getattr(document, name, None)) for name in document_fields}
            for document in sorted(documents, key=lambda item: getattr(item, "id", 0) or 0)
        ],
    }


def build_input_fingerprint(*, case: models.Case, tasks: Iterable[models.Task], documents: Iterable[models.Document]) -> str:
    payload = _stable_payload(case=case, tasks=tasks, documents=documents)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def latest_snapshot(db: Session, *, case_id: int) -> models.CaseIntelligenceSnapshot | None:
    return (
        db.query(models.CaseIntelligenceSnapshot)
        .filter(models.CaseIntelligenceSnapshot.case_id == case_id)
        .order_by(models.CaseIntelligenceSnapshot.generated_at.desc(), models.CaseIntelligenceSnapshot.id.desc())
        .first()
    )


def snapshot_is_current(snapshot: models.CaseIntelligenceSnapshot, *, fingerprint: str) -> bool:
    return bool(snapshot.input_fingerprint) and snapshot.input_fingerprint == fingerprint


def response_from_snapshot(
    snapshot: models.CaseIntelligenceSnapshot,
    *,
    current_fingerprint: str,
    current_work_status: schemas.AssistantCaseWorkStatus,
) -> schemas.AssistantCaseIntelligenceResponse:
    return schemas.AssistantCaseIntelligenceResponse(
        intelligence=schemas.AssistantCaseIntelligence.model_validate(snapshot.intelligence_json),
        work_status=current_work_status,
        sources=[schemas.AssistantSource.model_validate(item) for item in (snapshot.sources_json or [])],
        freshness=schemas.AssistantCaseIntelligenceFreshness(
            snapshot_id=snapshot.id,
            status="current" if snapshot_is_current(snapshot, fingerprint=current_fingerprint) else "outdated",
            generated_at=snapshot.generated_at,
            generated_by=snapshot.generated_by,
            can_refresh=True,
        ),
    )


def persist_snapshot(
    db: Session,
    *,
    case_id: int,
    generated_by: int | None,
    ai_query_id: int | None,
    input_fingerprint: str,
    intelligence: schemas.AssistantCaseIntelligence,
    work_status: schemas.AssistantCaseWorkStatus,
    sources: list[schemas.AssistantSource],
) -> models.CaseIntelligenceSnapshot:
    snapshot = models.CaseIntelligenceSnapshot(
        case_id=case_id,
        generated_by=generated_by,
        ai_query_id=ai_query_id,
        input_fingerprint=input_fingerprint,
        intelligence_json=intelligence.model_dump(mode="json"),
        work_status_json=work_status.model_dump(mode="json"),
        sources_json=[source.model_dump(mode="json") for source in sources],
        source_document_ids=sorted({source.document_id for source in sources}),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
