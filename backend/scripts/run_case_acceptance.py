from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from app import models, schemas
from app.database import SessionLocal
from app.routes.assistant import query_case_assistant
from app.services.case_access import require_case_view
from app.services.case_qa import (
    TaskType,
    build_sources,
    build_task_request_text,
    public_sources,
    retrieve_case_evidence,
)

TASK_TYPES: tuple[TaskType, ...] = (
    "question", "chronology", "evidence", "entities",
    "brief_evidence", "brief_outline", "brief_draft", "brief_review", "intelligence",
)


@dataclass
class AcceptanceResult:
    case_id: int
    user_id: int
    task_type: str
    query: str
    mode: str
    retrieved_source_count: int
    retrieved_sources: list[dict[str, Any]]
    model_checked: bool
    model_referenced_source_ids: list[str]
    invalid_model_source_ids: list[str]
    audit_query_id: int | None
    audit_status: str | None
    audit_source_count: int
    passed: bool
    failures: list[str]


def _public_source_record(source: Any) -> dict[str, Any]:
    if hasattr(source, "model_dump"):
        return source.model_dump(mode="json")
    return dict(source)


def _source_ids_from_response(response: schemas.CaseAssistantResponse) -> set[str]:
    from app.services.ai_audit import referenced_source_ids
    # CaseAssistantResponse extends the model answer, so the audit helper can validate it.
    return referenced_source_ids(response)


def run(*, case_id: int, user_id: int, query: str, task_type: TaskType,
        retrieval_only: bool, limit: int | None) -> AcceptanceResult:
    failures: list[str] = []
    model_ids: set[str] = set()
    invalid_model_ids: set[str] = set()
    audit_query_id: int | None = None
    audit_status: str | None = None
    audit_source_count = 0

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        if user is None or not user.is_active:
            raise RuntimeError(f"Active user {user_id} was not found.")
        case = db.get(models.Case, case_id)
        if case is None:
            raise RuntimeError(f"Case {case_id} was not found.")
        require_case_view(db, user, case_id)

        if retrieval_only:
            # Mirror the route's retrieval input exactly (including task-specific query expansion).
            request_text = build_task_request_text(question=query, task_type=task_type, brief_context=None)
            chunks = retrieve_case_evidence(
                db=db, user=user, case_id=case_id, question=request_text,
                task_type=task_type, limit=limit,
            )
            sources = build_sources(chunks)
            safe_sources = [_public_source_record(s) for s in public_sources(sources)]
            if not sources:
                failures.append(
                    "No relevant indexed source was retrieved for this task/query. "
                    "For broad case-overview checks use --task-type intelligence or chronology; "
                    "the generic question task intentionally uses a stricter similarity threshold."
                )
        else:
            if task_type in {"brief_evidence", "brief_outline", "brief_draft", "brief_review"}:
                raise RuntimeError(
                    "The generic runner does not invent brief_context. Use --retrieval-only for brief_* "
                    "tasks or test question/chronology/evidence/entities/intelligence."
                )

            before_id = db.query(models.AIQueryLog.id).order_by(models.AIQueryLog.id.desc()).limit(1).scalar() or 0
            payload = schemas.CaseAssistantQueryRequest(question=query, task_type=task_type)
            # Call the exact same application route function used by the frontend. This exercises
            # ACL -> audit log -> retrieval -> source audit -> OpenAI -> citation validation -> completion.
            response = query_case_assistant(case_id=case_id, payload=payload, db=db, current_user=user)
            safe_sources = [_public_source_record(s) for s in response.sources]
            model_ids = _source_ids_from_response(response)
            valid_ids = {s["source_id"] for s in safe_sources}
            invalid_model_ids = model_ids - valid_ids

            audit = (
                db.query(models.AIQueryLog)
                .filter(models.AIQueryLog.id > before_id,
                        models.AIQueryLog.user_id == user_id,
                        models.AIQueryLog.case_id == case_id)
                .order_by(models.AIQueryLog.id.desc())
                .first()
            )
            if audit is None:
                failures.append("No AI audit record was created by the application route.")
            else:
                audit_query_id = audit.id
                audit_status = audit.status
                audit_source_count = len(audit.sources)
                if audit.status != "Completed":
                    failures.append(f"AI audit record ended with status {audit.status!r}, not 'Completed'.")
                if audit_source_count != len(safe_sources):
                    failures.append(
                        f"Audit/source mismatch: response has {len(safe_sources)} sources but audit has {audit_source_count}."
                    )

            if not safe_sources:
                failures.append("The application route returned no evidence sources.")
            if invalid_model_ids:
                failures.append("The model referenced invalid source IDs: " + ", ".join(sorted(invalid_model_ids)))
            if safe_sources and not model_ids:
                failures.append("The model output did not reference any retrieved source.")

    return AcceptanceResult(
        case_id=case_id, user_id=user_id, task_type=task_type, query=query,
        mode="retrieval-only" if retrieval_only else "full-application-route",
        retrieved_source_count=len(safe_sources), retrieved_sources=safe_sources,
        model_checked=not retrieval_only,
        model_referenced_source_ids=sorted(model_ids),
        invalid_model_source_ids=sorted(invalid_model_ids),
        audit_query_id=audit_query_id, audit_status=audit_status,
        audit_source_count=audit_source_count,
        passed=not failures, failures=failures,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a generic Case Flow end-to-end RAG acceptance check.")
    parser.add_argument("--case-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--task-type", choices=TASK_TYPES, default="intelligence",
        help="Assistant task type. Default is intelligence because it is appropriate for generic case-overview acceptance checks.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional retrieval limit (retrieval-only mode).")
    parser.add_argument("--retrieval-only", action="store_true",
                        help="Check ACL-scoped retrieval only. Full mode calls the exact frontend assistant route and verifies audit records.")
    args = parser.parse_args()

    try:
        result = run(case_id=args.case_id, user_id=args.user_id, query=args.query,
                     task_type=args.task_type, retrieval_only=args.retrieval_only, limit=args.limit)
    except Exception as exc:
        print(f"ACCEPTANCE ERROR: {exc}", file=sys.stderr)
        return 2

    print("\nAcceptance result:")
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
