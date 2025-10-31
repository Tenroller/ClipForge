"""Revision: 0002_add_result_column

Adds the missing result column to the jobs table.
"""
from sqlalchemy import text

revision = "0002_add_result_column"

def upgrade(conn):
    """Add the result column to jobs table if it doesn't exist."""
    # First check if the jobs table exists
    table_check = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'jobs'
    """))

    if not table_check.fetchone():
        print("'jobs' table does not exist yet, skipping result column migration")
        return

    # Check if the result column exists
    result = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'jobs' AND column_name = 'result'
    """))

    if not result.fetchone():
        print("Adding missing 'result' column to jobs table...")
        conn.execute(text("ALTER TABLE jobs ADD COLUMN result JSONB;"))
        print("Successfully added 'result' column to jobs table")
    else:
        print("'result' column already exists in jobs table")
