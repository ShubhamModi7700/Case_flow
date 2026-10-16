"""Run the manager's real insolvency-case acceptance test.

This is intentionally a live acceptance runner: it uses the configured database,
ACLs, embeddings and (unless --retrieval-only is supplied) the configured AI
provider. It does not seed or alter case documents.

Example:
    python -m scripts.run_insolvency_acceptance --case-id 42 --user-id 7

Exit status 0 means the minimum acceptance criteria passed. A non-zero exit
status prints the missing criteria so the run can be used in CI or a demo
checklist.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from typing import Any

from app import models
from app.database import SessionLocal
from app.services.case_access import require_case_view
from app.services.case_qa import (
    answer_case_question,
    build_sources,
    public_sources,
    retrieve_case_evidence,
)

DEFAULT_QUESTION = (
    "Bereite die Tatsachengrundlage für einen Schriftsatz zur Frage vor, ob eine "
    "weitere Zeugenvernehmung zu den bereits übergebenen Buchhaltungsunterlagen "
    "noch Erkenntnisgewinn verspricht. Ermittle selbständig die früheren Übergaben "
    "und belege jede Tatsachenbehauptung mit Quellen. Kennzeichne Lücken und "
    "Widersprüche ausdrücklich."
)

ACCOUNTING_TERMS = (
    "buchhaltung",
    "buchhaltungsunterlagen",
    "kontenblatt",
    "kontenblätter",
    "buchungsjournal",
    "op-liste",
)

SEPTEMBER_PATTERNS = (
    r"2025-09",
    r"sep(?:tember)?\s+2025",
    r"26[.\-/ ]0?9[.\-/ ]2025",
    r"26\s+sep(?:tember)?\s+2025",
)
OCTOBER_PATTERNS = (
    r"2025-10",
    r"okt(?:ober)?\s+2025",
    r"oct(?:ober)?\s+2025",
    r"17[.\-/ ]10[.\-/ ]2025",
    r"17\s+oct(?:ober)?\s+2025",
)


@dataclass
class AcceptanceResult:
    case_id: int
    user_id: int
    retrieved_source_count: int
    accounting_sources: list[str]
    september_sources: list[str]
    october_sources: list[str]
    model_checked: bool
    model_referenced_source_ids: list[str]
    has_explicit_uncertainty: bool
    passed: bool
    failures: list[str]


def _source_text(source: dict[str, Any]) -> str:
    values = (
        source.get("filename"),
        source.get("document_date"),
        source.get("sender"),
        source.get("content"),
        source.get("parent_filename"),
        source.get("root_email_filename"),
    )
    return " ".join(str(value) for value in values if value).casefold()


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _source_ids_matching(sources: list[dict[str, Any]], predicate) -> list[str]:
    return [source["source_id"] for source in sources if predicate(_source_text(source))]


def _collect_model_source_ids(result: Any) -> set[str]:
    from app.services.ai_audit import referenced_source_ids

    return referenced_source_ids(result)


def run(case_id: int, user_id: int, question: str, retrieval_only: bool) -> AcceptanceResult:
    failures: list[str] = []

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        if user is None or not user.is_active:
            raise RuntimeError(f"Active user {user_id} was not found.")

        case = db.get(models.Case, case_id)
        if case is None:
            raise RuntimeError(f"Case {case_id} was not found.")

        require_case_view(db, user, case_id)

        chunks = retrieve_case_evidence(
            db=db,
            user=user,
            case_id=case_id,
            question=question,
            task_type="brief_evidence",
            limit=40,
        )
        sources = build_sources(chunks)

        accounting = _source_ids_matching(
            sources,
            lambda text: any(term in text for term in ACCOUNTING_TERMS),
        )
        september = _source_ids_matching(
            sources,
            lambda text: any(term in text for term in ACCOUNTING_TERMS)
            and _matches_any(text, SEPTEMBER_PATTERNS),
        )
        october = _source_ids_matching(
            sources,
            lambda text: any(term in text for term in ACCOUNTING_TERMS)
            and _matches_any(text, OCTOBER_PATTERNS),
        )

        if not accounting:
            failures.append("No retrieved source mentions accounting records.")
        if not september:
            failures.append("No September 2025 accounting-delivery source was retrieved.")
        if not october:
            failures.append("No October 2025 accounting-delivery source was retrieved.")

        model_ids: set[str] = set()
        has_uncertainty = False

        if not retrieval_only:
            result = answer_case_question(
                question=question,
                sources=sources,
                task_type="brief_evidence",
                brief_context=__import__("app.schemas", fromlist=["AssistantBriefContext"]).AssistantBriefContext(
                    client="Acceptance-Test: bestehender Insolvenzvorgang",
                    objective="Schriftsatz zur Relevanz bzw. zum Erkenntnisgewinn einer weiteren Zeugenvernehmung vorbereiten",
                ),
            )
            model_ids = _collect_model_source_ids(result)

            if september and not model_ids.intersection(september):
                failures.append("The model did not cite a retrieved September 2025 delivery source.")
            if october and not model_ids.intersection(october):
                failures.append("The model did not cite a retrieved October 2025 delivery source.")

            has_uncertainty = bool(
                result.missing_information
                or result.unsupported_statements
                or result.contradictions
                or (
                    result.brief_evidence_package
                    and (
                        result.brief_evidence_package.open_issues
                    )
                )
            )
            if not has_uncertainty:
                failures.append("The result contains no explicit gap, contradiction, or unsupported-statement signal.")

            print("\nValidated public sources:")
            for source in public_sources(sources):
                print(
                    f"  {source.source_id}: {source.filename} | date={source.document_date or '-'} "
                    f"| sender={source.sender or '-'} | page={source.page_number or '-'}"
                )

        return AcceptanceResult(
            case_id=case_id,
            user_id=user_id,
            retrieved_source_count=len(sources),
            accounting_sources=accounting,
            september_sources=september,
            october_sources=october,
            model_checked=not retrieval_only,
            model_referenced_source_ids=sorted(model_ids),
            has_explicit_uncertainty=has_uncertainty,
            passed=not failures,
            failures=failures,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the insolvency-case RAG acceptance test.")
    parser.add_argument("--case-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Check ACL-scoped retrieval without making the final model call.",
    )
    args = parser.parse_args()

    try:
        result = run(args.case_id, args.user_id, args.question, args.retrieval_only)
    except Exception as exc:
        print(f"ACCEPTANCE ERROR: {exc}", file=sys.stderr)
        return 2

    print("\nAcceptance result:")
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
