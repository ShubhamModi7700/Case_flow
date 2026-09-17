from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app import models, schemas


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_ai_query_log(
    *,
    db: Session,
    user_id: int,
    case_id: int,
    task_type: str,
    question: str,
    model_name: str,
    prompt_version: str,
) -> models.AIQueryLog:
    query = models.AIQueryLog(
        user_id=user_id,
        case_id=case_id,
        task_type=task_type,
        question=question.strip(),
        provider="openai",
        model_name=model_name,
        prompt_version=prompt_version,
        status="Started",
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


def record_ai_query_sources(
    *,
    db: Session,
    query: models.AIQueryLog,
    chunks: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> None:
    chunk_by_id = {
        chunk.get("chunk_id"): chunk
        for chunk in chunks
        if chunk.get("chunk_id") is not None
    }

    for source in sources:
        chunk = chunk_by_id.get(source.get("chunk_id"), {})
        db.add(
            models.AIQuerySourceLog(
                ai_query_id=query.id,
                document_id=source.get("document_id"),
                chunk_id=source.get("chunk_id"),
                source_id=source["source_id"],
                filename=source.get("filename") or "Unbekanntes Dokument",
                document_date=source.get("document_date"),
                sender=source.get("sender"),
                page_number=source.get("page_number"),
                sheet_name=source.get("sheet_name"),
                email_section=source.get("email_section"),
                similarity=chunk.get("similarity"),
            )
        )

    query.source_count = len(sources)
    db.add(query)
    db.commit()


def referenced_source_ids(result: schemas.CaseAssistantModelAnswer) -> set[str]:
    """Return source IDs that survived validation and are present in the result."""
    ids: set[str] = set(re.findall(r"\[(S\d+)\]", result.answer or ""))

    for item in result.claims:
        ids.update(item.source_ids)
    for item in result.contradictions:
        ids.update(item.source_ids)
    for item in result.chronology:
        ids.update(item.source_ids)
    for item in result.evidence:
        ids.update(item.source_ids)
    for item in result.entities:
        ids.update(item.source_ids)

    package = result.brief_evidence_package
    if package is not None:
        for item in package.established_facts:
            ids.update(item.source_ids)
        for item in package.key_evidence:
            ids.update(item.source_ids)
        for item in package.relevant_events:
            ids.update(item.source_ids)
        for item in package.relevant_entities:
            ids.update(item.source_ids)

    outline = result.brief_outline
    if outline is not None:
        for section in outline.sections:
            for item in section.factual_basis:
                ids.update(item.source_ids)
            for item in section.evidence_notes:
                ids.update(item.source_ids)

    draft = result.brief_draft
    if draft is not None:
        for item in draft.introduction:
            ids.update(item.source_ids)
        for section in draft.sections:
            for item in section.paragraphs:
                ids.update(item.source_ids)
        for item in draft.conclusion:
            ids.update(item.source_ids)

    review = result.brief_review
    if review is not None:
        for item in review.counterarguments:
            ids.update(item.source_ids)
        for item in review.factual_risks:
            ids.update(item.source_ids)
        for item in review.contradictions:
            ids.update(item.source_ids)

    return ids


def mark_ai_query_completed(
    *,
    db: Session,
    query_id: int,
    result: schemas.CaseAssistantModelAnswer,
) -> None:
    query = db.get(models.AIQueryLog, query_id)
    if query is None:
        raise RuntimeError(f"AI audit query {query_id} no longer exists.")

    used_ids = referenced_source_ids(result)
    for source in query.sources:
        source.used_in_output = source.source_id in used_ids

    query.output_json = result.model_dump(mode="json")
    query.status = "Completed"
    query.completed_at = _utc_now()
    query.error_message = None
    db.add(query)
    db.commit()


def mark_ai_query_failed(
    *,
    db: Session,
    query_id: int,
    error: object,
) -> None:
    query = db.get(models.AIQueryLog, query_id)
    if query is None:
        return

    message = str(error).strip() or error.__class__.__name__
    query.status = "Failed"
    query.error_message = message[:4000]
    query.completed_at = _utc_now()
    db.add(query)
    db.commit()
