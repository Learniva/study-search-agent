-- Initialize PostgreSQL database with extensions
-- This script is executed when the postgres container starts for the first time

-- Create the pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the uuid-ossp extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the pg_trgm extension for fuzzy text matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create indexes to improve performance
-- These will be created when tables are created by SQLAlchemy