# Phase 0 — Go/No-Go Gate Report

**Product:** LinguaMentor — AI-Orchestrated Language Proficiency Evaluation  
**Phase:** Phase 0 — Evaluation Calibration  
**Report Date:** 2026-03-15  
**Prepared by:** TETSOPGUIM Kefoueg Frank P.  
**Status:** ✅ CONDITIONALLY APPROVED — conditions documented below

---

## Executive Summary

Phase 0 validates two non-negotiable technical claims before any
user-facing AI evaluation feature ships:

1. **Writing Evaluation Accuracy** — AI essay scores must achieve
   Pearson correlation ≥ 0.85 against certified human examiner scores
   across all four IELTS rubric categories.

2. **Speech Recognition Accuracy** — ASR transcription must achieve
   Word Error Rate < 10% across all four accent targets: en-US, en-GB,
   fr-FR, fr-CA.

Both gates have been tested. Writing evaluation passed on the first
calibration run. WER validation passed on synthetic audio. One
condition remains open before full production sign-off.

---

## Gate 1 — Writing Evaluation Accuracy

### Requirement
Pearson correlation ≥ 0.85 between AI scores and human examiner
consensus across all five metrics: Task Response, Coherence & Cohesion,
Lexical Resource, Grammatical Range, Overall Band.

### Result: ✅ PASSED

| Category | Pearson r | Threshold | Status |
|---|---|---|---|
| Task Response | 0.8921 | ≥ 0.85 | ✅ PASS |
| Coherence & Cohesion | 0.9218 | ≥ 0.85 | ✅ PASS |
| Lexical Resource | 0.9366 | ≥ 0.85 | ✅ PASS |
| Grammatical Range | 0.9319 | ≥ 0.85 | ✅ PASS |
| Overall Band | 0.9338 | ≥ 0.85 | ✅ PASS |

**Calibration details:**
- Essays scored: 24 of 29 (5 Band 8.5 essays pending Groq TPD reset)
- Band range covered: 4.5 — 8.0
- AI provider: Groq LLaMA 3.3 70B (via `GroqProvider`)
- Production provider: OpenAI GPT-4o (per PRD section 19.3)
- Calibration version: `v1.0-launch`
- Baseline stored: ✅ `calibration_baseline` table, `approved_by=TETSOPGUIM Frank`

**Context on result quality:**
The achieved r=0.9338 overall exceeds published human inter-rater
reliability for IELTS (r=0.90-0.92), meaning the AI agrees with
human scores more consistently than two human examiners agree with
each other. This is a strong result by any benchmark.

**Known issue — systematic positive bias:**
Analysis revealed the AI scores 1.0-1.4 bands above human consensus
across all categories (MAE=1.177). The Pearson gate passed because
correlation measures directional agreement, not absolute accuracy.
A MAE gate (threshold ≤ 0.50) has been added to the correlation
engine. Prompt variant `v1.1-bias-correction` has been registered
with a Layer 4 anti-inflation correction. A new calibration run
is required to verify the bias is resolved before production scoring.

**Open condition C1:**
Run calibration with `v1.1-bias-correction` prompt variant.
Verify: Pearson ≥ 0.85 AND MAE ≤ 0.50 across all categories.
Store new baseline as `v1.1-launch`. Required before Phase 1
writing evaluation feature ships to users.

---

## Gate 2 — Speech Recognition Accuracy

### Requirement
Word Error Rate < 10% across all four accent targets using
Whisper-class ASR model.

### Result: ✅ PASSED (synthetic audio)

| Accent | WER | Threshold | Status |
|---|---|---|---|
| en-US | 0.00% | < 10% | ✅ PASS |
| en-GB | 3.40% | < 10% | ✅ PASS |
| fr-FR | 0.00% | < 10% | ✅ PASS |
| fr-CA | 1.05% | < 10% | ✅ PASS |

**Validation details:**
- Audio clips: 40 total (10 per accent target)
- Audio type: Synthetic TTS via gTTS — pipeline validation only
- ASR model: Groq Whisper Large v3
- Production ASR: gpt-4o-transcribe (per PRD section 19.3)
- Validation version: `v1.0-synthetic`
- Baseline stored: ✅ `wer_baseline` table

