-- =============================================================
-- LinguaMentor Phase 1 — Complete Application Schema
-- Migration: 003_phase1_schema.sql
-- =============================================================
-- Domains covered:
--   1. Identity & Auth     → users, refresh_tokens
--   2. Learner Profile     → learner_profiles, skill_vectors
--   3. AI Evaluation       → writing_sessions, speaking_sessions
--   4. Adaptive Engine     → srs_schedules, daily_sessions, score_appeals
--   5. Exam & Progress     → exam_attempts, exam_sections,
--                            readiness_snapshots, share_events
--   6. AI Infrastructure   → ai_model_runs
--
-- Design rules enforced:
--   • All PKs are UUID v4 (uuid_generate_v4())
--   • All scores stored as NUMERIC(4,2) — never FLOAT
--   • All timestamps UTC, named created_at / updated_at
--   • Soft deletes: deleted_at column, NULL means active
--   • PII lives in users only — all other tables use user_id FK
--   • Every AI evaluation references an ai_model_run_id FK
-- =============================================================

SET search_path TO linguamentor, public;


-- =============================================================
-- DOMAIN 1: IDENTITY & AUTH
-- =============================================================

-- The only table that stores PII (email, display_name).
-- All other tables reference this via user_id FK.
-- Downstream services never store name or email — PRD §28.2.
CREATE TABLE IF NOT EXISTS users (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- PII — isolated here by PRD design principle
    email                   VARCHAR(320) NOT NULL UNIQUE,
    display_name            VARCHAR(100),
    password_hash           VARCHAR(255) NOT NULL,   -- argon2id hash

    -- Role-based access control — enforced at API Gateway (PRD §10.4)
    -- Values: learner | admin | institution_admin
    role                    VARCHAR(30) NOT NULL DEFAULT 'learner',

    -- Subscription tier gates feature access throughout the system
    -- Values: free | pro
    subscription_tier       VARCHAR(20) NOT NULL DEFAULT 'free',

    -- GDPR / Privacy consent flags (PRD §10.5)
    voice_recording_consent BOOLEAN NOT NULL DEFAULT FALSE,
    retraining_opt_out      BOOLEAN NOT NULL DEFAULT FALSE,

    -- Active = not deleted. NULL = active user.
    -- Hard delete only on GDPR erasure request (PRD §28.2)
    deleted_at              TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast email lookups on login
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)
    WHERE deleted_at IS NULL;

-- Refresh token table — one per session/device.
-- Access tokens are stateless JWTs. Refresh tokens are stored
-- here so we can invalidate them on logout and detect reuse.
-- Rotation: every use issues a new token and invalidates the old one.
-- (PRD §10.4 — 7-day lifetime, HTTP-only cookie storage)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Stored as SHA-256 hash — never plaintext (defense in depth)
    token_hash              VARCHAR(64) NOT NULL UNIQUE,

    -- Device/session label for multi-device support
    device_label            VARCHAR(100),

    -- When this token was last successfully used
    last_used_at            TIMESTAMPTZ,
    expires_at              TIMESTAMPTZ NOT NULL,
    revoked_at              TIMESTAMPTZ,     -- NULL = still valid

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens (token_hash)
    WHERE revoked_at IS NULL;


-- =============================================================
-- DOMAIN 2: LEARNER PROFILE
-- =============================================================

