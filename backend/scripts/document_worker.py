import argparse
import logging
import time
from app import models
from app.database import SessionLocal
from app.services.document_indexing import index_document
from app.services.document_jobs import claim, finish

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("caseflow.worker")


def run_once() -> bool:
    with SessionLocal() as db:
        claimed = claim(db)
    if claimed is None:
        return False
    job_id, document_id, attempt = claimed
    error = None
    try:
        with SessionLocal() as db:
            document = db.get(models.Document, document_id)
            if document is None:
                raise RuntimeError("Document was deleted")
            if document.embedding_status != "Ready" or document.processing_status not in {"Ready", "Partial"}:
                index_document(document=document, db=db)
        log.info("Processed document %s", document_id)
    except Exception as exc:
        error = str(exc)
        log.exception("Processing document %s failed", document_id)
    with SessionLocal() as db:
        if not finish(db, job_id, error, attempt=attempt):
            log.warning("Stale job completion ignored: job=%s attempt=%s", job_id, attempt)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    log.info("Document worker started (loop=%s, poll=%ss)", args.loop, args.poll_seconds)
    while True:
        try:
            did_work = run_once()
        except Exception:
            log.exception("Worker iteration failed; will retry")
            did_work = False
            if not args.loop:
                raise
        if not args.loop:
            break
        if not did_work:
            time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    main()