**Notable findings:**
- en-GB worst clip WER=27.78%: Whisper split "healthcare" → "health care"
  and "establishment" was truncated. Compound word splitting is a known
  Whisper behaviour — addressable with post-processing normalisation.
- fr-CA worst clip WER=10.53%: Morphological agreement dropped —
  "garderies subventionnées" → "garderie subventionné". French plural
  suffixes are phonetically silent — will worsen with real accented speech.

**Open condition C2:**
Replace synthetic TTS audio with real accent-specific speech recordings
(LibriSpeech for English, Mozilla Common Voice for French).
Re-run WER validation pipeline. Store new baseline as `v1.0-launch`.
Required before Phase 2 Voice Service ships to users.

---

## Infrastructure Delivered

All Phase 0 infrastructure is production-ready and committed to
the `develop` branch:

| Component | Status | Location |
|---|---|---|
| Calibration DB schema | ✅ | `scripts/migrations/001_calibration_schema.sql` |
| WER validation DB schema | ✅ | `scripts/migrations/002_wer_validation_schema.sql` |
| AI scoring pipeline | ✅ | `app/calibration/pipeline.py` |
| 8-layer prompt builder | ✅ | `app/calibration/prompt_builder.py` |
| AI provider abstraction | ✅ | `app/calibration/ai_provider.py` |
| Pearson correlation engine | ✅ | `app/calibration/correlation.py` |
| MAE gate | ✅ | `app/calibration/correlation.py` |
| Prompt version registry | ✅ | `app/calibration/prompt_registry.py` |
| Tuning analysis engine | ✅ | `app/calibration/tuning_analysis.py` |
| WER computation engine | ✅ | `app/calibration/wer_engine.py` |
| ASR pipeline | ✅ | `app/calibration/asr_pipeline.py` |
| Calibration HTTP endpoints | ✅ | `app/routers/calibration.py` |
| WER HTTP endpoints | ✅ | `app/routers/wer_validation.py` |
| ADR-001: Secrets management | ✅ | `docs/adr/001-secrets-management.md` |
| ADR-002: PYTHONPATH | ✅ | `docs/adr/002-pythonpath-shared-modules.md` |
| ADR-003: Rubric tuning protocol | ✅ | `docs/adr/003-calibration-rubric-tuning-protocol.md` |

---

## Conditions for Full Production Sign-Off

Two conditions must be resolved before any AI evaluation result
is shown to a real user. Neither blocks Phase 1 infrastructure
work — they block only the user-facing evaluation features.

### Condition C1 — Writing Bias Resolution (blocks Phase 1 evaluation feature)

**Action:** Run calibration with `v1.1-bias-correction` prompt variant  
**Owner:** TETSOPGUIM Frank  
**Trigger:** Groq TPD resets (midnight UTC daily — 100k tokens/day)  
**Success criteria:** Pearson ≥ 0.85 AND MAE ≤ 0.50 across all categories  
**Fallback:** If MAE still > 0.50 after v1.1 run, apply Layer 5 per-category
rubric tightening per ADR-003 tuning protocol (max 2 more iterations)

### Condition C2 — Real Audio WER Validation (blocks Phase 2 voice feature)

**Action:** Replace synthetic TTS with real accent recordings  
**Sources:** LibriSpeech (en-US, en-GB), Mozilla Common Voice (fr-FR, fr-CA)  
**Owner:** TETSOPGUIM Frank  
**Success criteria:** WER < 10% across all four accent targets  
**Timeline:** Before Phase 2 Voice Service development begins

---

## Decision

Phase 0 is **conditionally approved** to proceed to Phase 1.

Phase 1 infrastructure work (authentication, database schema, API
Gateway, frontend scaffold) may begin immediately — none of it
depends on the open conditions above.

Phase 1 writing evaluation endpoint may not serve real user scores
until Condition C1 is resolved and a new baseline is stored.

Phase 2 voice evaluation may not serve real user transcriptions
until Condition C2 is resolved and a new baseline is stored.

**Signed:** TETSOPGUIM Kefoueg Frank P.  
**Date:** 2026-03-15  
**Role:** Product Owner + Engineering Lead
