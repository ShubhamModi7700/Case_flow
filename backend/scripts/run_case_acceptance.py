from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from app import models
from app.database import SessionLocal
from app.services.case_access import require_case_view
from app.services.case_qa import (
    TaskType,
    answer_case_question,
    build_sources,
    public_sources,
    retrieve_case_evidence,
)

TASK_TYPES: tuple[TaskType, ...] = (
    "question",
    "chronology",
    "evidence",
    "entities",
    "brief_evidence",
    "brief_outline",
    "brief_draft",
    "brief_review",
    "intelligence",
)


@dataclass
class AcceptanceResult:
    case_id: int
    user_id: int
    task_type: str
    query: str
    retrieved_source_count: int
    retrieved_sources: list[dict[str, Any]]
    model_checked: bool
    model_referenced_source_ids: list[str]
    invalid_model_source_ids: list[str]
    passed: bool
    failures: list[str]


def _public_source_record(source: Any) -> dict[str, Any]:
    """Return safe source metadata only; never print retrieved document content."""
    if hasattr(source, "model_dump"):
        return source.model_dump(mode="json")
    return dict(source)


def run(
    *,
    case_id: int,
    user_id: int,
    query: str,
    task_type: TaskType,
    retrieval_only: bool,
    limit: int | None,
) -> AcceptanceResult:
    failures: list[str] = []

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        if user is None or not user.is_active:
            raise RuntimeError(f"Active user {user_id} was not found.")

        case = db.get(models.Case, case_id)
        if case is None:
            raise RuntimeError(f"Case {case_id} was not found.")

        # Explicit pre-flight authorization. Retrieval enforces the same ACL a
        # second time inside the vector SQL query before ranking and LIMIT.
        require_case_view(db, user, case_id)

        chunks = retrieve_case_evidence(
            db=db,
            user=user,
            case_id=case_id,
            question=query,
            task_type=task_type,
            limit=limit,
        )
        sources = build_sources(chunks)
        safe_sources = [_public_source_record(s) for s in public_sources(sources)]

        if not sources:
            failures.append(
                "No relevant indexed source was retrieved. Check that the case has "
                "documents, document_chunks with embeddings, and that the query is relevant."
            )

        model_ids: set[str] = set()
        invalid_model_ids: set[str] = set()

        if not retrieval_only and sources:
            # Generic runner deliberately supports non-brief tasks without
            # inventing case-specific drafting context.
            if task_type in {"brief_evidence", "brief_outline", "brief_draft", "brief_review"}:
                raise RuntimeError(
                    "Generic model checking for brief_* tasks requires case-specific brief_context. "
                    "Use --retrieval-only for those tasks, or test a generic task such as question, "
                    "chronology, evidence, entities, or intelligence."
                )

            result = answer_case_question(
                question=query,
                sources=sources,
                task_type=task_type,
            )

            from app.services.ai_audit import referenced_source_ids

            model_ids = referenced_source_ids(result)
            valid_ids = {source["source_id"] for source in sources}
            invalid_model_ids = model_ids - valid_ids

            if invalid_model_ids:
                failures.append(
                    "The model referenced source IDs that were not present in the retrieved evidence: "
                    + ", ".join(sorted(invalid_model_ids))
                )
            if not model_ids:
                failures.append(
                    "The model answer did not reference any retrieved source."
                )

    return AcceptanceResult(
        case_id=case_id,
        user_id=user_id,
        task_type=task_type,
        query=query,
        retrieved_source_count=len(safe_sources),
        retrieved_sources=safe_sources,
        model_checked=not retrieval_only and bool(safe_sources),
        model_referenced_source_ids=sorted(model_ids),
        invalid_model_source_ids=sorted(invalid_model_ids),
        passed=not failures,
        failures=failures,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a generic Case Flow RAG acceptance check.")
    parser.add_argument("--case-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--query", required=True, help="Natural-language question/task for the case.")
    parser.add_argument(
        "--task-type",
        choices=TASK_TYPES,
        default="question",
        help="Case Assistant task type (default: question).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional retrieval result limit; otherwise the application task default is used.",
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Check ACL-scoped semantic retrieval without making the final model call.",
    )
    args = parser.parse_args()

    try:
        result = run(
            case_id=args.case_id,
            user_id=args.user_id,
            query=args.query,
            task_type=args.task_type,
            retrieval_only=args.retrieval_only,
            limit=args.limit,
        )
    except Exception as exc:
        print(f"ACCEPTANCE ERROR: {exc}", file=sys.stderr)
        return 2

    print("\nAcceptance result:")
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
