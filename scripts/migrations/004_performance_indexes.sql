-- =================================================================
-- Migration 004 — Production Performance Indexes
-- =================================================================
-- Purpose:
--   Add the missing indexes required to sustain the PRD performance
--   SLAs at production load (1,000+ concurrent users).
--
--   PRD §9.1 Hard SLAs:
--     - API responses (non-AI): < 300ms P95
--     - Essay scoring (async):  < 6s P95
--     - Daily SRS (cached):     < 200ms P95
--
--   Without these indexes, query plans degrade to sequential scans
--   on tables that will reach millions of rows in production:
--     - ai_model_runs      → 1 row per every LLM call, every user, every day
--     - writing_sessions   → 1 row per essay submission
--     - learner_profiles   → 1 row per user (relatively small but hot)
--
-- NOTE ON POOL CONFIG (not a SQL concern — documented here for traceability):
--   asyncpg pool settings live in shared/db_utils/connection.py.
--   Production values:
--     min_size=5                         — keep 5 connections warm at all times
--     max_size=20                        — ceiling for burst load
--     max_inactive_connection_lifetime=300.0  — recycle idle connections after 5 min
--   These values were chosen based on:
--     - Writing eval workers hold connections for up to 6s (LLM wait time)
--     - At 10 concurrent evals, 10 connections are occupied for up to 6s each
--     - max_size=20 gives 2x headroom above that worst case
--     - min_size=5 prevents cold connection establishment on first-morning traffic
--
-- Run with:
--   docker cp scripts/migrations/004_performance_indexes.sql lm_postgres:/tmp/004.sql
--   docker exec lm_postgres psql -U lm_user -d linguamentor -f /tmp/004.sql
-- =================================================================

SET search_path TO linguamentor, public;

-- =================================================================
-- BLOCK 1 — pg_stat_statements
-- =================================================================
-- Enables per-query execution statistics collection at the DB level.
--
-- WHY THIS MATTERS:
--   Without pg_stat_statements, when Grafana shows P95 latency
--   spiking, you have NO way to identify which SQL query is the
--   culprit. With it, you can run:
--     SELECT query, mean_exec_time, calls
--     FROM pg_stat_statements
--     ORDER BY mean_exec_time DESC LIMIT 20;
--   ...and immediately see which query is slow and how often it runs.
--
-- PRD §9 mandates Prometheus + Grafana observability. pg_stat_statements
-- is the PostgreSQL foundation that feeds the query-level metrics.
--
-- IMPORTANT: After enabling, add to postgresql.conf (or docker env):
--   shared_preload_libraries = 'pg_stat_statements'
-- For local docker-compose dev, this extension activates automatically
-- on CREATE EXTENSION. Production k8s deployments need the preload config.
-- =================================================================

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;


-- =================================================================
-- BLOCK 2 — writing_sessions indexes
-- =================================================================
-- Query patterns this table must serve efficiently:
--
--   Pattern A — "My recent evaluations" (dashboard, hot path):
--     SELECT * FROM writing_sessions
--     WHERE user_id = $1 AND deleted_at IS NULL
--     ORDER BY created_at DESC LIMIT 20;
--
--   Pattern B — "Evaluation result polling" (GET /writing/result/:job_id):
--     SELECT status, score_overall, feedback_json, calibration_version
--     FROM writing_sessions
--     WHERE id = $1 AND user_id = $2;
--     → Covered by PK on id. No new index needed.
--
--   Pattern C — "BullMQ worker stall detection" (cron every 30s):
--     SELECT id FROM writing_sessions
--     WHERE status IN ('pending', 'processing')
--     AND created_at < NOW() - INTERVAL '30 seconds';
--     → Partial index on status already exists from migration 003.
--     → Add created_at to make the time-window filter index-only.
--
--   Pattern D — "Score report — fetch AI run metadata":
--     SELECT amr.model_name, amr.calibration_version, amr.latency_ms
--     FROM writing_sessions ws
--     JOIN ai_model_runs amr ON amr.id = ws.ai_model_run_id
--     WHERE ws.id = $1;
--     → FK join on ai_model_run_id — needs index on writing_sessions side.
-- =================================================================

-- Pattern A: user dashboard — recent evaluations
-- Replaces the migration 003 index which lacked status in the covering columns
DROP INDEX IF EXISTS linguamentor.idx_writing_sessions_user_id;

