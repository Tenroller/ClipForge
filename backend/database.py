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

from sqlalchemy import create_engine, Column, String, Text, Integer, TIMESTAMP, JSON, Index, func, Boolean, Float, text, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

# Import configuration
from .core.config import AppConfig

# Database configuration (PostgreSQL only)
config = AppConfig.from_env()
DB_URL = config.database_url

# SQLAlchemy setup for PostgreSQL
Base = declarative_base()
engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=config.videohelper_db_pool_size,
    pool_timeout=config.videohelper_db_pool_timeout,
    max_overflow=20,
    pool_pre_ping=True,
    # PostgreSQL-specific optimizations
    connect_args={
        "options": "-c timezone=utc",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# SQLAlchemy Model optimized for PostgreSQL
class Job(Base):
    """Job model for PostgreSQL."""
    __tablename__ = "jobs"

    # Primary key - using String for job IDs but with PostgreSQL optimizations
    id = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    step = Column(String)
    workflow = Column(String)
    user_id = Column(String)
    request_data = Column(JSON)
    result = Column(JSON)  # Changed from result_data to match database schema
    error_message = Column(Text)
    logs = Column(JSON, default=list)
    resume_data = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(TIMESTAMP(timezone=True))
    duration_seconds = Column(Integer)
    ended_at = Column(TIMESTAMP(timezone=True))  # Explicit ended_at separate from updated_at
    # Resume metadata
    resumed_from = Column(String)  # Original job ID if this job is a resume of another
    resume_attempt = Column(Integer)  # Attempt count (1 = original, 2 = first resume, etc.)
    resumed_to = Column(JSON, default=list)  # List of child job IDs resumed from this one

    # PostgreSQL-specific indexes for better query performance
    __table_args__ = (
        Index('ix_jobs_status_created', 'status', 'created_at'),
        Index('ix_jobs_workflow_status', 'workflow', 'status'),
        Index('ix_jobs_user_id_created', 'user_id', 'created_at'),
        Index('ix_jobs_created_at', 'created_at'),
    )


class Video(Base):
    """Video model for tracking generated videos."""
    __tablename__ = "videos"

    # Primary key - unique video ID
    id = Column(String, primary_key=True)
    
    # Video metadata
    filename = Column(String, nullable=False)
    file_path = Column(Text, nullable=False)  # Full path to video file
    size_bytes = Column(Integer)
    duration_seconds = Column(Float)
    
    # Video categorization
    workflow = Column(String, nullable=False)  # moneyprinter, brainrot, etc.
    video_type = Column(String)  # ai_generated, compilation, etc.
    
    # Brainrot-specific fields
    compilation_type = Column(String)  # normal, tts, etc.
    compilation_num = Column(Integer)
    
    # Job association
    job_id = Column(String, nullable=False)
    
    # Status tracking
    posted = Column(Boolean, default=False, nullable=False)
    posted_at = Column(TIMESTAMP(timezone=True))
    
    # Additional metadata
    video_metadata = Column(JSON)  # For storing additional video-specific data
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # PostgreSQL-specific indexes for better query performance
    __table_args__ = (
        Index('ix_videos_job_id', 'job_id'),
        Index('ix_videos_workflow', 'workflow'),
        Index('ix_videos_posted', 'posted'),
        Index('ix_videos_created_at', 'created_at'),
        Index('ix_videos_workflow_posted', 'workflow', 'posted'),
    )


class JobTombstone(Base):
    """Tracks purged/expired jobs so we can return 410 (Gone)."""
    __tablename__ = "job_tombstones"

    id = Column(String, primary_key=True)
    reason = Column(Text)
    deleted_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    # Index for faster lookups
    __table_args__ = (
        Index('ix_job_tombstones_deleted_at', 'deleted_at'),
    )


class JobStore:
    """PostgreSQL-based job storage using SQLAlchemy."""

    def __init__(self):
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        try:
            # Run lightweight migrations to add any required schema changes
            try:
                from .migrations import run_migrations
                run_migrations(engine)
            except Exception:
                # If migrations fail, raise so the startup/test process is aware
                raise

            # Create any missing tables from models
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
                # Start as queued to reflect actual lifecycle; the in-memory queue will
                # transition to running when execution begins.
                status="queued",
                step="init",
                workflow=workflow,
                user_id=user_id,
                request_data=request_data,
                logs=[],
                resume_attempt=1,
                resumed_to=[]
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
                    setattr(job, 'result', value)  # Changed from result_data to result
                elif field == "error":
                    setattr(job, 'error_message', str(value) if value else None)
                elif field == "resume_data" and isinstance(value, dict):
                    setattr(job, 'resume_data', value)
                elif field == "resumed_from":
                    setattr(job, 'resumed_from', value)
                elif field == "resume_attempt":
                    setattr(job, 'resume_attempt', value)
                elif field == "resumed_to" and isinstance(value, list):
                    setattr(job, 'resumed_to', value)
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
            raw_status = str(job.status)
            # Map internal statuses to frontend-compatible statuses
            status_map = {
                "completed": "done",
                "failed": "error"
            }
            job_dict = {
                "id": job.id,
                "status": status_map.get(raw_status, raw_status),
                "step": job.step,
                "workflow": job.workflow,
                "user_id": job.user_id,
                "logs": job.logs if job.logs is not None else [],
                "result": job.result,  # Changed from job.result_data to job.result
                "request_data": job.request_data if job.request_data is not None else {},
                "resume_data": job.resume_data,
                "resumed_from": job.resumed_from,
                "resumed_to": job.resumed_to if getattr(job, 'resumed_to', None) is not None else [],
                "resume_attempt": job.resume_attempt,
                "error": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at is not None else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at is not None else None,
                "started_at": job.started_at.isoformat() if job.started_at is not None else None,
                "duration_seconds": job.duration_seconds,
                "ended_at": job.ended_at.isoformat() if job.ended_at is not None else None
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
            status_map = {
                "completed": "done",
                "failed": "error"
            }
            for job in jobs:
                job_list.append({
                    "id": job.id,
                    "status": status_map.get(str(job.status), str(job.status)),
                    "step": job.step,
                    "workflow": job.workflow,
                    "user_id": job.user_id,
                    "logs": job.logs if job.logs is not None else [],
                    "result": job.result,  # Changed from job.result_data to job.result
                    "request_data": job.request_data if job.request_data is not None else {},
                    "resume_data": job.resume_data,
                    "resumed_from": job.resumed_from,
                    "resumed_to": job.resumed_to if getattr(job, 'resumed_to', None) is not None else [],
                    "resume_attempt": job.resume_attempt,
                    "error": job.error_message,
                    "created_at": job.created_at.isoformat() if job.created_at is not None else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at is not None else None,
                    "started_at": job.started_at.isoformat() if job.started_at is not None else None,
                    "duration_seconds": job.duration_seconds,
                    "ended_at": job.ended_at.isoformat() if job.ended_at is not None else None
                })

            return job_list

    def delete_old_jobs(self, days: int = 30) -> int:
        """Delete jobs older than specified days."""
        from datetime import datetime, timedelta, timezone

        with self._get_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            result = session.query(Job).filter(Job.created_at < cutoff_date).delete()
            session.commit()
            return result

    def delete_job(self, job_id: str) -> bool:
        """Delete a single job by ID."""
        with self._get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return False
            
            session.delete(job)
            session.commit()
            return True

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

    def expire_stale_jobs(self, running_timeout_hours: int = 4, queued_timeout_hours: int = 12) -> Dict[str, Any]:
        """Mark stale running/queued jobs as cancelled with explanatory error.

        Returns counts of updated jobs.
        """
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        running_cutoff = now - timedelta(hours=running_timeout_hours)
        queued_cutoff = now - timedelta(hours=queued_timeout_hours)

        with self._get_session() as session:
            # Collect IDs first (so we can optionally purge later outside this method)
            running_ids = [r.id for r in session.query(Job.id).filter(
                Job.status == 'running',
                Job.started_at != None,  # noqa: E711
                Job.started_at < running_cutoff
            ).all()]

            queued_ids = [q.id for q in session.query(Job.id).filter(
                Job.status == 'queued',
                Job.created_at < queued_cutoff
            ).all()]

            updated_running = 0
            updated_queued = 0

            if running_ids:
                updated_running = session.query(Job).filter(Job.id.in_(running_ids)).update({
                    Job.status: 'cancelled',
                    Job.error_message: f"Auto-cancelled: exceeded max runtime ({running_timeout_hours}h limit)"
                }, synchronize_session=False)

            if queued_ids:
                updated_queued = session.query(Job).filter(Job.id.in_(queued_ids)).update({
                    Job.status: 'cancelled',
                    Job.error_message: f"Auto-cancelled: queued longer than {queued_timeout_hours}h"
                }, synchronize_session=False)

            if updated_running or updated_queued:
                session.commit()

            return {
                "running_expired": updated_running,
                "queued_expired": updated_queued,
                "running_ids": running_ids,
                "queued_ids": queued_ids
            }

    # Tombstone / purge utilities
    def purge_job(self, job_id: str, reason: str = "Purged by user") -> bool:
        """Soft-delete job and record tombstone so future GET returns 410."""
        with self._get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            existing_tombstone = session.query(JobTombstone).filter(JobTombstone.id == job_id).first()
            if not job and existing_tombstone:
                return True  # Already purged
            if job:
                session.delete(job)
            if not existing_tombstone:
                tomb = JobTombstone(id=job_id, reason=reason)
                session.add(tomb)
            session.commit()
            return True

    def is_purged(self, job_id: str) -> Optional[str]:
        with self._get_session() as session:
            tomb = session.query(JobTombstone).filter(JobTombstone.id == job_id).first()
            if tomb:
                # Cast to str in case Column element is returned differently in typing
                reason_val = getattr(tomb, 'reason', None)
                if reason_val:
                    return str(reason_val)
                return "Purged"
            return None

    # Video management methods
    def create_video(self, video_id: str, filename: str, file_path: str, job_id: str, 
                     workflow: str, video_type: Optional[str] = None, size_bytes: Optional[int] = None, 
                     duration_seconds: Optional[float] = None, compilation_type: Optional[str] = None, 
                     compilation_num: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Create a new video record."""
        with self._get_session() as session:
            video = Video(
                id=video_id,
                filename=filename,
                file_path=file_path,
                job_id=job_id,
                workflow=workflow,
                video_type=video_type,
                size_bytes=size_bytes,
                duration_seconds=duration_seconds,
                compilation_type=compilation_type,
                compilation_num=compilation_num,
                video_metadata=metadata or {},
                posted=False
            )
            session.add(video)
            session.commit()

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video by ID."""
        with self._get_session() as session:
            video = session.query(Video).filter(Video.id == video_id).first()
            
            if not video:
                return None
            
            return {
                "id": video.id,
                "filename": video.filename,
                "file_path": video.file_path,
                "job_id": video.job_id,
                "workflow": video.workflow,
                "video_type": video.video_type,
                "size_bytes": video.size_bytes,
                "duration_seconds": video.duration_seconds,
                "compilation_type": video.compilation_type,
                "compilation_num": video.compilation_num,
                "posted": video.posted,
                "posted_at": video.posted_at.isoformat() if getattr(video, 'posted_at', None) is not None else None,
                "metadata": video.video_metadata or {},
                "created_at": video.created_at.isoformat() if getattr(video, 'created_at', None) is not None else None,
                "updated_at": video.updated_at.isoformat() if getattr(video, 'updated_at', None) is not None else None
            }

    def update_video(self, video_id: str, **fields: Any) -> bool:
        """Update video fields."""
        if not fields:
            return False

        with self._get_session() as session:
            video = session.query(Video).filter(Video.id == video_id).first()
            if not video:
                return False

            for field, value in fields.items():
                if field == "posted" and value and getattr(video, 'posted_at', None) is None:
                    # Set posted_at timestamp when marking as posted
                    setattr(video, 'posted_at', func.now())
                elif field == "metadata":
                    # Map metadata to video_metadata column
                    setattr(video, 'video_metadata', value)
                elif hasattr(video, field):
                    setattr(video, field, value)

            session.commit()
            return True

    def list_videos(self, limit: int = 100, offset: int = 0, workflow: Optional[str] = None, 
                    posted: Optional[bool] = None, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List videos with optional filtering."""
        with self._get_session() as session:
            query = session.query(Video)

            if workflow:
                query = query.filter(Video.workflow == workflow)
            if posted is not None:
                query = query.filter(Video.posted == posted)
            if job_id:
                query = query.filter(Video.job_id == job_id)

            videos = query.order_by(Video.created_at.desc()).offset(offset).limit(limit).all()

            video_list = []
            for video in videos:
                video_list.append({
                    "id": video.id,
                    "filename": video.filename,
                    "file_path": video.file_path,
                    "job_id": video.job_id,
                    "workflow": video.workflow,
                    "video_type": video.video_type,
                    "size_bytes": video.size_bytes,
                    "duration_seconds": video.duration_seconds,
                    "compilation_type": video.compilation_type,
                    "compilation_num": video.compilation_num,
                    "posted": video.posted,
                    "posted_at": video.posted_at.isoformat() if getattr(video, 'posted_at', None) is not None else None,
                    "metadata": video.video_metadata or {},
                    "created_at": video.created_at.isoformat() if getattr(video, 'created_at', None) is not None else None,
                    "updated_at": video.updated_at.isoformat() if getattr(video, 'updated_at', None) is not None else None
                })

            return video_list

    def delete_video(self, video_id: str) -> bool:
        """Delete a video record by ID."""
        with self._get_session() as session:
            video = session.query(Video).filter(Video.id == video_id).first()
            if not video:
                return False
            
            session.delete(video)
            session.commit()
            return True

    def get_random_video(self, workflow: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a random video from the database."""
        from sqlalchemy import func
        
        with self._get_session() as session:
            query = session.query(Video)

            if workflow:
                query = query.filter(Video.workflow == workflow)

            # Use ORDER BY RANDOM() for PostgreSQL to get a random video
            video = query.order_by(func.random()).first()

            if not video:
                return None

            return {
                "id": video.id,
                "filename": video.filename,
                "file_path": video.file_path,
                "job_id": video.job_id,
                "workflow": video.workflow,
                "video_type": video.video_type,
                "size_bytes": video.size_bytes,
                "duration_seconds": video.duration_seconds,
                "compilation_type": video.compilation_type,
                "compilation_num": video.compilation_num,
                "posted": video.posted,
                "posted_at": video.posted_at.isoformat() if getattr(video, 'posted_at', None) is not None else None,
                "metadata": video.video_metadata or {},
                "created_at": video.created_at.isoformat() if getattr(video, 'created_at', None) is not None else None,
                "updated_at": video.updated_at.isoformat() if getattr(video, 'updated_at', None) is not None else None
            }

    def get_video_stats(self) -> Dict[str, Any]:
        """Get video statistics."""
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func

        with self._get_session() as session:
            # Total videos
            total = session.query(func.count(Video.id)).scalar() or 0

            # Videos by workflow: count and summed size in bytes
            workflow_rows = session.query(
                Video.workflow,
                func.count(Video.id),
                func.sum(Video.size_bytes)
            ).group_by(Video.workflow).all()

            workflows: Dict[str, Dict[str, Any]] = {}
            for workflow, count, sum_bytes in workflow_rows:
                workflows[workflow] = {
                    "count": int(count or 0),
                    "size_mb": round((sum_bytes or 0) / (1024 * 1024), 2)
                }

            # Ensure common workflow keys exist to avoid undefined access in frontend
            for k in ("moneyprinter", "brainrot"):
                workflows.setdefault(k, {"count": 0, "size_mb": 0})

            # Videos by type (ai_generated, compilation)
            type_rows = session.query(
                Video.video_type,
                func.count(Video.id),
                func.sum(Video.size_bytes)
            ).group_by(Video.video_type).all()

            video_types: Dict[str, Dict[str, Any]] = {}
            for vtype, count, sum_bytes in type_rows:
                key = vtype or "unknown"
                video_types[key] = {
                    "count": int(count or 0),
                    "size_mb": round((sum_bytes or 0) / (1024 * 1024), 2)
                }

            # Ensure common video type keys
            for k in ("ai_generated", "compilation"):
                video_types.setdefault(k, {"count": 0, "size_mb": 0})

            # Videos by posted status
            posted_count = session.query(func.count(Video.id)).filter(Video.posted == True).scalar() or 0
            unposted_count = session.query(func.count(Video.id)).filter(Video.posted == False).scalar() or 0

            # Recent videos (last 24 hours)
            cutoff_date = datetime.now(timezone.utc) - timedelta(hours=24)
            recent = session.query(func.count(Video.id)).filter(Video.created_at > cutoff_date).scalar() or 0

            # Total size
            total_size = session.query(func.sum(Video.size_bytes)).scalar() or 0

            return {
                "total_videos": int(total),
                "total_size_mb": round(total_size / (1024 * 1024), 2) if total_size else 0,
                "workflows": workflows,
                "video_types": video_types,
                "posted_count": int(posted_count),
                "unposted_count": int(unposted_count),
                "recent_24h": int(recent),
                "total_size_bytes": int(total_size)
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
    """Migrate existing JSON job data to PostgreSQL database."""
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
            workflow = job_data.get("workflow", "unknown")  # Use actual workflow if available
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
            if "user_id" in job_data:
                update_fields["user_id"] = job_data["user_id"]
            if "resume_data" in job_data:
                update_fields["resume_data"] = job_data["resume_data"]

            if update_fields:
                job_store.update_job(job_id, **update_fields)

            migrated += 1

        return migrated

    except Exception as e:
        print(f"Migration failed: {e}")
        return 0