-- Per-learner learning configuration and 4D CEFR state.
-- One row per user. Created during placement test (Stage 1, PRD §14.1).
-- Language, exam target, and accent config all live here and flow
-- into every AI prompt via Layer 6 of the prompt stack (PRD §19.4).
CREATE TABLE IF NOT EXISTS learner_profiles (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- Language and exam configuration — drives rubric selection
    -- and AI prompt parameterization throughout the system
    target_language         VARCHAR(10) NOT NULL DEFAULT 'en',   -- 'en' | 'fr'
    target_exam             VARCHAR(30),   -- 'IELTS' | 'TOEFL' | 'DELF' | NULL (fluency track)
    exam_date               DATE,          -- Target exam date for countdown and urgency signals

    -- Accent target — parameterizes ASR model selection and
    -- pronunciation scoring baseline (PRD §7.2, §20.4)
    -- Values: en-US | en-UK | fr-FR | fr-CA
    accent_target           VARCHAR(10) NOT NULL DEFAULT 'en-US',

    -- Teaching persona — default for new sessions.
    -- Also stored in Redis persona:{session_id} per active session.
    -- Values: companion | coach | examiner (PRD §17.2)
    default_persona         VARCHAR(20) NOT NULL DEFAULT 'companion',

    -- Track selection — affects dashboard layout and content emphasis
    -- Values: fluency | exam
    track                   VARCHAR(20) NOT NULL DEFAULT 'fluency',

    -- Current 4D CEFR levels — updated by adaptive engine after sessions.
    -- Values: A1 | A2 | B1 | B2 | C1 | C2
    -- Listening and reading start as NULL (not yet measured, PRD §7.4)
    cefr_writing            VARCHAR(5),
    cefr_speaking           VARCHAR(5),
    cefr_listening          VARCHAR(5),    -- activated Phase 2
    cefr_reading            VARCHAR(5),    -- activated Phase 3

    -- Weakness tags — populated by adaptive engine when a skill
    -- dimension falls below threshold for 3 sessions (PRD §23.2)
    -- JSONB array: [{dimension, severity, detected_at}, ...]
    weakness_tags           JSONB NOT NULL DEFAULT '[]',

    -- Daily engagement streak — consecutive days with completed micro-session
    current_streak          INTEGER NOT NULL DEFAULT 0,
    longest_streak          INTEGER NOT NULL DEFAULT 0,
    last_session_date       DATE,

    -- Placement test completed flag — gating for first session
    placement_completed     BOOLEAN NOT NULL DEFAULT FALSE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- 6-dimensional skill vector per learner (PRD §22, §23).
-- Updated using weighted moving average after every session:
-- new_score = (previous × 0.8) + (recent × 0.2)
-- All dimensions normalized 0.0–1.0.
-- Also drives SRS priority formula and readiness prediction.
CREATE TABLE IF NOT EXISTS skill_vectors (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- The 6 skill dimensions (PRD §22.1)
    -- All NUMERIC(4,3) for 0.000 to 1.000 precision
    grammar                 NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    vocabulary              NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    coherence               NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    pronunciation           NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    fluency                 NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    comprehension           NUMERIC(4,3) NOT NULL DEFAULT 0.0,

    -- SRS tracking per dimension — drives Daily Diagnostic scheduling.
    -- Stored here so the SRS scheduler can compute priority formula
    -- without joining to session history (PRD §23.3).
    -- Priority = (days_since × 0.4) + ((1-score) × 0.4) + (volatility × 0.2)
    grammar_last_practiced_at       TIMESTAMPTZ,
    grammar_repetition_interval     INTEGER NOT NULL DEFAULT 1,   -- days

    vocabulary_last_practiced_at    TIMESTAMPTZ,
    vocabulary_repetition_interval  INTEGER NOT NULL DEFAULT 1,

    coherence_last_practiced_at     TIMESTAMPTZ,
    coherence_repetition_interval   INTEGER NOT NULL DEFAULT 1,

    pronunciation_last_practiced_at TIMESTAMPTZ,
    pronunciation_repetition_interval INTEGER NOT NULL DEFAULT 1,

    fluency_last_practiced_at       TIMESTAMPTZ,
    fluency_repetition_interval     INTEGER NOT NULL DEFAULT 1,

    comprehension_last_practiced_at TIMESTAMPTZ,
    comprehension_repetition_interval INTEGER NOT NULL DEFAULT 1,

    -- Version counter — incremented on every update for
    -- optimistic concurrency control when multiple sessions
    -- update the vector simultaneously
    version                 INTEGER NOT NULL DEFAULT 0,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================
-- DOMAIN 3: AI EVALUATION
-- =============================================================

-- Writing session — one row per essay submission.
-- Async pipeline: status moves PENDING → PROCESSING → SCORED.
-- Scores stored as NUMERIC(4,2) to prevent rounding drift
-- in calibration comparisons (PRD §28.2).
CREATE TABLE IF NOT EXISTS writing_sessions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- Exam configuration at time of submission
    exam_type               VARCHAR(30) NOT NULL,   -- IELTS | TOEFL | DELF
    task_type               VARCHAR(30),             -- Task1 | Task2 | Independent | Integrated

    -- The submitted essay text
    essay_text              TEXT NOT NULL,
    word_count              INTEGER,

    -- Evaluation status — drives polling in GET /writing/result/:job_id
    -- Values: pending | processing | scored | failed
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- Rubric scores — NUMERIC(4,2) per PRD §28.2
    -- NULL until evaluation completes
    score_task_response     NUMERIC(4,2),
    score_coherence         NUMERIC(4,2),
    score_lexical           NUMERIC(4,2),
    score_grammar           NUMERIC(4,2),
    score_overall           NUMERIC(4,2),

    -- CEFR level assigned by the evaluation (B1, B2, C1, etc.)
    cefr_level              VARCHAR(5),

    -- Structured feedback as JSONB — grammar corrections, improvement tips
    feedback_json           JSONB,

    -- Calibration metadata shown on every score report (PRD §21.3)
    calibration_version     VARCHAR(50),
    calibration_correlation NUMERIC(4,3),

    -- FK to the AI inference record — mandatory per PRD §28.2
    -- "No evaluation result exists without a traceable AI execution record"
    ai_model_run_id         UUID,   -- FK added after ai_model_runs table

    -- Score appeal state (PRD §21.4)
    -- Values: none | pending | resolved | escalated
    appeal_status           VARCHAR(20) NOT NULL DEFAULT 'none',

    -- Soft delete
    deleted_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_writing_sessions_user_id
    ON writing_sessions (user_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_writing_sessions_status
    ON writing_sessions (status)
    WHERE status IN ('pending', 'processing');


-- Speaking session — one row per voice session.
-- Populated by Voice Service (Phase 2).
-- Schema defined now so FK references work and
-- Phase 2 can add data without schema changes (PRD §12.2).
CREATE TABLE IF NOT EXISTS speaking_sessions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    exam_type               VARCHAR(30),
    accent_target           VARCHAR(10) NOT NULL DEFAULT 'en-US',
    persona                 VARCHAR(20) NOT NULL DEFAULT 'companion',

    -- Duration in seconds
    duration_seconds        INTEGER,

    -- Pronunciation score 0.0–1.0 (PRD §20.4)
    pronunciation_score     NUMERIC(4,3),
    fluency_score           NUMERIC(4,3),
    grammar_score           NUMERIC(4,3),

    -- Socratic follow-up turns in this session
    socratic_turns          INTEGER NOT NULL DEFAULT 0,

    -- Weakness detected and acted on this session
    weakness_dimension      VARCHAR(30),

    -- S3 key for the audio recording blob
    -- NULL if user has not consented (PRD §10.5)
    audio_s3_key            VARCHAR(500),

    -- Full transcript and structured feedback
    transcript_text         TEXT,
    feedback_json           JSONB,

    ai_model_run_id         UUID,

    deleted_at              TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_speaking_sessions_user_id
    ON speaking_sessions (user_id, created_at DESC)
    WHERE deleted_at IS NULL;


-- =============================================================
-- DOMAIN 4: ADAPTIVE ENGINE
-- =============================================================

-- Daily Diagnostic Micro-Session — one per learner per day.
-- Pre-generated at 2AM UTC by the SRS scheduler and served from
-- Redis cache on user login. This is the retention engine of the
-- entire platform (PRD §15.2, §23.3).
CREATE TABLE IF NOT EXISTS daily_sessions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- The skill dimension this session targets — chosen by SRS priority
    target_dimension        VARCHAR(30) NOT NULL,

    -- Pre-generated content (lesson text, exercises, prompts)
    content_json            JSONB NOT NULL,

    -- Session date (UTC date, not datetime — one per day per user)
    session_date            DATE NOT NULL,

    -- Completion tracking
    completed               BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at            TIMESTAMPTZ,

    -- Score delta from this session — displayed as "+0.2 bands today"
    skill_delta             NUMERIC(5,4),

    ai_model_run_id         UUID,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One micro-session per learner per day
    UNIQUE (user_id, session_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_sessions_user_date
    ON daily_sessions (user_id, session_date DESC);


-- Score appeals — one per writing or speaking session that
-- the learner challenges. Secondary evaluation runs async
-- within 60 seconds (PRD §21.4, §42).
CREATE TABLE IF NOT EXISTS score_appeals (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- The session being appealed
    -- Exactly one of these will be non-NULL
    writing_session_id      UUID REFERENCES writing_sessions(id),
    speaking_session_id     UUID REFERENCES speaking_sessions(id),

    -- Appeal status (PRD §42)
    -- Values: pending | resolved | escalated | error
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- Original score before appeal
    original_score          NUMERIC(4,2) NOT NULL,

    -- Score from the secondary evaluation
    secondary_score         NUMERIC(4,2),

    -- Delta between original and secondary
    score_delta             NUMERIC(4,2),

    -- If delta > 0.5 bands, escalate to human review (PRD §42)
    escalated_to_human      BOOLEAN NOT NULL DEFAULT FALSE,

    -- The secondary AI run that produced the appeal result
    secondary_ai_model_run_id UUID,

    resolved_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One appeal per session — button permanently disabled after first (PRD §42)
    UNIQUE (writing_session_id),
    UNIQUE (speaking_session_id)
);

CREATE INDEX IF NOT EXISTS idx_score_appeals_user_id
    ON score_appeals (user_id, created_at DESC);


-- =============================================================
-- DOMAIN 5: EXAM & PROGRESS
-- =============================================================

-- Exam attempt — one row per mock exam session.
-- Lifecycle: INIT → IN_PROGRESS → SUBMITTED → RESULT (PRD §24.1)
CREATE TABLE IF NOT EXISTS exam_attempts (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    exam_type               VARCHAR(30) NOT NULL,   -- IELTS | TOEFL | DELF

    -- Exam lifecycle state (PRD §24.1)
    -- Values: init | in_progress | submitted | result
    status                  VARCHAR(30) NOT NULL DEFAULT 'init',

    -- Weighted overall score computed after all sections complete
    overall_score           NUMERIC(4,2),

    -- CEFR level assigned from the overall exam score
    cefr_level              VARCHAR(5),

    -- JSON snapshot of section-by-section results
    section_results_json    JSONB,

    -- S3 key for the generated PDF report (Pro tier, PRD §35.5)
    pdf_report_s3_key       VARCHAR(500),

    -- Score appeal state for the overall exam
    appeal_status           VARCHAR(20) NOT NULL DEFAULT 'none',

    -- Auto-save timestamp — writing sections save every 60s (PRD §41.4)
    last_autosave_at        TIMESTAMPTZ,

    deleted_at              TIMESTAMPTZ,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exam_attempts_user_id
    ON exam_attempts (user_id, created_at DESC)
    WHERE deleted_at IS NULL;


-- Individual exam sections within an attempt.
-- Writing and Speaking sections link back to their evaluation sessions.
CREATE TABLE IF NOT EXISTS exam_sections (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exam_attempt_id         UUID NOT NULL REFERENCES exam_attempts(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- Section type determines which evaluation pipeline handles it
    -- Values: writing_task1 | writing_task2 | speaking_part1 |
    --         speaking_part2 | speaking_part3
    section_type            VARCHAR(30) NOT NULL,

    -- Section lifecycle state
    -- Values: not_started | in_progress | submitted | scored
    status                  VARCHAR(30) NOT NULL DEFAULT 'not_started',

    -- The prompt/question for this section
    prompt_text             TEXT,

    -- Learner's answer
    response_text           TEXT,

    -- Section score (same type as evaluation scores)
    score                   NUMERIC(4,2),

    -- Links to the evaluation sessions that scored this section
    writing_session_id      UUID REFERENCES writing_sessions(id),
    speaking_session_id     UUID REFERENCES speaking_sessions(id),

    -- Time management
    time_limit_seconds      INTEGER,
    time_used_seconds       INTEGER,

    submitted_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exam_sections_attempt
    ON exam_sections (exam_attempt_id);


-- Readiness snapshots — one per session completion.
-- Time-series data that powers the readiness trend chart
-- and daily delta display (PRD §25.2, §17.2 new entities list)
CREATE TABLE IF NOT EXISTS readiness_snapshots (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- The computed readiness index (0.0–1.0)
    -- Formula: weighted_skill_average × trend_factor × stability_factor
    readiness_index         NUMERIC(5,4) NOT NULL,

    -- Projected exam band and confidence interval
    projected_band          NUMERIC(4,2),
    confidence_interval     NUMERIC(4,2),   -- ± value, e.g. 0.50 means ±0.5 bands

    -- Delta from the previous snapshot — "You improved +0.2 bands today"
    delta_from_previous     NUMERIC(5,4),

    -- Snapshot of the skill vector at this moment (for charting)
    skill_vector_snapshot   JSONB NOT NULL,

    -- What triggered this recomputation
    -- Values: session_complete | daily_diagnostic | appeal_resolved
    trigger_event           VARCHAR(50),

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Time-series index for fast trend queries (dashboard charting)
CREATE INDEX IF NOT EXISTS idx_readiness_snapshots_user_time
    ON readiness_snapshots (user_id, created_at DESC);


-- Share events — tracks every "Share Your Score" card generation.
-- Used for viral attribution analytics (PRD §18.3, §5.4).
CREATE TABLE IF NOT EXISTS share_events (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    exam_attempt_id         UUID REFERENCES exam_attempts(id),

    -- Score at time of sharing
    band_score              NUMERIC(4,2) NOT NULL,

    -- Improvement since learner's first attempt (the emotional hook)
    improvement_delta       NUMERIC(4,2),

    -- Which platform the share was generated for
    -- Values: whatsapp | linkedin | twitter | copy_link | instagram
    platform                VARCHAR(30) NOT NULL,

    -- Whether the share actually resulted in a tracked new signup
    converted_signup        BOOLEAN NOT NULL DEFAULT FALSE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_share_events_user_id
    ON share_events (user_id, created_at DESC);


-- =============================================================
-- DOMAIN 6: AI INFRASTRUCTURE
-- =============================================================

-- AI inference audit log — one row per LLM/ASR/TTS call.
-- Non-negotiable: no evaluation result exists without this record.
-- Stores complete traceability metadata for drift detection,
-- cost analysis, and model version audits (PRD §11.5, §28.2).
--
-- Written to a dedicated partition (or separate table in large scale)
-- per PRD §52 — "AIModelRun data written to dedicated PostgreSQL
-- partition, separate from user-facing tables."
CREATE TABLE IF NOT EXISTS ai_model_runs (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- All required fields per PRD §11.5
    model_name              VARCHAR(100) NOT NULL,   -- e.g. 'gpt-4o', 'llama-3.3-70b'
    model_version           VARCHAR(100),            -- provider's version string
    task_type               VARCHAR(50) NOT NULL,    -- 'writing_score' | 'grammar_correction' | 'cefr_classify' | etc.

    -- Prompt fingerprint — SHA-256 of the full assembled prompt.
    -- Enables detection of identical prompts served from cache.
    prompt_hash             VARCHAR(64) NOT NULL,

    -- Token usage — drives cost analytics and per-user ceiling enforcement
    input_token_count       INTEGER,
    output_token_count      INTEGER,

    -- Latency tracking (PRD §9.1 — first token < 500ms target)
    latency_ms              INTEGER,
    streaming_first_token_ms INTEGER,

    -- SHA-256 of the AI response — detects response anomalies
    -- and enables de-duplication of identical outputs (PRD §37)
    response_hash           VARCHAR(64),

    -- Anonymized user reference — no email or PII stored here (PRD §28.2)
    -- This is deliberately not a FK — anonymized records must survive
    -- GDPR user deletion without cascade-deleting the audit trail
    user_reference_id       UUID,

    -- Calibration version active at time of this call
    -- Referenced on every score report shown to learners
    calibration_version     VARCHAR(50),

    -- Teaching persona active at time of this call
    -- Values: companion | coach | examiner | null (non-conversational calls)
    persona_config          VARCHAR(20),

    -- Which provider was actually used (after failover logic)
    provider_name           VARCHAR(50),   -- 'openai' | 'anthropic' | 'groq' | 'gemini'

    -- Whether this was served from cache or was a fresh inference call
    served_from_cache       BOOLEAN NOT NULL DEFAULT FALSE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on task_type and created_at for latency trend dashboards
CREATE INDEX IF NOT EXISTS idx_ai_model_runs_task_time
    ON ai_model_runs (task_type, created_at DESC);

-- Index for per-user cost analytics (using user_reference_id)
CREATE INDEX IF NOT EXISTS idx_ai_model_runs_user_ref
    ON ai_model_runs (user_reference_id, created_at DESC);


-- =============================================================
-- FK BACK-REFERENCES (added after both tables exist)
-- =============================================================
-- These FKs couldn't be declared inline because the target table
-- didn't exist at declaration time.

ALTER TABLE writing_sessions
    ADD CONSTRAINT fk_writing_ai_run
    FOREIGN KEY (ai_model_run_id) REFERENCES ai_model_runs(id)
    ON DELETE SET NULL;

ALTER TABLE speaking_sessions
    ADD CONSTRAINT fk_speaking_ai_run
    FOREIGN KEY (ai_model_run_id) REFERENCES ai_model_runs(id)
    ON DELETE SET NULL;

ALTER TABLE daily_sessions
    ADD CONSTRAINT fk_daily_ai_run
    FOREIGN KEY (ai_model_run_id) REFERENCES ai_model_runs(id)
    ON DELETE SET NULL;

ALTER TABLE score_appeals
    ADD CONSTRAINT fk_appeal_secondary_ai_run
    FOREIGN KEY (secondary_ai_model_run_id) REFERENCES ai_model_runs(id)
    ON DELETE SET NULL;


-- =============================================================
-- VERIFICATION
-- =============================================================
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(tablename)))
        AS total_size
FROM pg_tables
WHERE schemaname = 'linguamentor'
ORDER BY tablename;


-- writing_sessions: calibration_sample_count shown in API response (PRD §35.4 p.74)
ALTER TABLE writing_sessions
    ADD COLUMN IF NOT EXISTS calibration_sample_count INTEGER;

-- learner_profiles: timestamp of when placement test was completed (PRD §35.2 p.74)
-- We keep placement_completed BOOLEAN for fast filtering, add timestamp for display
ALTER TABLE learner_profiles
    ADD COLUMN IF NOT EXISTS placement_completed_at TIMESTAMPTZ;

-- daily_sessions: store the SRS priority score that selected this dimension (PRD §35.3 p.75)
ALTER TABLE daily_sessions
    ADD COLUMN IF NOT EXISTS srs_priority_score NUMERIC(5,4);

-- share_events: rename improvement_delta to delta to match PRD §18.3 spec exactly
-- (PRD: "band_score, delta, shared_at, platform")
ALTER TABLE share_events
    RENAME COLUMN improvement_delta TO delta;

-- ai_model_runs: calibration_sample_count used in transparency display
ALTER TABLE ai_model_runs
    ADD COLUMN IF NOT EXISTS calibration_sample_count INTEGER;