CREATE INDEX IF NOT EXISTS idx_ws_user_status_created
    ON writing_sessions (user_id, created_at DESC)
    INCLUDE (status, score_overall, exam_type)
    WHERE deleted_at IS NULL;

COMMENT ON INDEX linguamentor.idx_ws_user_status_created IS
    'Covers dashboard query: recent writing sessions per user. '
    'INCLUDE avoids heap fetch for the three most-read columns.';

-- Pattern C: stall detection — extend existing partial index to include created_at
-- The old index only has (status) — adding created_at makes the time filter index-only
DROP INDEX IF EXISTS linguamentor.idx_writing_sessions_status;

CREATE INDEX IF NOT EXISTS idx_ws_pending_created
    ON writing_sessions (created_at ASC)
    WHERE status IN ('pending', 'processing');

COMMENT ON INDEX linguamentor.idx_ws_pending_created IS
    'BullMQ stall detection: finds jobs stuck in pending/processing '
    'for longer than the expected SLA window. Low cardinality filter '
    'combined with time range — partial index keeps it small.';

-- Pattern D: FK join to ai_model_runs for score reports
CREATE INDEX IF NOT EXISTS idx_ws_ai_model_run_id
    ON writing_sessions (ai_model_run_id)
    WHERE ai_model_run_id IS NOT NULL;

COMMENT ON INDEX linguamentor.idx_ws_ai_model_run_id IS
    'FK join from writing_sessions to ai_model_runs. '
    'Partial (NOT NULL) keeps the index small — NULL means not yet scored.';


-- =================================================================
-- BLOCK 3 — ai_model_runs indexes
-- =================================================================
-- This is the highest-write table in the system. Every LLM call —
-- for every user, every session, every appeal, every daily diagnostic —
-- inserts a row. At 10,000 active users doing 3 AI calls/day,
-- that's 30,000 rows/day = ~900,000 rows/month.
--
-- Query patterns:
--
--   Pattern A — Calibration drift monitor (weekly cron, PRD §11.5):
--     SELECT AVG(latency_ms), COUNT(*)
--     FROM ai_model_runs
--     WHERE calibration_version = 'v1.0-launch'
--     AND created_at > NOW() - INTERVAL '7 days';
--
--   Pattern B — Provider cost breakdown (Grafana dashboard):
--     SELECT model_name, COUNT(*), SUM(input_token_count + output_token_count)
--     FROM ai_model_runs
--     WHERE created_at > NOW() - INTERVAL '30 days'
--     GROUP BY model_name;
--
--   Pattern C — Latency trend per provider per task (SLA monitoring):
--     SELECT provider_name, task_type,
--            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)
--     FROM ai_model_runs
--     WHERE created_at > NOW() - INTERVAL '1 day'
--     GROUP BY provider_name, task_type;
--
--   Pattern D — Per-user AI cost ceiling enforcement (real-time):
--     SELECT COUNT(*) FROM ai_model_runs
--     WHERE user_reference_id = $1
--     AND task_type = 'writing_score'
--     AND created_at > date_trunc('month', NOW());
--
-- NOTE: ai_model_runs is append-only. No UPDATEs. This means
-- BRIN indexes are ideal for created_at — they're tiny (pages/blocks)
-- and extremely fast for time-range queries on monotonically
-- increasing timestamp columns. BTREE for everything else.
-- =================================================================

-- Pattern A: calibration drift monitor
CREATE INDEX IF NOT EXISTS idx_amr_calibration_version_created
    ON ai_model_runs (calibration_version, created_at DESC)
    WHERE calibration_version IS NOT NULL;

COMMENT ON INDEX linguamentor.idx_amr_calibration_version_created IS
    'Calibration drift monitor weekly query. Partial (NOT NULL) '
    'excludes non-AI-evaluation rows (e.g. health checks).';

-- Pattern B: provider cost breakdown
CREATE INDEX IF NOT EXISTS idx_amr_model_name_created
    ON ai_model_runs (model_name, created_at DESC);

COMMENT ON INDEX linguamentor.idx_amr_model_name_created IS
    'Grafana cost dashboard: token usage grouped by model over time.';

-- Pattern C: latency trend per provider per task type
CREATE INDEX IF NOT EXISTS idx_amr_provider_task_created
    ON ai_model_runs (provider_name, task_type, created_at DESC)
    WHERE provider_name IS NOT NULL;

COMMENT ON INDEX linguamentor.idx_amr_provider_task_created IS
    'SLA monitoring: P95 latency per provider per task type. '
    'Used by the PRD §9.1 latency alert rules in Prometheus.';

