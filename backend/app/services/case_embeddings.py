from sqlalchemy.orm import Session

from app import models
from app.services.embeddings import create_query_embedding
from app.services.openai_client import embedding_model


def build_case_search_text(case: models.Case) -> str:
    return "\n".join([
        f"Titel: {case.title or ''}",
        f"Unternehmen: {case.company or ''}",
        f"Abteilung: {case.department or ''}",
        f"Kategorie: {case.category or ''}",
        f"Beschreibung: {case.description or ''}",
        f"Management-Zusammenfassung: {case.management_summary or ''}",
        f"Nächste Maßnahme: {case.next_action or ''}",
    ])


def refresh_case_embedding(*, case: models.Case, db: Session) -> None:
    text = build_case_search_text(case)
    vector = create_query_embedding(text)
    record = db.query(models.CaseEmbedding).filter(
        models.CaseEmbedding.case_id == case.id
    ).first()
    if record is None:
        record = models.CaseEmbedding(case_id=case.id)
        db.add(record)
    record.searchable_text = text
    record.embedding = vector
    record.embedding_model = embedding_model()
    db.commit()
