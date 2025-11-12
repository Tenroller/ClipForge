"""Lightweight migration to remove logs column from jobs table.
Not using Alembic yet; safe to run multiple times.
"""
import os
from sqlalchemy import create_engine, inspect, text

def run():
    # Get database URL directly from environment to avoid circular imports
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return

    # Create engine directly
    engine = create_engine(db_url)

    with engine.connect() as conn:
        inspector = inspect(conn)
        cols = {c['name'] for c in inspector.get_columns('jobs')}
        statements = []
        if 'logs' in cols:
            statements.append("ALTER TABLE jobs DROP COLUMN IF EXISTS logs")
        if statements:
            for stmt in statements:
                conn.execute(text(stmt))
            conn.commit()
            print(f"Applied remove logs column migration: {len(statements)} changes")
        else:
            print("Logs column already removed; no changes applied")

if __name__ == "__main__":
    run()