-- Pattern D: per-user monthly AI usage ceiling
-- This replaces the migration 003 index which lacked task_type
DROP INDEX IF EXISTS linguamentor.idx_ai_model_runs_user_ref;

CREATE INDEX IF NOT EXISTS idx_amr_user_ref_task_created
    ON ai_model_runs (user_reference_id, task_type, created_at DESC)
    WHERE user_reference_id IS NOT NULL;

COMMENT ON INDEX linguamentor.idx_amr_user_ref_task_created IS
    'Per-user AI usage enforcement. Partial (NOT NULL) because '
    'GDPR-erased rows have user_reference_id set to NULL — those '
    'must be excluded from usage counts (PRD §10.5, §28.2).';

-- BRIN index on created_at — tiny footprint, fast time-range scans
-- on this append-only table. Complements the BTREE indexes above
-- for pure date-range queries that don't filter on other columns.
CREATE INDEX IF NOT EXISTS idx_amr_created_brin
    ON ai_model_runs USING BRIN (created_at)
    WITH (pages_per_range = 128);

COMMENT ON INDEX linguamentor.idx_amr_created_brin IS
    'BRIN index for pure time-range scans on append-only table. '
    'pages_per_range=128 balances granularity vs index size. '
    'Orders of magnitude smaller than BTREE for monotonic columns.';

-- Keep the existing task_type + created_at index from migration 003
-- (idx_ai_model_runs_task_time) — it covers a different access pattern
-- (task-first filters) vs the provider+task index above.


-- =================================================================
-- BLOCK 4 — learner_profiles indexes
-- =================================================================
-- This table has one row per user but is READ on EVERY AI call
-- because accent_target and target_exam drive rubric and ASR selection
-- (PRD §19.4 Layer 6 — User Context).
--
-- At 10,000 users the table is small, but these are hot lookup columns
-- that appear in JOIN conditions and WHERE clauses on every
-- prompt assembly. Index them.
-- =================================================================

-- accent_target: drives ASR model selection (every voice session)
-- and pronunciation rubric parameterization
CREATE INDEX IF NOT EXISTS idx_lp_accent_target
    ON learner_profiles (accent_target);

COMMENT ON INDEX linguamentor.idx_lp_accent_target IS
    'ASR model selection and pronunciation rubric parameterization. '
    'READ on every voice session and every writing session prompt assembly.';

-- target_exam: drives rubric injection at prompt Layer 5
-- Partial — NULL means fluency track (no exam target), skip those
CREATE INDEX IF NOT EXISTS idx_lp_target_exam
    ON learner_profiles (target_exam)
    WHERE target_exam IS NOT NULL;

COMMENT ON INDEX linguamentor.idx_lp_target_exam IS
    'Rubric selection at prompt Layer 5. Partial (NOT NULL) — '
    'fluency-track users have no exam target and never need rubric selection.';

-- target_language: drives language-level routing in adaptive engine
CREATE INDEX IF NOT EXISTS idx_lp_target_language
    ON learner_profiles (target_language);

COMMENT ON INDEX linguamentor.idx_lp_target_language IS
    'Language routing for adaptive engine and SRS scheduler. '
    'Separates English and French cohorts for batch processing.';

-- Composite: cefr_writing + user_id — used by placement gate checks
-- and writing session CEFR classification validation
CREATE INDEX IF NOT EXISTS idx_lp_cefr_writing_user
    ON learner_profiles (cefr_writing, user_id)
    WHERE cefr_writing IS NOT NULL;

COMMENT ON INDEX linguamentor.idx_lp_cefr_writing_user IS
    'CEFR level gate checks and band projection queries. '
    'Partial (NOT NULL) — new users have no CEFR level until placement.';


-- =================================================================
-- BLOCK 5 — readiness_snapshots indexes
-- =================================================================
-- This is a time-series table — one row per session completion per user.
-- PRD §25.2 requires a trend chart (last 30 days of readiness index).
-- The existing index covers (user_id, created_at DESC) — correct.
-- Add a BRIN for full-table time-range scans (admin analytics).
-- =================================================================

CREATE INDEX IF NOT EXISTS idx_rs_created_brin
    ON readiness_snapshots USING BRIN (created_at)
    WITH (pages_per_range = 64);

COMMENT ON INDEX linguamentor.idx_rs_created_brin IS
    'Admin analytics: cohort readiness trends over time. '
    'BRIN is appropriate — readiness_snapshots is append-only.';


