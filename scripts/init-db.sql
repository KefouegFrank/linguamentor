-- =============================================================
-- LinguaMentor Database Initialization Script
-- =============================================================
-- Purpose : One-time setup of the PostgreSQL database
--           before any service or migration runs.
--
-- What this does NOT do:
--   - Create application tables (handled by Alembic migrations in Phase 1)
--   - Insert seed data (handled by separate seed scripts)
--
-- Run with:
--   docker compose exec postgres psql -U lm_user -d linguamentor \
--     -f /dev/stdin < scripts/init-db.sql
-- =============================================================

-- uuid-ossp: enables uuid_generate_v4() for primary keys.
-- Every entity in LinguaMentor uses UUID PKs — not auto-increment integers.
-- UUIDs are safe to generate in application code without DB coordination,
-- which is critical when multiple services create records independently.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pg_trgm: enables trigram-based fuzzy text search.
-- Used later for searching feedback content and learner submissions.
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Dedicated schema to namespace all LinguaMentor tables.
-- Keeps the database clean if other schemas are ever added
-- (e.g., a monitoring schema for Prometheus metrics).
CREATE SCHEMA IF NOT EXISTS linguamentor;

-- Set the default search path so queries don't need
-- to prefix every table with 'linguamentor.'
ALTER DATABASE linguamentor SET search_path TO linguamentor, public;

-- Verification output — confirm everything was created correctly
SELECT
    current_database()  AS database,
    current_schema()    AS schema,
    version()           AS postgres_version;
