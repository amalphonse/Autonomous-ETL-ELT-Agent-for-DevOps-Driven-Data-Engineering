-- Initialize PostgreSQL database for ETL agent
-- This file runs automatically when PostgreSQL container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas if needed (future use)
-- CREATE SCHEMA IF NOT EXISTS etl;

-- Create indexes for common queries
-- These will be created by Alembic migrations, but we prepare the groundwork here

-- Set default session parameters for better performance
ALTER DATABASE etl_agent_db SET log_statement = 'all';
ALTER DATABASE etl_agent_db SET log_duration = true;
