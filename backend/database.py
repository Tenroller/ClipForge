"""
Database models and utilities for job persistence.

Provides PostgreSQL-based job storage with SQLAlchemy ORM.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, String, Text, Integer, TIMESTAMP, JSON, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

# Import configuration
from config import get_config

# Database configuration
config = get_config()
DB_URL = config.get('database_url', 'postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper')

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=config.get_int('videohelper_db_pool_size', 5),
    pool_timeout=config.get_int('videohelper_db_pool_timeout', 30),
    pool_pre_ping=True,
    echo=config.get_bool('debug_mode', False)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# SQLAlchemy Model
class Job(Base):
    """Job model for SQLAlchemy."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False, index=True)
    step = Column(String)
    workflow = Column(String, index=True)
    user_id = Column(String, index=True)
    request_data = Column(JSONB)
    result_data = Column(JSONB)
    error_message = Column(Text)
    logs = Column(JSONB, default=list)
    resume_data = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(TIMESTAMP(timezone=True))
    duration_seconds = Column(Integer)


class JobStore:
    """PostgreSQL-based job storage using SQLAlchemy."""

    def __init__(self):
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        try:
            Base.metadata.create_all(bind=engine)
        except SQLAlchemyError as e:
            print(f"Error initializing database: {e}")
            raise

    @contextmanager
    def _get_session(self):
        """Get a database session with proper cleanup."""
        session = SessionLocal()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def cleanup_connections(self):
        """Clean up database connections."""
        # SQLAlchemy handles connection pooling automatically
        pass

    def create_job(self, job_id: str, workflow: str, request_data: Dict[str, Any], user_id: Optional[str] = None) -> None:
        """Create a new job record."""
        with self._get_session() as session:
            job = Job(
                id=job_id,
                status="running",
                step="init",
                workflow=workflow,
                user_id=user_id,
                request_data=request_data,
                logs=[]
            )
            session.add(job)
            session.commit()

    def update_job(self, job_id: str, **fields: Any) -> None:
        """Update job fields."""
        if not fields:
            return

        with self._get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return

            for field, value in fields.items():
                if field == "logs" and isinstance(value, list):
                    setattr(job, 'logs', value)
                elif field == "result" and isinstance(value, dict):
                    setattr(job, 'result_data', value)
                elif field == "error":
                    setattr(job, 'error_message', str(value) if value else None)
                elif field == "resume_data" and isinstance(value, dict):
                    setattr(job, 'resume_data', value)
                elif hasattr(job, field):
                    setattr(job, field, value)

            session.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        with self._get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()

            if not job:
                return None

            # Convert to dictionary and format fields
            job_dict = {
                "id": job.id,
                "status": job.status,
                "step": job.step,
                "workflow": job.workflow,
                "user_id": job.user_id,
                "logs": job.logs if job.logs is not None else [],
                "result": job.result_data,
                "request_data": job.request_data if job.request_data is not None else {},
                "resume_data": job.resume_data,
                "error": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at is not None else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at is not None else None,
                "started_at": job.started_at.isoformat() if job.started_at is not None else None,
                "duration_seconds": job.duration_seconds
            }

            return job_dict

    def list_jobs(self, limit: int = 100, status: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs with optional filtering."""
        with self._get_session() as session:
            query = session.query(Job)

            if status:
                query = query.filter(Job.status == status)
            if user_id:
                query = query.filter(Job.user_id == user_id)

            jobs = query.order_by(Job.created_at.desc()).limit(limit).all()

            job_list = []
            for job in jobs:
                job_dict = {
                    "id": job.id,
                    "status": job.status,
                    "step": job.step,
                    "workflow": job.workflow,
                    "user_id": job.user_id,
                    "logs": job.logs if job.logs is not None else [],
                    "result": job.result_data,
                    "request_data": job.request_data if job.request_data is not None else {},
                    "resume_data": job.resume_data,
                    "error": job.error_message,
                    "created_at": job.created_at.isoformat() if job.created_at is not None else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at is not None else None,
                    "started_at": job.started_at.isoformat() if job.started_at is not None else None,
                    "duration_seconds": job.duration_seconds
                }
                job_list.append(job_dict)

            return job_list

    def delete_old_jobs(self, days: int = 30) -> int:
        """Delete jobs older than specified days."""
        from datetime import datetime, timedelta, timezone

        with self._get_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            result = session.query(Job).filter(Job.created_at < cutoff_date).delete()
            session.commit()
            return result

    def get_stats(self) -> Dict[str, Any]:
        """Get job statistics."""
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func

        with self._get_session() as session:
            # Total jobs
            total = session.query(func.count(Job.id)).scalar()

            # Jobs by status
            status_counts = session.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
            by_status = {status: count for status, count in status_counts}

            # Recent jobs (last 24 hours)
            cutoff_date = datetime.now(timezone.utc) - timedelta(hours=24)
            recent = session.query(func.count(Job.id)).filter(Job.created_at > cutoff_date).scalar()

            return {
                "total_jobs": total,
                "by_status": by_status,
                "recent_24h": recent
            }


# Global job store instance
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """Get or create the global job store instance."""
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store


def cleanup_job_store():
    """Clean up the global job store connections."""
    global _job_store
    if _job_store is not None:
        _job_store.cleanup_connections()
        _job_store = None


def migrate_from_json(json_file: Path, job_store: Optional[JobStore] = None) -> int:
    """Migrate existing JSON job data to database."""
    if job_store is None:
        job_store = get_job_store()

    if not json_file.exists():
        return 0

    try:
        data = json.loads(json_file.read_text("utf-8"))
        if not isinstance(data, dict):
            return 0

        migrated = 0
        for job_id, job_data in data.items():
            if not isinstance(job_data, dict):
                continue

            # Check if job already exists
            if job_store.get_job(job_id):
                continue

            # Create job with available data
            workflow = "unknown"  # Can't determine from JSON
            request_data = job_data.get("request_data", {})

            job_store.create_job(job_id, workflow, request_data)

            # Update with other fields
            update_fields = {}
            if "status" in job_data:
                update_fields["status"] = job_data["status"]
            if "step" in job_data:
                update_fields["step"] = job_data["step"]
            if "result" in job_data:
                update_fields["result"] = job_data["result"]
            if "error" in job_data:
                update_fields["error"] = job_data["error"]
            if "logs" in job_data:
                update_fields["logs"] = job_data["logs"]

            if update_fields:
                job_store.update_job(job_id, **update_fields)

            migrated += 1

        return migrated

    except Exception:
        return 0
