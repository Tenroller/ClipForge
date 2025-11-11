"""
Persistent job storage for video processor with automatic recovery.

Supports both PostgreSQL and Redis backends for maximum flexibility.
Jobs are persisted to ensure recovery after crashes or restarts.
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from loguru import logger

# Bind logger with context for this module
logger = logger.bind(name="core.persistence")


class JobStorageBackend(ABC):
    """Abstract base class for job storage backends."""

    @abstractmethod
    async def connect(self):
        """Connect to the storage backend."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the storage backend."""
        pass

    @abstractmethod
    async def save_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Save or update a job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        pass

    @abstractmethod
    async def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status."""
        pass

    @abstractmethod
    async def get_queue_order(self) -> List[str]:
        """Get the current queue order (list of job IDs)."""
        pass

    @abstractmethod
    async def save_queue_order(self, job_ids: List[str]) -> bool:
        """Save the queue order."""
        pass


class PostgreSQLBackend(JobStorageBackend):
    """PostgreSQL-based job storage backend."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._setup_models()

    def _setup_models(self):
        """Setup SQLAlchemy models."""
        from sqlalchemy import create_engine, Column, String, Text, Integer, TIMESTAMP, JSON, Boolean
        from sqlalchemy.orm import sessionmaker, declarative_base
        from sqlalchemy.pool import QueuePool
        from sqlalchemy import func

        Base = declarative_base()

        class ProcessorJob(Base):
            """Job model for video processor persistence."""
            __tablename__ = "processor_jobs"

            job_id = Column(String, primary_key=True)
            workflow = Column(String, nullable=False)
            priority = Column(String, nullable=False)
            status = Column(String, nullable=False)
            request_data = Column(JSON, nullable=False)
            callback_url = Column(Text)
            created_at = Column(TIMESTAMP(timezone=True), nullable=False)
            started_at = Column(TIMESTAMP(timezone=True))
            completed_at = Column(TIMESTAMP(timezone=True))
            duration_seconds = Column(Integer)
            progress = Column(String)
            current_step = Column(String)
            error_message = Column(Text)
            result_data = Column(JSON)
            logs = Column(JSON, default=list)
            cancelled = Column(Boolean, default=False)
            processor_id = Column(String)  # Which processor owns this job
            queue_position = Column(Integer)  # Position in queue

        self.ProcessorJob = ProcessorJob
        self.Base = Base

    async def connect(self):
        """Connect to PostgreSQL."""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy.pool import QueuePool

            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={
                    "options": "-c timezone=utc",
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5
                }
            )

            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            # Create tables if they don't exist
            self.Base.metadata.create_all(bind=self.engine)

            logger.info("Connected to PostgreSQL job storage")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def disconnect(self):
        """Disconnect from PostgreSQL."""
        if self.engine:
            self.engine.dispose()
            logger.info("Disconnected from PostgreSQL job storage")

    async def save_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Save or update a job in PostgreSQL."""
        try:
            session = self.SessionLocal()
            try:
                # Check if job exists
                existing_job = session.query(self.ProcessorJob).filter(
                    self.ProcessorJob.job_id == job_id
                ).first()

                # Parse datetime strings to datetime objects
                created_at = job_data.get('created_at')
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                elif not created_at:
                    created_at = datetime.now(timezone.utc)

                started_at = job_data.get('started_at')
                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))

                completed_at = job_data.get('completed_at')
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))

                if existing_job:
                    # Update existing job
                    existing_job.workflow = job_data.get('workflow', existing_job.workflow)
                    existing_job.priority = job_data.get('priority', existing_job.priority)
                    existing_job.status = job_data.get('status', existing_job.status)
                    existing_job.request_data = job_data.get('request_data', existing_job.request_data)
                    existing_job.callback_url = job_data.get('callback_url', existing_job.callback_url)
                    existing_job.started_at = started_at
                    existing_job.completed_at = completed_at
                    existing_job.duration_seconds = job_data.get('duration_seconds')
                    existing_job.progress = job_data.get('progress')
                    existing_job.current_step = job_data.get('current_step')
                    existing_job.error_message = job_data.get('error_message')
                    existing_job.result_data = job_data.get('result_data')
                    existing_job.logs = job_data.get('logs', existing_job.logs)
                    existing_job.cancelled = job_data.get('cancelled', existing_job.cancelled)
                    existing_job.processor_id = job_data.get('processor_id')
                    existing_job.queue_position = job_data.get('queue_position')
                else:
                    # Create new job
                    new_job = self.ProcessorJob(
                        job_id=job_id,
                        workflow=job_data['workflow'],
                        priority=job_data['priority'],
                        status=job_data['status'],
                        request_data=job_data['request_data'],
                        callback_url=job_data.get('callback_url'),
                        created_at=created_at,
                        started_at=started_at,
                        completed_at=completed_at,
                        duration_seconds=job_data.get('duration_seconds'),
                        progress=job_data.get('progress'),
                        current_step=job_data.get('current_step'),
                        error_message=job_data.get('error_message'),
                        result_data=job_data.get('result_data'),
                        logs=job_data.get('logs', []),
                        cancelled=job_data.get('cancelled', False),
                        processor_id=job_data.get('processor_id'),
                        queue_position=job_data.get('queue_position')
                    )
                    session.add(new_job)

                session.commit()
                return True

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to save job {job_id} to PostgreSQL: {e}")
            return False

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job from PostgreSQL."""
        try:
            session = self.SessionLocal()
            try:
                job = session.query(self.ProcessorJob).filter(
                    self.ProcessorJob.job_id == job_id
                ).first()

                if not job:
                    return None

                return {
                    'job_id': job.job_id,
                    'workflow': job.workflow,
                    'priority': job.priority,
                    'status': job.status,
                    'request_data': job.request_data,
                    'callback_url': job.callback_url,
                    'created_at': job.created_at.isoformat() if job.created_at else None,
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'duration_seconds': job.duration_seconds,
                    'progress': job.progress,
                    'current_step': job.current_step,
                    'error_message': job.error_message,
                    'result_data': job.result_data,
                    'logs': job.logs or [],
                    'cancelled': job.cancelled,
                    'processor_id': job.processor_id,
                    'queue_position': job.queue_position
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get job {job_id} from PostgreSQL: {e}")
            return None

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job from PostgreSQL."""
        try:
            session = self.SessionLocal()
            try:
                result = session.query(self.ProcessorJob).filter(
                    self.ProcessorJob.job_id == job_id
                ).delete()
                session.commit()
                return result > 0

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to delete job {job_id} from PostgreSQL: {e}")
            return False

    async def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs from PostgreSQL."""
        try:
            session = self.SessionLocal()
            try:
                query = session.query(self.ProcessorJob)

                if status:
                    query = query.filter(self.ProcessorJob.status == status)

                # Order by queue position (for queued jobs) and created_at
                query = query.order_by(
                    self.ProcessorJob.queue_position.asc().nullslast(),
                    self.ProcessorJob.created_at.desc()
                )

                jobs = []
                for job in query.all():
                    jobs.append({
                        'job_id': job.job_id,
                        'workflow': job.workflow,
                        'priority': job.priority,
                        'status': job.status,
                        'request_data': job.request_data,
                        'callback_url': job.callback_url,
                        'created_at': job.created_at.isoformat() if job.created_at else None,
                        'started_at': job.started_at.isoformat() if job.started_at else None,
                        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                        'duration_seconds': job.duration_seconds,
                        'progress': job.progress,
                        'current_step': job.current_step,
                        'error_message': job.error_message,
                        'result_data': job.result_data,
                        'logs': job.logs or [],
                        'cancelled': job.cancelled,
                        'processor_id': job.processor_id,
                        'queue_position': job.queue_position
                    })

                return jobs

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to list jobs from PostgreSQL: {e}")
            return []

    async def get_queue_order(self) -> List[str]:
        """Get queue order from PostgreSQL."""
        try:
            session = self.SessionLocal()
            try:
                jobs = session.query(self.ProcessorJob).filter(
                    self.ProcessorJob.status == 'queued',
                    self.ProcessorJob.queue_position.isnot(None)
                ).order_by(self.ProcessorJob.queue_position.asc()).all()

                return [job.job_id for job in jobs]

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get queue order from PostgreSQL: {e}")
            return []

    async def save_queue_order(self, job_ids: List[str]) -> bool:
        """Save queue order to PostgreSQL."""
        try:
            session = self.SessionLocal()
            try:
                for position, job_id in enumerate(job_ids):
                    session.query(self.ProcessorJob).filter(
                        self.ProcessorJob.job_id == job_id
                    ).update({'queue_position': position})

                session.commit()
                return True

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to save queue order to PostgreSQL: {e}")
            return False


class RedisBackend(JobStorageBackend):
    """Redis-based job storage backend."""

    def __init__(self, redis_url: str, redis_db: int = 1):
        self.redis_url = redis_url
        self.redis_db = redis_db
        self.redis = None

    async def connect(self):
        """Connect to Redis."""
        try:
            import redis.asyncio as redis
            self.redis = await redis.from_url(
                self.redis_url,
                db=self.redis_db,
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis job storage")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis job storage")

    async def save_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Save job to Redis."""
        try:
            key = f"processor:job:{job_id}"

            # Convert datetime objects to ISO format strings
            serializable_data = {}
            for k, v in job_data.items():
                if isinstance(v, datetime):
                    serializable_data[k] = v.isoformat()
                else:
                    serializable_data[k] = v

            await self.redis.set(key, json.dumps(serializable_data))

            # Add to status index
            status = job_data.get('status', 'unknown')
            await self.redis.sadd(f"processor:jobs:status:{status}", job_id)

            return True
        except Exception as e:
            logger.error(f"Failed to save job {job_id} to Redis: {e}")
            return False

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job from Redis."""
        try:
            key = f"processor:job:{job_id}"
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get job {job_id} from Redis: {e}")
            return None

    async def delete_job(self, job_id: str) -> bool:
        """Delete job from Redis."""
        try:
            # Get job to find its status for index cleanup
            job_data = await self.get_job(job_id)
            if job_data:
                status = job_data.get('status', 'unknown')
                await self.redis.srem(f"processor:jobs:status:{status}", job_id)

            # Delete job data
            key = f"processor:job:{job_id}"
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete job {job_id} from Redis: {e}")
            return False

    async def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs from Redis."""
        try:
            jobs = []

            if status:
                # Get jobs with specific status
                job_ids = await self.redis.smembers(f"processor:jobs:status:{status}")
            else:
                # Get all job keys
                job_keys = await self.redis.keys("processor:job:*")
                job_ids = [key.split(":")[-1] for key in job_keys]

            for job_id in job_ids:
                job_data = await self.get_job(job_id)
                if job_data:
                    jobs.append(job_data)

            # Sort by created_at
            jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return jobs

        except Exception as e:
            logger.error(f"Failed to list jobs from Redis: {e}")
            return []

    async def get_queue_order(self) -> List[str]:
        """Get queue order from Redis."""
        try:
            return await self.redis.lrange("processor:queue:order", 0, -1)
        except Exception as e:
            logger.error(f"Failed to get queue order from Redis: {e}")
            return []

    async def save_queue_order(self, job_ids: List[str]) -> bool:
        """Save queue order to Redis."""
        try:
            await self.redis.delete("processor:queue:order")
            if job_ids:
                await self.redis.rpush("processor:queue:order", *job_ids)
            return True
        except Exception as e:
            logger.error(f"Failed to save queue order to Redis: {e}")
            return False


class JobPersistenceManager:
    """Manages job persistence with automatic backend selection."""

    def __init__(self, database_url: Optional[str] = None, redis_url: Optional[str] = None, redis_db: int = 1):
        """
        Initialize persistence manager.

        Priority: PostgreSQL > Redis > None (in-memory fallback)
        """
        self.backend: Optional[JobStorageBackend] = None

        # Try PostgreSQL first
        if database_url:
            try:
                self.backend = PostgreSQLBackend(database_url)
                logger.info("Using PostgreSQL for job persistence")
            except Exception as e:
                logger.warning(f"Failed to initialize PostgreSQL backend: {e}")

        # Fall back to Redis
        if not self.backend and redis_url:
            try:
                self.backend = RedisBackend(redis_url, redis_db)
                logger.info("Using Redis for job persistence")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis backend: {e}")

        if not self.backend:
            logger.warning("No persistence backend available - jobs will not survive restarts!")

    async def connect(self) -> bool:
        """Connect to the persistence backend."""
        if self.backend:
            await self.backend.connect()
            return True
        return False

    async def disconnect(self):
        """Disconnect from the persistence backend."""
        if self.backend:
            await self.backend.disconnect()

    async def save_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Save job to persistent storage."""
        if self.backend:
            return await self.backend.save_job(job_id, job_data)
        return False

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job from persistent storage."""
        if self.backend:
            return await self.backend.get_job(job_id)
        return None

    async def delete_job(self, job_id: str) -> bool:
        """Delete job from persistent storage."""
        if self.backend:
            return await self.backend.delete_job(job_id)
        return False

    async def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs from persistent storage."""
        if self.backend:
            return await self.backend.list_jobs(status)
        return []

    async def get_queue_order(self) -> List[str]:
        """Get queue order from persistent storage."""
        if self.backend:
            return await self.backend.get_queue_order()
        return []

    async def save_queue_order(self, job_ids: List[str]) -> bool:
        """Save queue order to persistent storage."""
        if self.backend:
            return await self.backend.save_queue_order(job_ids)
        return False

    def is_available(self) -> bool:
        """Check if persistence is available."""
        return self.backend is not None
