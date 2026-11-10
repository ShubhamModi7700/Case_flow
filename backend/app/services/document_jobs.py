from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app import models

MAX_ATTEMPTS = 3
LEASE_MINUTES = 30


def now():
    return datetime.now(timezone.utc)


def enqueue(db: Session, document_id: int, *, retry: bool = False) -> bool:
    current = now()
    job = (db.query(models.DocumentProcessingJob)
           .filter_by(document_id=document_id).with_for_update().first())
    if job:
        if job.status == "Running" and job.lease_until and job.lease_until > current:
            return False
        if not retry and job.status in {"Pending", "Running", "Ready"}:
            return False
        job.status = "Pending"
        job.attempts = 0
        job.available_at = current
        job.lease_until = None
        job.last_error = None
        job.updated_at = current
    else:
        db.add(models.DocumentProcessingJob(
            document_id=document_id, status="Pending",
            available_at=current, updated_at=current,
        ))
    db.flush()
    return True


def claim(db: Session):
    current = now()
    job = (db.query(models.DocumentProcessingJob)
           .filter(models.DocumentProcessingJob.attempts < MAX_ATTEMPTS)
           .filter(or_(
               and_(models.DocumentProcessingJob.status == "Pending",
                    models.DocumentProcessingJob.available_at <= current),
               and_(models.DocumentProcessingJob.status == "Running",
                    models.DocumentProcessingJob.lease_until.isnot(None),
                    models.DocumentProcessingJob.lease_until <= current),
           ))
           .order_by(models.DocumentProcessingJob.available_at,
                     models.DocumentProcessingJob.id)
           .with_for_update(skip_locked=True).first())
    if job is None:
        db.commit()
        return None
    job.status = "Running"
    job.attempts += 1
    job.lease_until = current + timedelta(minutes=LEASE_MINUTES)
    job.updated_at = current
    result = (job.id, job.document_id, job.attempts)
    db.commit()
    return result


def finish(db: Session, job_id: int, error: str | None, *, attempt: int) -> bool:
    """Finalize only the matching claim. Return False for stale workers."""
    job = (db.query(models.DocumentProcessingJob)
           .filter_by(id=job_id).with_for_update().first())
    if job is None or job.status != "Running" or job.attempts != attempt:
        db.rollback()
        return False
    current = now()
    job.lease_until = None
    job.updated_at = current
    if error:
        job.last_error = error[:4000]
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "Failed"
        else:
            job.status = "Pending"
            job.available_at = current + timedelta(minutes=min(30, 2 ** job.attempts))
    else:
        job.status = "Ready"
        job.last_error = None
    db.commit()
    return True
