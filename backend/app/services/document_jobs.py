"""PostgreSQL-backed document processing queue. Run the worker outside Vercel."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app import models

MAX_ATTEMPTS = 3
LEASE_MINUTES = 30

def now():
    return datetime.now(timezone.utc)

def enqueue(db: Session, document_id: int, *, retry: bool = False) -> bool:
    job = db.query(models.DocumentProcessingJob).filter_by(document_id=document_id).with_for_update().first()
    if job:
        if job.status in {"Pending", "Running", "Ready"} and not retry:
            return False
        if job.status == "Running" and job.lease_until and job.lease_until > now():
            return False
        job.status = "Pending"
        job.attempts = 0
        job.available_at = now()
        job.lease_until = None
        job.last_error = None
        job.updated_at = now()
    else:
        db.add(models.DocumentProcessingJob(document_id=document_id, status="Pending", available_at=now(), updated_at=now()))
    db.flush()
    return True

def claim(db: Session):
    current = now()
    job = (db.query(models.DocumentProcessingJob)
        .filter(models.DocumentProcessingJob.attempts < MAX_ATTEMPTS)
        .filter(or_(
            (models.DocumentProcessingJob.status == "Pending") & (models.DocumentProcessingJob.available_at <= current),
            (models.DocumentProcessingJob.status == "Running") & (models.DocumentProcessingJob.lease_until < current),
        ))
        .order_by(models.DocumentProcessingJob.available_at, models.DocumentProcessingJob.id)
        .with_for_update(skip_locked=True).first())
    if job is None:
        db.commit()
        return None
    job.status = "Running"
    job.attempts += 1
    job.lease_until = current + timedelta(minutes=LEASE_MINUTES)
    job.updated_at = current
    document_id, job_id = job.document_id, job.id
    db.commit()
    return job_id, document_id

def finish(db: Session, job_id: int, error: str | None):
    job = db.get(models.DocumentProcessingJob, job_id)
    if job is None:
        return
    job.lease_until = None
    job.updated_at = now()
    if error:
        job.last_error = error[:4000]
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "Failed"
        else:
            job.status = "Pending"
            job.available_at = now() + timedelta(minutes=min(30, 2 ** job.attempts))
    else:
        job.status = "Ready"
        job.last_error = None
    db.commit()
