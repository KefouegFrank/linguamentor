"""
app/routers/wer_validation.py

HTTP endpoints for the WER validation pipeline.

Admin-only endpoints for triggering and monitoring ASR validation runs.
Never exposed to learners. In production these sit behind admin RBAC
at the API Gateway layer.
"""

import logging
import uuid as uuid_module
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.calibration.wer_engine import (
    compute_wer,
    compute_run_wer,
    normalise_text,
    store_wer_baseline,
    WER_THRESHOLD,
)
from app.calibration.asr_pipeline import run_asr_pipeline
from app.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wer", tags=["wer-validation"])


class CreateRunRequest(BaseModel):
    run_label:      str
    asr_model:      str = "gpt-4o-transcribe"
    accent_targets: list[str] = ["en-US", "en-GB", "fr-FR", "fr-CA"]
    notes:          str = ""


class TranscriptionSubmitRequest(BaseModel):
    """Submit ASR hypothesis for a single audio sample."""
    sample_id:       str
    hypothesis_text: str
    confidence:      float = None
    latency_ms:      int   = None


class BaselineRequest(BaseModel):
    approved_by:         str
    validation_version:  str = "v1.0-launch"


@router.post(
    "/runs",
    summary="Create a new WER validation run",
)
async def create_wer_run(
    request: CreateRunRequest,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """
    Creates a WER validation run record.
    Transcription results are submitted per-clip via POST /wer/runs/{id}/results.
    """
    run_id = str(uuid_module.uuid4())

    await conn.execute(
        """
        INSERT INTO linguamentor.wer_validation_runs (
            id, run_label, asr_model, accent_targets, notes, started_at
        ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
        uuid_module.UUID(run_id),
        request.run_label,
        request.asr_model,
        request.accent_targets,
        request.notes,
        datetime.now(timezone.utc),
    )

    # Count available clips for this run
    clips_available = await conn.fetchval(
        """
        SELECT COUNT(*) FROM linguamentor.wer_audio_samples
        WHERE accent_target = ANY($1)
        """,
        request.accent_targets,
    )

    logger.info(f"WER run created: {run_id} | {clips_available} clips available")

    return {
        "run_id":           run_id,
        "asr_model":        request.asr_model,
        "accent_targets":   request.accent_targets,
        "clips_available":  clips_available,
        "status":           "created",
        "next_step": (
            f"Submit transcription results via "
            f"POST /wer/runs/{run_id}/results for each clip"
        ),
    }

    
@router.post(
    "/runs/{run_id}/transcribe",
    summary="Run ASR pipeline — transcribe all pending audio samples",
)
async def run_transcription_pipeline(
    run_id: str,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """
    Transcribes all pending audio samples for this run using
    Groq Whisper Large v3. Call after creating a run and before
    calling /compute to get WER results.
    """
    # Fetch accent targets for this run
    run = await conn.fetchrow(
        "SELECT accent_targets FROM linguamentor.wer_validation_runs WHERE id = $1",
        uuid_module.UUID(run_id),
    )
    if not run:
        return {"error": f"Run {run_id} not found"}

    summary = await run_asr_pipeline(
        conn=conn,
        run_id=run_id,
        accent_targets=list(run["accent_targets"]),
    )
    return summary

@router.post(
    "/runs/{run_id}/results",
    summary="Submit ASR hypothesis for one audio clip",
)
async def submit_transcription_result(
    run_id: str,
    request: TranscriptionSubmitRequest,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """
    Submits the ASR hypothesis for one audio sample.
    WER is computed immediately against the stored reference transcript.
    """
    # Fetch reference transcript
    sample = await conn.fetchrow(
        """
        SELECT reference_text, accent_target, word_count
        FROM linguamentor.wer_audio_samples
        WHERE id = $1
        """,
        uuid_module.UUID(request.sample_id),
    )

    if not sample:
        return {"error": f"Sample {request.sample_id} not found"}

    # Compute WER immediately
    result = compute_wer(sample["reference_text"], request.hypothesis_text)

    # Store result
    await conn.execute(
        """
        INSERT INTO linguamentor.wer_transcription_results (
            id, run_id, sample_id,
            hypothesis_text, wer,
            substitutions, insertions, deletions,
            confidence, latency_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        uuid_module.uuid4(),
        uuid_module.UUID(run_id),
        uuid_module.UUID(request.sample_id),
        request.hypothesis_text,
        result.wer,
        result.substitutions,
        result.insertions,
        result.deletions,
        request.confidence,
        request.latency_ms,
    )

    # Update clips_scored counter
    await conn.execute(
        """
        UPDATE linguamentor.wer_validation_runs
        SET clips_scored = clips_scored + 1
        WHERE id = $1
        """,
        uuid_module.UUID(run_id),
    )

    return {
        "sample_id":    request.sample_id,
        "accent":       sample["accent_target"],
        "wer":          result.wer,
        "wer_pct":      f"{result.wer:.1%}",
        "passed":       result.wer < WER_THRESHOLD,
        "errors": {
            "substitutions": result.substitutions,
            "insertions":    result.insertions,
            "deletions":     result.deletions,
        },
    }


@router.post(
    "/runs/{run_id}/compute",
    summary="Compute aggregated WER for completed run",
)
async def compute_run_wer_endpoint(
    run_id: str,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """
    Computes mean WER per accent target and checks against threshold.
    Call after all clip results have been submitted.
    """
    report = await compute_run_wer(conn, run_id)

    return {
        "run_id":       run_id,
        "asr_model":    report.asr_model,
        "passed":       report.passed_overall,
        "verdict":      report.verdict,
        "accents": [
            {
                "accent_target": a.accent_target,
                "wer_mean":      a.wer_mean,
                "wer_pct":       f"{a.wer_mean:.1%}",
                "wer_min":       a.wer_min,
                "wer_max":       a.wer_max,
                "clip_count":    a.clip_count,
                "passed":        a.passed,
                "worst_clips":   a.worst_clips[:3],
            }
            for a in report.accents
        ],
    }


@router.post(
    "/runs/{run_id}/baseline",
    summary="Store approved WER baseline — Go/No-Go sign-off",
)
async def store_wer_baseline_endpoint(
    run_id: str,
    request: BaselineRequest,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """
    Records the immutable WER baseline after Go/No-Go approval.
    Only callable when all accent targets have passed threshold.
    """
    run = await conn.fetchrow(
        "SELECT passed_threshold FROM linguamentor.wer_validation_runs WHERE id = $1",
        uuid_module.UUID(run_id),
    )

    if not run:
        return {"error": f"Run {run_id} not found"}

    if not run["passed_threshold"]:
        return {
            "error": "WER threshold not passed — cannot store baseline",
            "required": f"WER < {WER_THRESHOLD:.0%} for all accent targets",
        }

    report = await compute_run_wer(conn, run_id)
    version = await store_wer_baseline(
        conn=conn,
        run_id=run_id,
        report=report,
        approved_by=request.approved_by,
        validation_version=request.validation_version,
    )

    return {
        "validation_version": version,
        "approved_by":        request.approved_by,
        "status":             "WER baseline stored — Go/No-Go complete",
    }


@router.get(
    "/compute-wer",
    summary="Compute WER for a single reference/hypothesis pair",
)
async def compute_single_wer(
    reference:  str,
    hypothesis: str,
) -> dict:
    """
    Utility endpoint — computes WER for any reference/hypothesis pair.
    Useful for testing normalisation and WER computation during development.
    """
    result = compute_wer(reference, hypothesis)
    return {
        "reference_normalised":  normalise_text(reference),
        "hypothesis_normalised": normalise_text(hypothesis),
        "wer":          result.wer,
        "wer_pct":      f"{result.wer:.1%}",
        "passed":       result.wer < WER_THRESHOLD,
        "ref_words":    result.ref_word_count,
        "substitutions": result.substitutions,
        "insertions":    result.insertions,
        "deletions":     result.deletions,
    }
