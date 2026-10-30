"""Phase 2 foundation: deterministic, source-validated findings for a single answer.

This module deliberately does not infer facts from prose or claim cross-turn persistence.
It consumes the assistant's already validated structured output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FindingKind = Literal["documented", "conflict", "missing_evidence"]


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    text: str
    source_ids: tuple[str, ...]
    document_ids: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_ids"] = list(self.source_ids)
        data["document_ids"] = list(self.document_ids)
        return data


def build_findings_ledger(answer: Any, sources: list[dict[str, Any]]) -> list[Finding]:
    """Extract only explicitly structured findings, never unsupported narrative.

    A conflict requires at least two distinct cited source locations. A single
    source describing two versions may still be useful evidence, but is not
    automatically a verified inter-document contradiction.
    """
    source_map = {str(s["source_id"]): s for s in sources if s.get("source_id")}
    result: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: FindingKind, text: str, ids: list[str]) -> None:
        clean = " ".join(str(text).split()).strip()
        valid = tuple(dict.fromkeys(str(i) for i in ids if str(i) in source_map))
        if not clean or (kind != "missing_evidence" and not valid):
            return
        key = (kind, clean.casefold())
        if key in seen:
            return
        seen.add(key)
        docs = tuple(dict.fromkeys(int(source_map[i]["document_id"]) for i in valid))
        result.append(Finding(kind, clean, valid, docs))

    for item in getattr(answer, "claims", []) or []:
        add("documented", item.text, item.source_ids)
    for item in getattr(answer, "contradictions", []) or []:
        add("conflict", item.text, item.source_ids)
    for item in getattr(answer, "missing_information", []) or []:
        add("missing_evidence", str(item), [])
    return result
