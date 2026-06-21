"""
HTTP endpoints for triggering and monitoring calibration runs.

These endpoints are admin-only — never exposed to learners.
In production they sit behind an admin RBAC check at the API Gateway.
During Phase 0 we call them directly for simplicity.
"""

import logging
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import asyncpg

from app.calibration.schemas import ExamType
from app.calibration.pipeline import (
    create_calibration_run,
    run_calibration_scoring,
)
from app.calibration.correlation import (
    compute_correlation,
    store_calibration_baseline,
    PEARSON_THRESHOLD,
)

from app.calibration.tuning_analysis import analyse_run

from app.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calibration", tags=["calibration"])


class StartRunRequest(BaseModel):
    """Request body for starting a new calibration run."""
    exam_type:  ExamType
    run_label:  str
    notes:      str = ""


class StartRunResponse(BaseModel):
    """Returned immediately when a run is created."""
    run_id:     str
    exam_type:  str
    run_label:  str
    status:     str

class CorrelationResultResponse(BaseModel):
    """Returned after correlation computation completes."""
    run_id:                     str
    pearson_task_response:      float
    pearson_coherence_cohesion: float
    pearson_lexical_resource:   float
    pearson_grammatical_range:  float
    pearson_overall:            float
    passed_threshold:           bool
    verdict:                    str


class BaselineRequest(BaseModel):
    """Request body for storing the approved calibration baseline."""
    approved_by: str

@router.post(
    "/runs",
    response_model=StartRunResponse,
    summary="Start a calibration scoring run",
)
async def start_calibration_run(
    request: StartRunRequest,
    conn: asyncpg.Connection = Depends(get_db),
) -> StartRunResponse:
    """
    Creates a calibration run record and triggers the AI scoring pipeline.

    This is a synchronous endpoint for Phase 0 — it runs the full
    pipeline in the request and returns when complete. In a future
    iteration this would be moved to a background BullMQ job.
    """
    run_id = await create_calibration_run(
        conn=conn,
        exam_type=request.exam_type,
        run_label=request.run_label,
        notes=request.notes,
    )

    # Run the scoring pipeline — scores all pending essays for this exam type
    summary = await run_calibration_scoring(
        conn=conn,
        run_id=run_id,
        exam_type=request.exam_type,
    )

    logger.info(f"Calibration run complete: {summary}")

    return StartRunResponse(
        run_id=run_id,
        exam_type=request.exam_type.value,
        run_label=request.run_label,
        status="complete",
    )


@router.get(
    "/runs/{run_id}",
    summary="Get calibration run status",
)
async def get_run_status(
    run_id: str,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """Returns current status and progress of a calibration run."""
    row = await conn.fetchrow(
        """
        SELECT
            id::text,
            run_label,
            exam_type,
            essays_scored,
            passed_threshold,
            pearson_overall,
            started_at,
            completed_at
        FROM linguamentor.calibration_runs
        WHERE id = $1::uuid
        """,
        run_id,
    )

    if not row:
        return {"error": f"Run {run_id} not found"}

    return dict(row)

@router.post(
    "/runs/{run_id}/correlate",
    response_model=CorrelationResultResponse,
    summary="Compute Pearson correlation for a completed run",
)
async def run_correlation(
    run_id: str,
    conn: asyncpg.Connection = Depends(get_db),
) -> CorrelationResultResponse:
    """
    Computes Pearson correlation between AI and human scores for this run.
    Requires the AI scoring pipeline to have completed first.
    Results are written to calibration_runs and returned here.
    """
    report = await compute_correlation(conn, run_id)

    return CorrelationResultResponse(
        run_id=run_id,
        pearson_task_response=report.task_response.pearson_r,
        pearson_coherence_cohesion=report.coherence_cohesion.pearson_r,
        pearson_lexical_resource=report.lexical_resource.pearson_r,
        pearson_grammatical_range=report.grammatical_range.pearson_r,
        pearson_overall=report.overall_score.pearson_r,
        passed_threshold=report.passed_overall,
        verdict=(
            "PASSED — Ready for Go/No-Go review"
            if report.passed_overall
            else "FAILED — Rubric tuning required"
        ),
    )


@router.post(
    "/runs/{run_id}/baseline",
    summary="Store approved calibration baseline (Go/No-Go sign-off)",
)
async def store_baseline(
    run_id: str,
    request: BaselineRequest,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """
    Records the immutable calibration baseline after Go/No-Go approval.
    Only callable when correlation has passed threshold.
    The calibration_version 'v1.0-launch' stored here appears on
    every user score report in production.
    """
    # Verify correlation was actually computed and passed
    run = await conn.fetchrow(
        """
        SELECT passed_threshold, pearson_overall
        FROM linguamentor.calibration_runs
        WHERE id = $1::uuid
        """,
        run_id,
    )

    if not run:
        return {"error": f"Run {run_id} not found"}

    if not run["passed_threshold"]:
        return {
            "error": "Correlation has not passed threshold",
            "pearson_overall": float(run["pearson_overall"] or 0),
            "required": PEARSON_THRESHOLD,
        }

    # Re-fetch the full report to pass to store_calibration_baseline
    report = await compute_correlation(conn, run_id)
    version = await store_calibration_baseline(
        conn=conn,
        run_id=run_id,
        report=report,
        approved_by=request.approved_by,
    )

    return {
        "calibration_version": version,
        "approved_by": request.approved_by,
        "status": "baseline stored — Go/No-Go complete",
    }

@router.get(
    "/runs/{run_id}/analysis",
    summary="Diagnose a calibration run — identify tuning targets",
)
async def get_tuning_analysis(
    run_id: str,
    conn: asyncpg.Connection = Depends(get_db),
) -> dict:
    """
    Produces a diagnostic report for a calibration run.

    Use this after any run — passing or failing — to understand
    where AI-human divergence is highest and what to adjust.
    Especially useful when a run fails the 0.85 threshold.
    """
    report = await analyse_run(conn, run_id)

    return {
        "run_id": report.run_id,
        "primary_issue": report.primary_issue,
        "recommended_layer": report.recommended_layer,
        "recommended_action": report.recommended_action,
        "categories": [
            {
                "category":             c.category,
                "pearson_r":            c.pearson_r,
                "mean_ai_score":        c.mean_ai_score,
                "mean_human_score":     c.mean_human_score,
                "mean_absolute_error":  c.mean_absolute_error,
                "bias":                 c.bias,
                "passed":               c.passed,
                "tuning_guidance":      c.tuning_guidance,
                "outlier_count":        len(c.outlier_essays),
            }
            for c in report.categories
        ],
    }
