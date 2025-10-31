"""Revision: 0001_add_resume_and_tombstone

Adds job resume columns and job_tombstones table.
"""
from sqlalchemy import text

revision = "0001_add_resume_and_tombstone"

def upgrade(conn):
    # Create tombstone table if not exists
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS job_tombstones (
            id TEXT PRIMARY KEY,
            reason TEXT,
            deleted_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        );
        """
    ))

    # Check if jobs table exists before trying to alter it
    table_check = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'jobs'
    """))

    if not table_check.fetchone():
        print("'jobs' table does not exist yet, skipping resume columns migration")
        return

    # Add resume-related columns to jobs table if missing
    # Use IF NOT EXISTS where supported
    conn.execute(text("ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS resumed_from TEXT;"))
    conn.execute(text("ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS resume_attempt INTEGER;"))
    conn.execute(text("ALTER TABLE IF EXISTS jobs ADD COLUMN IF NOT EXISTS resumed_to JSON;"))
