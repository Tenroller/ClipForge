-- PostgreSQL database initialization for AI Video Generator
-- This script sets up the database with optimal settings for the application

-- Set timezone to UTC for consistency
SET timezone = 'UTC';

-- Enable extensions that might be useful
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create the jobs table for job management
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    workflow VARCHAR(100) NOT NULL,
    step VARCHAR(100),
    user_id VARCHAR(255),
    request_data JSONB,
    result JSONB,
    resume_data JSONB,
    resumed_from UUID,
    resumed_to JSONB,  -- Changed from UUID[] to JSONB to match SQLAlchemy model
    resume_attempt INTEGER DEFAULT 1,
    error_message TEXT,  -- Changed from 'error' to match SQLAlchemy model
    logs JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds REAL
);

-- Create videos table for gallery functionality
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    size_bytes BIGINT,
    duration_seconds REAL,
    workflow VARCHAR(100) NOT NULL,
    video_type VARCHAR(50),
    compilation_type VARCHAR(50),
    compilation_num INTEGER,
    posted BOOLEAN DEFAULT FALSE NOT NULL,
    posted_at TIMESTAMP WITH TIME ZONE,
    video_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Legacy columns (kept for backward compatibility)
    title VARCHAR(255),
    description TEXT,
    duration REAL,
    file_size BIGINT,
    thumbnail_path TEXT,
    status VARCHAR(50) DEFAULT 'processing',
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_workflow ON jobs(workflow);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_updated_at ON jobs(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_resume_attempt ON jobs(resume_attempt);

-- Create indexes for videos table to match SQLAlchemy model
CREATE INDEX IF NOT EXISTS ix_videos_job_id ON videos(job_id);
CREATE INDEX IF NOT EXISTS ix_videos_workflow ON videos(workflow);
CREATE INDEX IF NOT EXISTS ix_videos_posted ON videos(posted);
CREATE INDEX IF NOT EXISTS ix_videos_created_at ON videos(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_videos_workflow_posted ON videos(workflow, posted);
CREATE INDEX IF NOT EXISTS idx_videos_video_type ON videos(video_type);
CREATE INDEX IF NOT EXISTS idx_videos_size_bytes ON videos(size_bytes);

-- Legacy indexes for backward compatibility
CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);

-- Create a function to update the updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for automatic updated_at timestamp updates
DROP TRIGGER IF EXISTS update_jobs_updated_at ON jobs;
CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_videos_updated_at ON videos;
CREATE TRIGGER update_videos_updated_at
    BEFORE UPDATE ON videos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Optimize PostgreSQL settings for the workload
ALTER DATABASE videohelper SET work_mem = '64MB';
ALTER DATABASE videohelper SET maintenance_work_mem = '256MB';
ALTER DATABASE videohelper SET effective_cache_size = '1GB';
ALTER DATABASE videohelper SET shared_preload_libraries = 'pg_stat_statements';
ALTER DATABASE videohelper SET pg_stat_statements.max = 10000;
ALTER DATABASE videohelper SET pg_stat_statements.track = 'all';

-- Grant permissions to the application user (videohelper_user)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO videohelper_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO videohelper_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO videohelper_user;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'AI Video Generator PostgreSQL database initialized successfully with tables: jobs, videos';
    RAISE NOTICE 'Database optimizations applied for video processing workload';
END $$;
