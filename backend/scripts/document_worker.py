import argparse
import logging
import time
import threading
import signal
import json
import re
import unicodedata
from uuid import uuid4
from app import models
from app.database import SessionLocal
from app.services.document_indexing import index_document
from app.services.document_jobs import claim, finish, renew_lease
from app.services.case_access import require_case_edit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("caseflow.worker")
shutdown_requested = threading.Event()


def _request_shutdown(signum, frame):
    log.info("Shutdown requested (signal=%s); finishing current job", signum)
    shutdown_requested.set()



def _heartbeat(job_id: int, attempt: int, stop: threading.Event) -> None:
    """Renew using a separate DB session; never share the indexing session."""
    while not stop.wait(5 * 60):
        try:
            with SessionLocal() as db:
                if not renew_lease(db, job_id, attempt=attempt):
                    log.warning("Worker lease lost: job=%s attempt=%s", job_id, attempt)
                    return
        except Exception:
            log.exception("Failed to renew lease: job=%s", job_id)


AUTO_ASSIGN_CONFIDENCE = 0.95
AUTO_ASSIGN_SIMILARITY = 0.85
AUTO_ASSIGN_MARGIN = 0.08


def _normalized_words(value: str) -> set[str]:
    """Normalize umlauts/punctuation for conservative case-title corroboration."""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return set(re.findall(r"[a-z0-9]{4,}", value))


def _has_case_specific_evidence(document_text: str, title: str) -> bool:
    """Require a distinctive case-title term in the document, not similarity alone.

    Short generic words do not qualify. This is deliberately a high-precision
    automatic-assignment gate; otherwise the suggestion stays for human review.
    """
    ignored = {"projekt", "vertrag", "kunde", "fall", "sache", "vorgang",
               "rechnung", "dokument", "angebot", "unternehmen", "service",
               "strom", "versorgung", "stromversorgung", "betreff", "anfrage"}
    title_words = {word for word in _normalized_words(title) if word not in ignored}
    return bool(title_words and title_words.intersection(_normalized_words(document_text)))


def _auto_assignment_candidate(suggestion, candidates, document_text=None):
    if suggestion.decision != "existing_case" or suggestion.suggested_case_id is None:
        return None
    if suggestion.confidence < AUTO_ASSIGN_CONFIDENCE:
        return None
    ranked = sorted((c for c in candidates if c.similarity is not None),
                    key=lambda c: c.similarity, reverse=True)
    if not ranked or ranked[0].case_id != suggestion.suggested_case_id:
        return None
    if ranked[0].similarity < AUTO_ASSIGN_SIMILARITY:
        return None
    if document_text is not None and not _has_case_specific_evidence(document_text, ranked[0].title):
        return None
    if len(ranked) > 1 and ranked[0].similarity - ranked[1].similarity < AUTO_ASSIGN_MARGIN:
        return None
    return suggestion.suggested_case_id


