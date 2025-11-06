"""Revision: 0003_add_youtube_cache

Adds youtube_videos table for caching downloaded YouTube videos across jobs.
"""
from sqlalchemy import text

revision = "0003_add_youtube_cache"

def upgrade(conn):
    # Create youtube_videos table if not exists
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS youtube_videos (
            video_id TEXT PRIMARY KEY,
            normalized_url TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size_bytes INTEGER,
            title TEXT NOT NULL,
            duration_seconds DOUBLE PRECISION,
            width INTEGER,
            height INTEGER,
            download_count INTEGER DEFAULT 1,
            last_used_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            file_hash TEXT
        );
        """
    ))

    # Create indexes for better query performance
    conn.execute(text(
        """
        CREATE INDEX IF NOT EXISTS ix_youtube_videos_last_used
        ON youtube_videos (last_used_at);
        """
    ))

    conn.execute(text(
        """
        CREATE INDEX IF NOT EXISTS ix_youtube_videos_created
        ON youtube_videos (created_at);
        """
    ))

    print("Created youtube_videos table and indexes")
