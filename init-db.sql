-- PostgreSQL database initialization for AI Video Generator
-- This script sets up the database with optimal settings for the application

-- Set timezone to UTC for consistency
SET timezone = 'UTC';

-- Create the videohelper database if it doesn't exist
-- (This is typically done by POSTGRES_DB environment variable, but we'll ensure it)

-- Create indexes and optimize for the jobs table
-- These will be created automatically by SQLAlchemy, but we can add additional optimizations

-- Set connection limits and timeouts for better performance
ALTER DATABASE videohelper SET shared_preload_libraries = 'pg_stat_statements';
ALTER DATABASE videohelper SET pg_stat_statements.max = 10000;
ALTER DATABASE videohelper SET pg_stat_statements.track = 'all';

-- Optimize PostgreSQL settings for the workload
ALTER DATABASE videohelper SET work_mem = '64MB';
ALTER DATABASE videohelper SET maintenance_work_mem = '256MB';
ALTER DATABASE videohelper SET effective_cache_size = '1GB';

-- Enable extensions that might be useful
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create a function to update the updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- The jobs table will be created by SQLAlchemy with proper indexes
-- Additional performance optimizations can be added here as needed

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'AI Video Generator PostgreSQL database initialized successfully';
END $$;
