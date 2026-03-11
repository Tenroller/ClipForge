"""Revision: 0005_add_users_table

Creates the users table for multi-user authentication.
"""
from sqlalchemy import text

revision = "0005_add_users_table"


def upgrade(conn):
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'user',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
        CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);
        CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active);
        """
    ))
    print("Created users table with indexes")


def downgrade(conn):
    conn.execute(text(
        """
        DROP TABLE IF EXISTS users;
        """
    ))
    print("Dropped users table")