def run_once() -> bool:
    with SessionLocal() as db:
        claimed = claim(db)
    if claimed is None:
        return False
    job_id, document_id, attempt = claimed
    error = None
    stop = threading.Event()
    heartbeat = threading.Thread(target=_heartbeat, args=(job_id, attempt, stop), daemon=True)
    heartbeat.start()
    try:
        with SessionLocal() as db:
            document = db.get(models.Document, document_id)
            if document is None:
                raise RuntimeError("Document was deleted")
            if document.embedding_status != "Ready" or document.processing_status not in {"Ready", "Partial"}:
                index_document(document=document, db=db)
        try:
            with SessionLocal() as db:
                document = db.get(models.Document, document_id)
                if document is not None and document.case_id is None and document.embedding_status == "Ready":
                    existing = db.query(models.DocumentCaseRoutingEvent.id).filter(
                        models.DocumentCaseRoutingEvent.document_id == document_id,
                        models.DocumentCaseRoutingEvent.event_type == "suggestion",
                    ).first()
                    if existing is None:
                        batch_item = db.query(models.DocumentUploadBatchItem).filter(
                            models.DocumentUploadBatchItem.document_id == document_id
                        ).first()
                        batch = db.get(models.DocumentUploadBatch, batch_item.batch_id) if batch_item else None
                        owner = db.get(models.User, batch.owner_id) if batch else None
                        if owner is None or not owner.is_active:
                            log.info("Skipping case suggestion without an active upload owner: document=%s", document_id)
                        else:
                            from app.services.document_case_routing import suggest_for_indexed_document
                            suggestion, candidates = suggest_for_indexed_document(document=document, db=db, user=owner)
                            db.add(models.DocumentCaseRoutingEvent(
                                id=str(uuid4()), document_id=document_id, actor_id=owner.id,
                                event_type="suggestion", decision=suggestion.decision,
                                suggested_case_id=suggestion.suggested_case_id,
                                confidence=suggestion.confidence, reason=suggestion.reason,
                                details=json.dumps({
                                    "candidates": [candidate.model_dump() for candidate in candidates],
                                    "new_case": suggestion.new_case.model_dump(mode="json") if suggestion.new_case else None,
                                    "generated_by": "document_worker",
                                }, ensure_ascii=False, default=str),
                            ))
                            db.commit()
                            document_text = "\n".join(
                                row[0] for row in db.query(models.DocumentChunk.content)
                                .filter(models.DocumentChunk.document_id == document_id)
                                .order_by(models.DocumentChunk.chunk_index).all()
                            )
                            case_id = _auto_assignment_candidate(suggestion, candidates, document_text)
                            if case_id is not None:
                                try:
                                    require_case_edit(db, owner, case_id)
                                    changed = db.query(models.Document).filter(
                                        models.Document.id == document_id,
                                        models.Document.case_id.is_(None),
                                    ).update({"case_id": case_id}, synchronize_session=False)
                                    if changed:
                                        db.query(models.DocumentChunk).filter(
                                            models.DocumentChunk.document_id == document_id
                                        ).update({"case_id": case_id}, synchronize_session=False)
                                        db.add(models.DocumentCaseRoutingEvent(
                                            id=str(uuid4()), document_id=document_id, actor_id=owner.id,
                                            event_type="auto_assignment", decision="assign_existing",
                                            suggested_case_id=case_id, assigned_case_id=case_id,
                                            confidence=suggestion.confidence,
                                            reason="Automatische Zuordnung nach strengen Konfidenz- und Ähnlichkeitsprüfungen.",
                                            details=json.dumps({"generated_by": "document_worker", "similarity": next((c.similarity for c in candidates if c.case_id == case_id), None)}),
                                        ))
                                        db.commit()
                                        log.info("Automatically assigned document=%s case=%s", document_id, case_id)
                                except Exception:
                                    db.rollback()
                                    log.exception("Automatic assignment skipped: document=%s case=%s", document_id, case_id)
                            log.info("Case suggestion prepared: document=%s decision=%s", document_id, suggestion.decision)
        except Exception:
            log.exception("Non-fatal case suggestion failed: document=%s", document_id)
        log.info("Processed document %s", document_id)
    except Exception as exc:
        error = str(exc)
        log.exception("Processing document %s failed", document_id)
    finally:
        stop.set()
        heartbeat.join(timeout=5)
    with SessionLocal() as db:
        if not finish(db, job_id, error, attempt=attempt):
            log.warning("Stale job completion ignored: job=%s attempt=%s", job_id, attempt)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _request_shutdown)
        signal.signal(signal.SIGINT, _request_shutdown)
    log.info("Document worker started (loop=%s, poll=%ss)", args.loop, args.poll_seconds)
    while not shutdown_requested.is_set():
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
            shutdown_requested.wait(timeout=max(1, args.poll_seconds))


if __name__ == "__main__":
    main()
