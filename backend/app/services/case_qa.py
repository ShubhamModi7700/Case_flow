from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app import models, schemas
from app.services.embeddings import create_query_embedding
from app.services.openai_client import analysis_model, get_openai_client
from app.services.retrieval import retrieve_chunks


SYSTEM_PROMPT = """
Du bist der KI-Assistent der Anwendung Case Flow.

Beantworte ausschließlich die konkrete Frage zum ausgewählten Vorgang.
Dir werden nur bereits durch Case Flow freigegebene Evidenzblöcke übergeben.

VERBINDLICHE REGELN:
1. Verwende ausschließlich die bereitgestellte Evidenz. Erfinde keine Tatsachen.
2. Jede Tatsachenbehauptung in `claims` muss mindestens eine gültige Quellen-ID
   wie S1 oder S2 enthalten.
3. Nutze ausschließlich die gelieferten Quellen-IDs. Erfinde keine IDs,
   Dateinamen, Daten, Absender, Seiten oder Abschnitte.
4. Die Freitextantwort soll die wichtigsten Quellen direkt als [S1], [S2] usw.
   nennen.
5. Widersprechen sich Quellen, erfasse den Widerspruch ausdrücklich unter
   `contradictions` und nenne die betroffenen Quellen-IDs.
6. Informationen, die zur Beantwortung fehlen, gehören in
   `missing_information`.
7. Aussagen, die anhand der Evidenz nicht belegt werden können, gehören in
   `unsupported_statements` und dürfen nicht als Tatsache formuliert werden.
8. Wenn die Evidenz keine belastbare Antwort erlaubt, sage das klar.
9. Antworte auf Deutsch.
""".strip()


def retrieve_case_evidence(
    *,
    db: Session,
    user: models.User,
    case_id: int,
    question: str,
    limit: int = 15,
) -> list[dict[str, Any]]:
    query_embedding = create_query_embedding(question)
    return retrieve_chunks(
        db=db,
        user=user,
        query_embedding=query_embedding,
        case_id=case_id,
        threshold=0.45,
        limit=limit,
    )


def build_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata") or {}
        sources.append(
            {
                "source_id": f"S{index}",
                "chunk_id": int(chunk["chunk_id"]),
                "document_id": int(chunk["document_id"]),
                "filename": chunk.get("file_name") or f"Dokument {chunk['document_id']}",
                "document_date": metadata.get("document_date"),
                "sender": metadata.get("sender"),
                "page_number": chunk.get("page_number"),
                "sheet_name": chunk.get("sheet_name"),
                "email_section": chunk.get("email_section"),
                "content": chunk["content"],
            }
        )
    return sources


def _source_context(source: dict[str, Any]) -> str:
    lines = [
        f"[{source['source_id']}]",
        f"Dokument: {source['filename']}",
    ]
    if source.get("document_date"):
        lines.append(f"Datum: {source['document_date']}")
    if source.get("sender"):
        lines.append(f"Absender: {source['sender']}")
    if source.get("page_number") is not None:
        lines.append(f"Seite: {source['page_number']}")
    if source.get("sheet_name"):
        lines.append(f"Tabellenblatt: {source['sheet_name']}")
    if source.get("email_section"):
        lines.append(f"Abschnitt: {source['email_section']}")
    lines.extend(["", "Inhalt:", source["content"]])
    return "\n".join(lines)


def build_evidence_context(sources: list[dict[str, Any]]) -> str:
    return "\n\n---\n\n".join(_source_context(source) for source in sources)


def _remove_invalid_inline_citations(text: str, valid_ids: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        source_id = match.group(1)
        return match.group(0) if source_id in valid_ids else ""

    return re.sub(r"\[(S\d+)\]", replace, text).strip()


def validate_answer_sources(
    result: schemas.CaseAssistantModelAnswer,
    sources: list[dict[str, Any]],
) -> schemas.CaseAssistantModelAnswer:
    valid_ids = {source["source_id"] for source in sources}
    unsupported = list(result.unsupported_statements)

    valid_claims: list[schemas.AssistantEvidenceStatement] = []
    for claim in result.claims:
        claim.source_ids = [source_id for source_id in claim.source_ids if source_id in valid_ids]
        if claim.source_ids:
            valid_claims.append(claim)
        else:
            unsupported.append(claim.text)
    result.claims = valid_claims

    valid_contradictions: list[schemas.AssistantEvidenceStatement] = []
    for contradiction in result.contradictions:
        contradiction.source_ids = [
            source_id for source_id in contradiction.source_ids if source_id in valid_ids
        ]
        if contradiction.source_ids:
            valid_contradictions.append(contradiction)
        else:
            unsupported.append(contradiction.text)
    result.contradictions = valid_contradictions

    result.answer = _remove_invalid_inline_citations(result.answer, valid_ids)
    result.unsupported_statements = list(dict.fromkeys(item.strip() for item in unsupported if item and item.strip()))
    result.missing_information = list(
        dict.fromkeys(item.strip() for item in result.missing_information if item and item.strip())
    )
    return result


def answer_case_question(
    *,
    question: str,
    sources: list[dict[str, Any]],
) -> schemas.CaseAssistantModelAnswer:
    if not sources:
        return schemas.CaseAssistantModelAnswer(
            answer=(
                "In den aktuell durchsuchbaren Dokumenten wurden keine ausreichend "
                "relevanten Belege für diese Frage gefunden."
            ),
            missing_information=[
                "Es wurden keine passenden Evidenzstellen aus dem freigegebenen Vorgang abgerufen."
            ],
        )

    evidence_context = build_evidence_context(sources)
    response = get_openai_client().responses.parse(
        model=analysis_model(),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "FRAGE\n=====\n"
                    f"{question.strip()}\n\n"
                    "FREIGEGEBENE EVIDENZ\n====================\n"
                    f"{evidence_context}"
                ),
            },
        ],
        text_format=schemas.CaseAssistantModelAnswer,
    )
    if response.output_parsed is None:
        raise RuntimeError("Die strukturierte KI-Antwort konnte nicht gelesen werden.")
    return validate_answer_sources(response.output_parsed, sources)


def public_sources(sources: list[dict[str, Any]]) -> list[schemas.AssistantSource]:
    return [
        schemas.AssistantSource.model_validate(
            {key: value for key, value in source.items() if key != "content"}
        )
        for source in sources
    ]
