"""Revision: 0004_fix_file_size_column

Fixes file_size_bytes column in youtube_videos table to support large files (>2GB).
Changes INTEGER to BIGINT to support files up to 9 exabytes.
"""
from sqlalchemy import text

revision = "0004_fix_file_size_column"

def upgrade(conn):
    # Alter the file_size_bytes column to BIGINT to support larger files
    conn.execute(text(
        """
        ALTER TABLE youtube_videos 
        ALTER COLUMN file_size_bytes TYPE BIGINT;
        """
    ))
    print("Changed youtube_videos.file_size_bytes from INTEGER to BIGINT")

def downgrade(conn):
    # Note: This downgrade may fail if there are values > INTEGER max
    conn.execute(text(
        """
        ALTER TABLE youtube_videos 
        ALTER COLUMN file_size_bytes TYPE INTEGER;
        """
    ))
    print("Changed youtube_videos.file_size_bytes from BIGINT to INTEGER")