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
