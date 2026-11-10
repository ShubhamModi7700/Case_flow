"""Authenticated, one-shot queue runner for scheduled invocations.

IMPORTANT: This is not a resumable PDF/attachment processor. Use only for jobs
that fit within the configured Vercel function duration.
"""
import hmac
import os
import logging
from fastapi import APIRouter, Header, HTTPException
from app import models
from app.database import SessionLocal
from app.services.document_jobs import claim, finish
from app.services.document_indexing import index_document

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)

@router.post("/process-next-document", include_in_schema=False)
def process_next_document(authorization: str | None = Header(default=None)):
    secret = os.getenv("CASEFLOW_CRON_SECRET", "")
    if len(secret) < 32 or not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if os.getenv("ENABLE_SERVERLESS_DOCUMENT_PROCESSING", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="Serverless processing disabled")

    with SessionLocal() as db:
        claimed = claim(db)
    if claimed is None:
        return {"status": "idle"}
    job_id, document_id = claimed
    error = None
    try:
        with SessionLocal() as db:
            document = db.get(models.Document, document_id)
            if document is None:
                raise RuntimeError("Document was deleted")
            if document.embedding_status != "Ready" or document.processing_status not in {"Ready", "Partial"}:
                index_document(document=document, db=db)
    except Exception as exc:
        error = str(exc)
        logger.exception("Scheduled processing failed for document %s", document_id)
    finally:
        with SessionLocal() as db:
            finish(db, job_id, error)
    return {"status": "failed" if error else "processed", "document_id": document_id}
