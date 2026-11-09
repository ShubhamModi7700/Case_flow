"""Enqueue all not-ready documents; safe to rerun."""
from app import models
from app.database import SessionLocal
from app.services.document_jobs import enqueue

def main():
    count = 0
    with SessionLocal() as db:
        ids = [item[0] for item in db.query(models.Document.id).filter(
            (models.Document.processing_status != "Ready") |
            (models.Document.embedding_status != "Ready")
        ).all()]
        for document_id in ids:
            if enqueue(db, document_id):
                count += 1
        db.commit()
    print(f"Queued {count} of {len(ids)} not-ready documents")

if __name__ == "__main__":
    main()
