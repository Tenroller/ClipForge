"""
Database models and utilities for job persistence.

Provides SQLite-based job storage with optional PostgreSQL support.
"""

import os
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

# Database configuration
DB_URL = os.getenv("DATABASE_URL", "")
# Resolve to absolute path to avoid cwd-related discrepancies during tests
DB_PATH = Path(os.getenv("DATABASE_PATH", "jobs.db")).resolve()


class JobStore:
    """Thread-safe job storage with SQLite backend."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.lock = threading.Lock()
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        # Ensure parent directory exists
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    step TEXT,
                    workflow TEXT,
                    user_id TEXT,
                    request_data TEXT,
                    result_data TEXT,
                    error_message TEXT,
                    logs TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)
            """)
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Best-effort add user_id to jobs if missing (older DBs)
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN user_id TEXT")
            except Exception:
                pass
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def create_job(self, job_id: str, workflow: str, request_data: Dict[str, Any], user_id: Optional[str] = None) -> None:
        """Create a new job record."""
        with self.lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO jobs (id, status, step, workflow, user_id, request_data, logs)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    "running",
                    "init",
                    workflow,
                    user_id,
                    json.dumps(request_data),
                    json.dumps([])
                ))
                conn.commit()
    
    def update_job(self, job_id: str, **fields: Any) -> None:
        """Update job fields."""
        if not fields:
            return
            
        with self.lock:
            with self._get_connection() as conn:
                # Build dynamic update query
                set_clauses = []
                values = []
                
                for field, value in fields.items():
                    if field == "logs" and isinstance(value, list):
                        value = json.dumps(value)
                    elif field == "result" and isinstance(value, dict):
                        set_clauses.append("result_data = ?")
                        values.append(json.dumps(value))
                        continue
                    elif field == "error":
                        set_clauses.append("error_message = ?")
                        values.append(str(value) if value else None)
                        continue
                    
                    # Map field names to column names
                    column_map = {
                        "status": "status",
                        "step": "step",
                        "logs": "logs"
                    }
                    
                    if field in column_map:
                        set_clauses.append(f"{column_map[field]} = ?")
                        values.append(value)
                
                if set_clauses:
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(job_id)
                    
                    query = f"UPDATE jobs SET {', '.join(set_clauses)} WHERE id = ?"
                    conn.execute(query, values)
                    conn.commit()
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            
            if not row:
                return None
            
            # Convert row to dict and parse JSON fields
            job = dict(row)
            
            try:
                job["logs"] = json.loads(job["logs"]) if job["logs"] else []
            except (json.JSONDecodeError, TypeError):
                job["logs"] = []
            
            try:
                job["result"] = json.loads(job["result_data"]) if job["result_data"] else None
            except (json.JSONDecodeError, TypeError):
                job["result"] = None
            
            try:
                job["request_data"] = json.loads(job["request_data"]) if job["request_data"] else {}
            except (json.JSONDecodeError, TypeError):
                job["request_data"] = {}
            
            # Rename fields to match API format
            job["error"] = job["error_message"]
            
            # Clean up internal fields
            for field in ["result_data", "error_message", "request_data"]:
                job.pop(field, None)
            
            return job
    
    def list_jobs(self, limit: int = 100, status: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs with optional filtering."""
        with self._get_connection() as conn:
            params: list[Any] = []
            where = []
            if status:
                where.append("status = ?")
                params.append(status)
            if user_id:
                where.append("user_id = ?")
                params.append(user_id)
            where_clause = (" WHERE " + " AND ".join(where)) if where else ""
            query = f"SELECT * FROM jobs{where_clause} ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, tuple(params)).fetchall()
            
            jobs = []
            for row in rows:
                job = dict(row)
                try:
                    job["logs"] = json.loads(job["logs"]) if job["logs"] else []
                except (json.JSONDecodeError, TypeError):
                    job["logs"] = []
                
                try:
                    job["result"] = json.loads(job["result_data"]) if job["result_data"] else None
                except (json.JSONDecodeError, TypeError):
                    job["result"] = None
                
                job["error"] = job["error_message"]
                
                # Clean up internal fields
                for field in ["result_data", "error_message", "request_data"]:
                    job.pop(field, None)
                
                jobs.append(job)
            
            return jobs

    # User management
    def create_user(self, user_id: str, email: str, password_hash: str, password_salt: str) -> None:
        with self.lock:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, password_salt) VALUES (?, ?, ?, ?)",
                    (user_id, email, password_hash, password_salt)
                )
                conn.commit()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None
    
    def delete_old_jobs(self, days: int = 30) -> int:
        """Delete jobs older than specified days."""
        with self.lock:
            with self._get_connection() as conn:
                result = conn.execute("""
                    DELETE FROM jobs 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))
                conn.commit()
                return result.rowcount
    
    def get_stats(self) -> Dict[str, Any]:
        """Get job statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            
            by_status = {}
            for row in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"):
                by_status[row[0]] = row[1]
            
            recent = conn.execute("""
                SELECT COUNT(*) FROM jobs 
                WHERE created_at > datetime('now', '-24 hours')
            """).fetchone()[0]
            
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
