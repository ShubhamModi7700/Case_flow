from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.services.case_access import has_global_case_access, require_case_view


def _vector_literal(vector: list[float]) -> str:
    if not vector:
        raise ValueError("Der Abfragevektor darf nicht leer sein.")

    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def _require_document_scope(
    *,
    db: Session,
    user: models.User,
    document_id: int,
) -> models.Document:
    """Validate document visibility before any semantic retrieval is executed.

    Documents linked to a case inherit that case's visibility. Unassigned
    documents are visible to global case roles only until a dedicated document
    ACL/ownership model is introduced.
    """
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id)
        .first()
    )
    if document is None:
        raise ValueError("Dokument nicht gefunden.")

    if document.case_id is None:
        if not has_global_case_access(user):
            raise PermissionError("Kein Zugriff auf dieses Dokument.")
    else:
        require_case_view(db, user, document.case_id)

    return document


def retrieve_chunks(
    *,
    db: Session,
    user: models.User,
    query_embedding: list[float],
    case_id: int | None = None,
    document_id: int | None = None,
    threshold: float = 0.55,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Retrieve evidence only from data visible to ``user``.

    Phase 5A applies authorization before vector results exist. The ACL predicate
    is part of the SQL vector query itself; inaccessible chunks cannot become
    retrieval candidates and therefore cannot be sent to OpenAI.
    """
    if case_id is not None:
        require_case_view(db, user, case_id)

    if document_id is not None:
        document = _require_document_scope(
            db=db,
            user=user,
            document_id=document_id,
        )
        if (
            case_id is not None
            and document.case_id is not None
            and document.case_id != case_id
        ):
            raise ValueError("Das Dokument gehört nicht zum angeforderten Fall.")

    # Do not call the legacy global match_document_chunks() RPC here. Keeping
    # the ACL inside this vector query guarantees that unauthorized rows are
    # filtered before ranking/limiting, not after retrieval.
    statement = text(
        """
        select
            dc.id as chunk_id,
            dc.document_id as document_id,
            d.case_id as case_id,
            d.file_name as file_name,
            dc.content as content,
            dc.source_type as source_type,
            dc.page_number as page_number,
            dc.sheet_name as sheet_name,
            dc.email_section as email_section,
            dc.metadata as metadata,
            (1 - (dc.embedding <=> cast(:query_embedding as extensions.vector)))::float
                as similarity
        from public.document_chunks dc
        join public.documents d on d.id = dc.document_id
        where dc.embedding is not null
          and (
                exists (
                    select 1
                    from public.users u
                    where u.id = :requesting_user_id
                      and u.is_active = true
                      and lower(coalesce(u.role, '')) in
                          ('manager', 'shareholder', 'admin')
                )
                or (
                    d.case_id is not null
                    and exists (
                        select 1
                        from public.case_access ca
                        where ca.case_id = d.case_id
                          and ca.user_id = :requesting_user_id
                    )
                )
          )
          and (:requested_case_id is null or d.case_id = :requested_case_id)
          and (:requested_document_id is null or d.id = :requested_document_id)
          and (
              1 - (dc.embedding <=> cast(:query_embedding as extensions.vector))
          ) >= :match_threshold
        order by dc.embedding <=> cast(:query_embedding as extensions.vector)
        limit :match_count
        """
    )

    result = db.execute(
        statement,
        {
            "query_embedding": _vector_literal(query_embedding),
            "requesting_user_id": user.id,
            "requested_case_id": case_id,
            "requested_document_id": document_id,
            "match_threshold": threshold,
            "match_count": max(limit, 0),
        },
    )

    return [dict(row._mapping) for row in result]


def match_cases(
    *,
    db: Session,
    user: models.User,
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Match only cases that are already visible to ``user``.

    Authorization is evaluated in SQL before cosine ranking and LIMIT. As a
    result, an inaccessible case cannot even become a candidate supplied to an
    OpenAI routing prompt.
    """
    statement = text(
        """
        select
            ce.case_id as case_id,
            (1 - (ce.embedding <=> cast(:query_embedding as extensions.vector)))::float
                as similarity
        from public.case_embeddings ce
        where ce.embedding is not null
          and (
                exists (
                    select 1
                    from public.users u
                    where u.id = :requesting_user_id
                      and u.is_active = true
                      and lower(coalesce(u.role, '')) in
                          ('manager', 'shareholder', 'admin')
                )
                or exists (
                    select 1
                    from public.case_access ca
                    where ca.case_id = ce.case_id
                      and ca.user_id = :requesting_user_id
                )
          )
        order by ce.embedding <=> cast(:query_embedding as extensions.vector)
        limit :match_count
        """
    )

    result = db.execute(
        statement,
        {
            "query_embedding": _vector_literal(query_embedding),
            "requesting_user_id": user.id,
            "match_count": max(limit, 0),
        },
    )

    return [dict(row._mapping) for row in result]
