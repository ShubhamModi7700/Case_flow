from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _vector_literal(vector: list[float]) -> str:
    if not vector:
        raise ValueError("Der Abfragevektor darf nicht leer sein.")

    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def retrieve_chunks(
    *,
    db: Session,
    query_embedding: list[float],
    case_id: int | None = None,
    document_id: int | None = None,
    threshold: float = 0.55,
    limit: int = 12,
) -> list[dict[str, Any]]:
    statement = text(
        """
        select *
        from public.match_document_chunks(
            cast(:query_embedding as extensions.vector),
            :requested_case_id,
            :requested_document_id,
            :match_threshold,
            :match_count
        )
        """
    )

    result = db.execute(
        statement,
        {
            "query_embedding": _vector_literal(query_embedding),
            "requested_case_id": case_id,
            "requested_document_id": document_id,
            "match_threshold": threshold,
            "match_count": limit,
        },
    )

    return [
        dict(row._mapping)
        for row in result
    ]


def match_cases(
    *,
    db: Session,
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict[str, Any]]:
    statement = text(
        """
        select *
        from public.match_cases(
            cast(:query_embedding as extensions.vector),
            :match_count
        )
        """
    )

    result = db.execute(
        statement,
        {
            "query_embedding": _vector_literal(query_embedding),
            "match_count": limit,
        },
    )

    return [
        dict(row._mapping)
        for row in result
    ]