-- =================================================================
-- BLOCK 6 — skill_vectors indexes
-- =================================================================
-- Skill vectors are updated after EVERY session (weighted moving average).
-- The SRS priority formula queries ALL 6 dimension scores + intervals
-- for a user in one shot. The existing UNIQUE index on user_id covers
-- that lookup. No additional indexes needed here.
--
-- The version column (optimistic concurrency) does not need an index —
-- it's always accessed via the user_id UNIQUE constraint lookup.
-- =================================================================

-- No new indexes needed for skill_vectors. Documented for clarity.


-- =================================================================
-- BLOCK 7 — score_appeals indexes
-- =================================================================
-- Appeals are low-frequency but must be fast (PRD §42: 60s resolution).
-- Add an index on status for the appeal worker queue check.
-- =================================================================

CREATE INDEX IF NOT EXISTS idx_appeals_status_created
    ON score_appeals (status, created_at ASC)
    WHERE status IN ('pending', 'escalated');

COMMENT ON INDEX linguamentor.idx_appeals_status_created IS
    'Appeal worker queue: finds pending appeals in FIFO order. '
    'Partial — only active statuses. Resolved/error appeals excluded.';


-- =================================================================
-- BLOCK 8 — daily_sessions indexes
-- =================================================================
-- The SRS pre-generation cron runs at 2AM UTC and generates sessions
-- for ALL users whose next session date = tomorrow.
-- The UNIQUE constraint on (user_id, session_date) is already the
-- primary lookup. Add an index for the bulk generation query.
-- =================================================================

CREATE INDEX IF NOT EXISTS idx_ds_session_date_completed
    ON daily_sessions (session_date, completed)
    WHERE completed = FALSE;

COMMENT ON INDEX linguamentor.idx_ds_session_date_completed IS
    'SRS scheduler: find all incomplete sessions for a given date. '
    'Used by the 2AM UTC cron to detect missed/stale sessions. '
    'Partial (completed=FALSE) — completed sessions are not queried here.';


-- =================================================================
-- AUTOVACUUM TUNING for high-write tables
-- =================================================================
-- ai_model_runs is append-only and high-write. Default autovacuum
-- settings are too conservative — they wait for 20% of rows to be
-- dead before vacuuming. On an append-only table, dead row accumulation
-- comes from HOT updates on the table metadata, not from row updates.
-- We reduce the scale_factor to keep the FSM (Free Space Map) fresh.
--
-- writing_sessions is updated frequently (pending → processing → scored)
-- which creates dead row versions. Tighter vacuum keeps bloat low.
-- =================================================================

ALTER TABLE linguamentor.ai_model_runs
    SET (
        autovacuum_vacuum_scale_factor     = 0.01,   -- vacuum when 1% rows are dead (vs 20%)
        autovacuum_analyze_scale_factor    = 0.005,  -- analyze when 0.5% rows are new
        autovacuum_vacuum_cost_delay       = 2,      -- ms — aggressive but not blocking
        autovacuum_vacuum_insert_scale_factor = 0.01 -- trigger after 1% inserts too
    );

ALTER TABLE linguamentor.writing_sessions
    SET (
        autovacuum_vacuum_scale_factor  = 0.05,  -- vacuum when 5% rows are dead
        autovacuum_analyze_scale_factor = 0.02
    );

ALTER TABLE linguamentor.readiness_snapshots
    SET (
        autovacuum_vacuum_scale_factor     = 0.01,
        autovacuum_analyze_scale_factor    = 0.005,
        autovacuum_vacuum_insert_scale_factor = 0.01
    );


-- =================================================================
-- VERIFICATION
-- =================================================================
-- Run this after migration to confirm all indexes were created.
-- Expected: all indexes listed with their table and size.
-- If size shows "0 bytes", the table is empty — that's fine in dev.
-- =================================================================

SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    indexdef
FROM pg_indexes
WHERE schemaname = 'linguamentor'
  AND indexname LIKE ANY (ARRAY[
      'idx_ws_%',
      'idx_amr_%',
      'idx_lp_%',
      'idx_rs_%',
      'idx_ds_%',
      'idx_appeals_%'
  ])
ORDER BY tablename, indexname;

-- Also confirm pg_stat_statements is active
SELECT name, setting
FROM pg_settings
WHERE name IN ('shared_preload_libraries', 'pg_stat_statements.track');
