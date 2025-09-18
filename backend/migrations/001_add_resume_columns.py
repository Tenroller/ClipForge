"""Lightweight migration to add resume-related columns to jobs table if missing.
Not using Alembic yet; safe to run multiple times.
"""
from sqlalchemy import inspect, text
from backend.database import engine

def run():
    with engine.connect() as conn:
        inspector = inspect(conn)
        cols = {c['name'] for c in inspector.get_columns('jobs')}
        statements = []
        if 'resumed_from' not in cols:
            statements.append("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS resumed_from VARCHAR")
        if 'resume_attempt' not in cols:
            statements.append("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS resume_attempt INTEGER")
        if 'resumed_to' not in cols:
            statements.append("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS resumed_to JSONB")
        if statements:
            for stmt in statements:
                conn.execute(text(stmt))
            conn.commit()
            print(f"Applied resume columns migration: {len(statements)} changes")
        else:
            print("Resume columns already present; no changes applied")

if __name__ == "__main__":
    run()
