-- =================================================================
-- Migration 001 — Calibration Schema
-- =================================================================
-- Phase 0 calibration tables. These are NOT part of the learner-
-- facing product schema — they exist purely to validate that the
-- AI scoring pipeline meets the Pearson correlation gate before
-- any real user receives a score.
--
-- Run with:
--   docker compose -f infrastructure/docker-compose.yml exec postgres \
--     psql -U lm_user -d linguamentor -f /dev/stdin \
--     < scripts/migrations/001_calibration_schema.sql
-- =================================================================

SET search_path TO linguamentor, public;

-- -----------------------------------------------------------------
-- calibration_essays
-- -----------------------------------------------------------------
-- Stores the raw essay samples used for calibration.
-- Each essay has a known difficulty level and exam type so we can
-- verify the AI scores correctly across the full band range —
-- not just at one difficulty level.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calibration_essays (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Which exam this essay was written for.
    -- Drives which rubric gets injected into the AI prompt.
    exam_type           VARCHAR(20) NOT NULL
                        CHECK (exam_type IN ('ielts_academic', 'ielts_general', 'toefl_ibt', 'delf_b1', 'delf_b2')),

    -- The writing task prompt the essay was responding to.
    -- Stored so we can reproduce the exact AI scoring context later.
    task_prompt         TEXT NOT NULL,

    -- The full essay text.
    essay_text          TEXT NOT NULL,

    -- Approximate band level of this essay as assessed during collection.
    -- Used to verify we have coverage across the full band range (4-9).
    -- NULL until a human grader confirms it.
    approximate_band    NUMERIC(3, 1),

    -- Where this essay came from — academic dataset, language school,
    -- commissioned writer, etc. Important for audit and licensing.
    source              VARCHAR(100) NOT NULL,

    -- Word count — essays under 50 words are invalid for IELTS Task 2.
    -- Computed at ingestion time, not recalculated on every query.
    word_count          INTEGER NOT NULL,

    -- Tracks whether this essay has been fully graded by the minimum
    -- required number of human examiners (2 per the calibration brief).
    -- The AI scoring pipeline only runs against essays where this is true.
    grading_complete    BOOLEAN NOT NULL DEFAULT FALSE,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on exam_type — most queries filter by exam type
-- when computing per-exam Pearson correlation
CREATE INDEX IF NOT EXISTS idx_cal_essays_exam_type
    ON calibration_essays (exam_type);

-- Index on grading_complete — the AI pipeline queries
-- WHERE grading_complete = TRUE frequently
CREATE INDEX IF NOT EXISTS idx_cal_essays_grading_complete
    ON calibration_essays (grading_complete);


-- -----------------------------------------------------------------
-- calibration_human_scores
-- -----------------------------------------------------------------
-- One row per examiner per essay. Two examiners grade each essay
-- independently. If they disagree by more than 1.0 band, a third
-- adjudicating examiner resolves it — that score is stored with
-- is_adjudicating = TRUE.
--
-- The consensus score (average of two agreeing examiners) is what
-- gets compared against the AI score in the Pearson computation.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calibration_human_scores (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    essay_id            UUID NOT NULL REFERENCES calibration_essays(id)
                        ON DELETE CASCADE,

    -- Anonymised examiner identifier — we track which examiner gave
    -- which score for inter-rater reliability computation but don't
    -- store PII in this table.
    examiner_id         VARCHAR(50) NOT NULL,

    -- IELTS/TOEFL rubric categories — all stored as separate columns
    -- so we can compute Pearson correlation per category, not just overall.
    -- Scores are on the 0.0-9.0 IELTS band scale in 0.5 increments.
    score_task_response         NUMERIC(3, 1) NOT NULL CHECK (score_task_response BETWEEN 0 AND 9),
    score_coherence_cohesion    NUMERIC(3, 1) NOT NULL CHECK (score_coherence_cohesion BETWEEN 0 AND 9),
    score_lexical_resource      NUMERIC(3, 1) NOT NULL CHECK (score_lexical_resource BETWEEN 0 AND 9),
    score_grammatical_range     NUMERIC(3, 1) NOT NULL CHECK (score_grammatical_range BETWEEN 0 AND 9),

    -- Composite overall band — weighted average of the four categories.
    -- Stored explicitly rather than computed on every query.
    score_overall               NUMERIC(3, 1) NOT NULL CHECK (score_overall BETWEEN 0 AND 9),

    -- TRUE for the third examiner brought in to resolve a disagreement.
    -- Adjudicating scores are used differently in consensus computation.
    is_adjudicating     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Examiner's qualitative notes — used during rubric prompt tuning
    -- to understand why the AI and human diverged on specific essays.
    grader_notes        TEXT,

    graded_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One examiner grades one essay once — prevent duplicate submissions
CREATE UNIQUE INDEX IF NOT EXISTS idx_cal_human_scores_unique
    ON calibration_human_scores (essay_id, examiner_id);

CREATE INDEX IF NOT EXISTS idx_cal_human_scores_essay_id
    ON calibration_human_scores (essay_id);


-- -----------------------------------------------------------------
-- calibration_ai_scores
-- -----------------------------------------------------------------
-- Stores the AI pipeline's score for each essay.
-- One row per essay per calibration run — when we tune the rubric
-- prompt and re-run, we create a new row rather than overwriting.
-- This gives us a full history of how each prompt version performed.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calibration_ai_scores (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    essay_id            UUID NOT NULL REFERENCES calibration_essays(id)
                        ON DELETE CASCADE,

    -- Which calibration run this score belongs to.
    -- Ties back to calibration_runs.id so we can group scores
    -- by run and compare across prompt tuning iterations.
    run_id              UUID NOT NULL,

    -- Mirrors the human score columns exactly — same scale, same
    -- categories. This parallel structure makes the Pearson
    -- computation straightforward: zip the two columns together.
    score_task_response         NUMERIC(3, 1) CHECK (score_task_response BETWEEN 0 AND 9),
    score_coherence_cohesion    NUMERIC(3, 1) CHECK (score_coherence_cohesion BETWEEN 0 AND 9),
    score_lexical_resource      NUMERIC(3, 1) CHECK (score_lexical_resource BETWEEN 0 AND 9),
    score_grammatical_range     NUMERIC(3, 1) CHECK (score_grammatical_range BETWEEN 0 AND 9),
    score_overall               NUMERIC(3, 1) CHECK (score_overall BETWEEN 0 AND 9),

    -- The LLM model that produced this score.
    -- Stored here because we may test multiple models during calibration
    -- before deciding which one meets the 0.85 threshold.
    model_name          VARCHAR(100) NOT NULL,
    model_version       VARCHAR(50) NOT NULL,

    -- SHA-256 hash of the exact prompt sent to the LLM.
    -- If two runs produce different scores for the same essay,
    -- comparing prompt hashes tells us whether the prompt changed.
    prompt_hash         VARCHAR(64) NOT NULL,

    -- Raw JSON response from the LLM before parsing.
    -- Kept for debugging prompt tuning failures — when the AI
    -- scores an essay badly, we need to see exactly what it said.
    raw_response        JSONB,

    -- Latency of this specific scoring call in milliseconds.
    -- Used to verify the < 6s P95 SLA during calibration load testing.
    latency_ms          INTEGER,

    scored_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_ai_scores_essay_id
    ON calibration_ai_scores (essay_id);

CREATE INDEX IF NOT EXISTS idx_cal_ai_scores_run_id
    ON calibration_ai_scores (run_id);


-- -----------------------------------------------------------------
-- calibration_runs
-- -----------------------------------------------------------------
-- One row per full calibration run — each time we run the AI
-- pipeline against the complete essay set and compute Pearson.
--
-- This table is the audit trail. It answers: "when was calibration
-- done, with which prompt version, and did it pass?"
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calibration_runs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Human-readable label for this run — 'initial-run',
    -- 'rubric-tuning-v2', 'pre-launch-final', etc.
    run_label           VARCHAR(100) NOT NULL,

    -- Which exam type this run covers.
    exam_type           VARCHAR(20) NOT NULL
                        CHECK (exam_type IN ('ielts_academic', 'ielts_general', 'toefl_ibt', 'delf_b1', 'delf_b2')),

    -- Number of essays scored in this run.
    -- Compared against total available essays to catch partial runs.
    essays_scored       INTEGER NOT NULL DEFAULT 0,

    -- Pearson correlation results per rubric category and overall.
    -- NULL until the run completes and correlation is computed.
    -- These are the numbers that determine pass/fail.
    pearson_task_response       NUMERIC(4, 3),
    pearson_coherence_cohesion  NUMERIC(4, 3),
    pearson_lexical_resource    NUMERIC(4, 3),
    pearson_grammatical_range   NUMERIC(4, 3),
    pearson_overall             NUMERIC(4, 3),

    -- TRUE only when ALL five Pearson values are >= 0.85.
    -- This is the field the Go/No-Go gate checks.
    passed_threshold    BOOLEAN NOT NULL DEFAULT FALSE,

    -- The prompt configuration hash used in this run.
    -- When we tune the rubric prompt, this changes — giving us
    -- a direct link between prompt version and correlation result.
    prompt_config_hash  VARCHAR(64),

    -- Run lifecycle timestamps
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,

    -- Free-text notes from the developer running calibration.
    -- Used to document what changed between tuning iterations.
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_cal_runs_exam_type
    ON calibration_runs (exam_type);

-- Partial index — we query for passing runs frequently
-- (specifically to find the latest passing run for baseline storage)
CREATE INDEX IF NOT EXISTS idx_cal_runs_passed
    ON calibration_runs (passed_threshold)
    WHERE passed_threshold = TRUE;


-- -----------------------------------------------------------------
-- calibration_baseline
-- -----------------------------------------------------------------
-- Immutable record of the approved calibration results.
-- Written once when the Go/No-Go gate is passed and signed off.
-- Never updated. Never deleted.
--
-- Every AI evaluation in production references this table to
-- display the calibration confidence indicator on score reports:
-- "This score was calibrated against N essays. Correlation: 0.88"
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calibration_baseline (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- The canonical version string referenced in every AIModelRun.
    -- 'v1.0-launch' is the value set when Phase 0 passes.
    calibration_version VARCHAR(50) NOT NULL UNIQUE,

    -- The calibration run that produced these results.
    run_id              UUID NOT NULL REFERENCES calibration_runs(id),

    -- Final approved Pearson values — copied from the passing run.
    -- Stored here so reports can display them without joining to runs.
    pearson_overall             NUMERIC(4, 3) NOT NULL,
    pearson_task_response       NUMERIC(4, 3) NOT NULL,
    pearson_coherence_cohesion  NUMERIC(4, 3) NOT NULL,
    pearson_lexical_resource    NUMERIC(4, 3) NOT NULL,
    pearson_grammatical_range   NUMERIC(4, 3) NOT NULL,

    -- Total essays used in the approved calibration run.
    -- Displayed on user score reports for transparency.
    essays_count        INTEGER NOT NULL,

    -- Who signed off on the Go/No-Go decision.
    approved_by         VARCHAR(100) NOT NULL,
    approved_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- This record is immutable — no updates allowed after creation.
    -- Enforced at the application layer, documented here for clarity.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -----------------------------------------------------------------
-- Verification
-- -----------------------------------------------------------------
SELECT
    table_name,
    pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS size
FROM information_schema.tables
WHERE table_schema = 'linguamentor'
  AND table_name LIKE 'calibration_%'
ORDER BY table_name;
