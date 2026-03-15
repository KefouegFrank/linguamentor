-- =================================================================
-- Migration 002 — WER Validation Schema
-- =================================================================
-- Phase 0 ASR validation tables. Parallel to the writing calibration
-- schema but for voice: reference audio clips → ASR transcription →
-- WER computation → threshold gate.
--
-- Target: WER < 0.10 (10%) across all four accent targets.
-- PRD Section 60: "ASR must achieve < 10% WER across en-US, en-GB,
-- fr-FR, fr-CA before any voice evaluation feature ships."
--
-- Run with:
--   docker cp scripts/migrations/002_wer_validation_schema.sql lm_postgres:/tmp/002.sql
--   docker exec lm_postgres psql -U lm_user -d linguamentor -f /tmp/002.sql
-- =================================================================

SET search_path TO linguamentor, public;

-- -----------------------------------------------------------------
-- wer_audio_samples
-- -----------------------------------------------------------------
-- Reference audio clips used for WER validation.
-- Each clip has a known reference transcript produced by a human
-- transcriber. The ASR system transcribes the audio and we compare
-- the hypothesis to this reference.
--
-- Audio files are stored externally (S3/local filesystem) — we store
-- only the path/URI here, not the binary data.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wer_audio_samples (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Accent target — matches PRD section 60 exactly.
    -- Four targets required before Go/No-Go.
    accent_target   VARCHAR(10) NOT NULL
                    CHECK (accent_target IN ('en-US', 'en-GB', 'fr-FR', 'fr-CA')),

    -- Path to audio file — relative to the ASR validation audio root.
    -- Format: {accent_target}/{sample_id}.wav
    -- e.g. en-US/sample_001.wav
    audio_path      VARCHAR(500) NOT NULL,

    -- Human-produced reference transcript.
    -- Normalised: lowercase, no punctuation (per WER computation standard).
    -- This is what ASR output is compared against.
    reference_text  TEXT NOT NULL,

    -- Duration in seconds — used to filter very short clips
    -- that produce unreliable WER measurements.
    duration_seconds NUMERIC(6, 2),

    -- Audio quality metadata — sample rate, channel count.
    -- Minimum acceptable: 16kHz mono (Whisper requirement).
    sample_rate_hz  INTEGER,
    channels        INTEGER DEFAULT 1,

    -- Source of this clip — important for audit and licensing.
    source          VARCHAR(100) NOT NULL,

    -- Word count of reference — needed to normalise WER per clip.
    word_count      INTEGER NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wer_samples_accent
    ON wer_audio_samples (accent_target);


-- -----------------------------------------------------------------
-- wer_validation_runs
-- -----------------------------------------------------------------
-- One row per complete WER validation run.
-- A run scores all clips for one or more accent targets.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wer_validation_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_label       VARCHAR(100) NOT NULL,

    -- ASR model used in this run — critical for audit trail.
    -- e.g. 'gpt-4o-transcribe', 'whisper-large-v3'
    asr_model       VARCHAR(100) NOT NULL,

    -- Accent targets covered in this run.
    -- Stored as array — a run can cover all four at once.
    accent_targets  VARCHAR(10)[] NOT NULL,

    -- Clips scored in this run
    clips_scored    INTEGER NOT NULL DEFAULT 0,
    clips_failed    INTEGER NOT NULL DEFAULT 0,

    -- WER results per accent target — NULL until run completes
    wer_en_us       NUMERIC(5, 4),
    wer_en_gb       NUMERIC(5, 4),
    wer_fr_fr       NUMERIC(5, 4),
    wer_fr_ca       NUMERIC(5, 4),

    -- TRUE only when ALL tested accent targets achieve WER < 0.10
    passed_threshold BOOLEAN NOT NULL DEFAULT FALSE,

    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_wer_runs_passed
    ON wer_validation_runs (passed_threshold)
    WHERE passed_threshold = TRUE;


-- -----------------------------------------------------------------
-- wer_transcription_results
-- -----------------------------------------------------------------
-- One row per audio clip per validation run.
-- Stores both the ASR hypothesis and the computed WER for that clip.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wer_transcription_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id          UUID NOT NULL REFERENCES wer_validation_runs(id)
                    ON DELETE CASCADE,
    sample_id       UUID NOT NULL REFERENCES wer_audio_samples(id)
                    ON DELETE CASCADE,

    -- What the ASR system produced
    hypothesis_text TEXT NOT NULL,

    -- WER for this specific clip
    -- WER = (S + I + D) / N where N = words in reference
    wer             NUMERIC(5, 4) NOT NULL,

    -- Error breakdown — useful for diagnosing failure patterns
    substitutions   INTEGER NOT NULL DEFAULT 0,
    insertions      INTEGER NOT NULL DEFAULT 0,
    deletions       INTEGER NOT NULL DEFAULT 0,

    -- ASR confidence score if available from the model
    confidence      NUMERIC(4, 3),

    -- Latency of ASR call in milliseconds
    latency_ms      INTEGER,

    transcribed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wer_results_run_id
    ON wer_transcription_results (run_id);

CREATE INDEX IF NOT EXISTS idx_wer_results_sample_id
    ON wer_transcription_results (sample_id);


-- -----------------------------------------------------------------
-- wer_baseline
-- -----------------------------------------------------------------
-- Immutable record of approved WER validation results.
-- Written once when all accent targets pass < 10% threshold.
-- Referenced by every Voice evaluation in production.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wer_baseline (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    validation_version  VARCHAR(50) NOT NULL UNIQUE,
    run_id              UUID NOT NULL REFERENCES wer_validation_runs(id),

    -- Final approved WER per accent target
    wer_en_us           NUMERIC(5, 4) NOT NULL,
    wer_en_gb           NUMERIC(5, 4) NOT NULL,
    wer_fr_fr           NUMERIC(5, 4) NOT NULL,
    wer_fr_ca           NUMERIC(5, 4) NOT NULL,

    -- Total clips in the approved run
    clips_count         INTEGER NOT NULL,

    -- ASR model that produced these results
    asr_model           VARCHAR(100) NOT NULL,

    approved_by         VARCHAR(100) NOT NULL,
    approved_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Verification
SELECT table_name,
       pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS size
FROM information_schema.tables
WHERE table_schema = 'linguamentor'
  AND table_name LIKE 'wer_%'
ORDER BY table_name;
