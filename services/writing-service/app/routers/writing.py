# Writing evaluation endpoints — PRD §35.4
#
# POST /api/v1/writing/evaluate
#   Accepts essay submission, enqueues async eval job.
#   Returns 202 Accepted with job_id for polling.
#   Free tier: 3 evals/month. Pro tier: unlimited.
#
# GET  /api/v1/writing/result/{job_id}
#   Polls evaluation status.
#   Returns scores and feedback when status=scored.
#
# POST /api/v1/writing/appeal/{session_id}
#   Triggers secondary evaluation (Pro only — PRD §42).
#   Implemented as W9.

import logging
import uuid as uuid_module
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.dependencies import (
    get_current_user,
    get_db,
    get_queue_registry,
)
from app.exceptions import ValidationError, NotFoundError
from app.queue.queues import QueueRegistry, WRITING_EVAL_JOB_OPTIONS
from app.writing.cefr import band_to_cefr

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/writing", tags=["writing"])

# ── Free tier monthly limit (PRD §5.1) ────────────────────────────────────────
FREE_TIER_MONTHLY_LIMIT = 3

# ── Minimum word counts per exam type (PRD §35.4) ─────────────────────────────
MIN_WORD_COUNTS = {
    "ielts_academic":  150,
    "ielts_general":   150,
    "toefl_ibt":       100,
    "delf_b1":          80,
    "delf_b2":          80,
}

VALID_EXAM_TYPES = set(MIN_WORD_COUNTS.keys())


# ── Request / Response schemas ─────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    exam_type:  str   = Field(..., description="ielts_academic | ielts_general | toefl_ibt | delf_b1 | delf_b2")
    task_type:  str | None = Field(None, description="Task1 | Task2 | Independent | Integrated")
    essay_text: str   = Field(..., min_length=50, max_length=8000)

    @field_validator("exam_type")
    @classmethod
    def validate_exam_type(cls, v: str) -> str:
        if v.lower() not in VALID_EXAM_TYPES:
            raise ValueError(f"exam_type must be one of: {', '.join(sorted(VALID_EXAM_TYPES))}")
        return v.lower()

    @field_validator("essay_text")
    @classmethod
    def strip_essay(cls, v: str) -> str:
        return v.strip()


class EvaluateResponse(BaseModel):
    job_id:      str
    session_id:  str
    status:      str   = "pending"
    polling_url: str
    message:     str   = "Essay submitted for evaluation. Poll the polling_url for results."


class EvaluationResult(BaseModel):
    session_id:              str
    status:                  str
    exam_type:               str
    score_overall:           float | None
    score_task_response:     float | None
    score_coherence:         float | None
    score_lexical:           float | None
    score_grammar:           float | None
    cefr_level:              str | None
    feedback:                dict | None
    calibration_version:     str | None
    calibration_correlation: float | None
    calibration_sample_count: int | None
    appeal_status:           str
    created_at:              str
    updated_at:              str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _count_words(text: str) -> int:
    return len(text.split())


async def _check_free_tier_limit(
    conn: asyncpg.Connection,
    user_id: str,
) -> None:
    """
    Enforces the free tier monthly evaluation limit (PRD §5.1).
    Counts evaluations in the current calendar month.
    Raises ValidationError if limit reached.
    """
    count = await conn.fetchval(
        """
        SELECT COUNT(*) FROM linguamentor.writing_sessions
        WHERE user_id    = $1
          AND status     != 'failed'
          AND deleted_at IS NULL
          AND created_at >= date_trunc('month', NOW())
        """,
        uuid_module.UUID(user_id),
    )
    if count >= FREE_TIER_MONTHLY_LIMIT:
        raise ValidationError(
            f"Free tier limit reached: {FREE_TIER_MONTHLY_LIMIT} evaluations per month. "
            f"Upgrade to Pro for unlimited evaluations."
        )


# ── POST /api/v1/writing/evaluate ─────────────────────────────────────────────

@router.post(
    "/evaluate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EvaluateResponse,
    summary="Submit an essay for AI evaluation",
)
async def evaluate_essay(
    data: EvaluateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    queues: QueueRegistry    = Depends(get_queue_registry),
    user: dict               = Depends(get_current_user),
) -> JSONResponse:
    user_id       = user["sub"]
    tier          = user.get("tier", "free")
    word_count    = _count_words(data.essay_text)
    min_words     = MIN_WORD_COUNTS.get(data.exam_type, 100)

    # ── Validation ─────────────────────────────────────────────────────────
    if word_count < min_words:
        raise ValidationError(
            f"Essay too short: {word_count} words. "
            f"{data.exam_type.upper()} requires at least {min_words} words."
        )

    # Free tier monthly limit check
    if tier == "free":
        await _check_free_tier_limit(conn, user_id)

    # ── Create writing_session (status=pending) ────────────────────────────
    session_id = uuid_module.uuid4()

    await conn.execute(
        """
        INSERT INTO linguamentor.writing_sessions (
            id, user_id, exam_type, task_type,
            essay_text, word_count,
            status, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6,
            'pending', NOW(), NOW()
        )
        """,
        session_id,
        uuid_module.UUID(user_id),
        data.exam_type,
        data.task_type,
        data.essay_text,
        word_count,
    )

    # ── Enqueue BullMQ job ─────────────────────────────────────────────────
    # CRITICAL: only session_id goes into the queue — never essay_text.
    # Redis job data is plaintext. Essay content must stay in PostgreSQL.
    job = await queues.writing_eval.add(
        "writing_eval",
        {"session_id": str(session_id)},
        WRITING_EVAL_JOB_OPTIONS,
    )

    polling_url = f"/api/v1/writing/result/{session_id}"

    logger.info(
        f"Essay submitted | session={str(session_id)[:8]}... | "
        f"job={job.id} | exam={data.exam_type} | words={word_count} | tier={tier}"
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=EvaluateResponse(
            job_id=str(job.id),
            session_id=str(session_id),
            status="pending",
            polling_url=polling_url,
        ).model_dump(),
    )


# ── GET /api/v1/writing/result/{session_id} ────────────────────────────────────

@router.get(
    "/result/{session_id}",
    response_model=EvaluationResult,
    summary="Poll evaluation status and retrieve results",
)
async def get_evaluation_result(
    session_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: dict               = Depends(get_current_user),
) -> JSONResponse:
    user_id = user["sub"]

    row = await conn.fetchrow(
        """
        SELECT
            id::text,
            exam_type,
            status,
            score_task_response,
            score_coherence,
            score_lexical,
            score_grammar,
            score_overall,
            cefr_level,
            feedback_json,
            calibration_version,
            calibration_correlation,
            calibration_sample_count,
            appeal_status,
            created_at,
            updated_at
        FROM linguamentor.writing_sessions
        WHERE id      = $1
          AND user_id = $2
          AND deleted_at IS NULL
        """,
        uuid_module.UUID(session_id),
        uuid_module.UUID(user_id),
    )

    if not row:
        raise NotFoundError("WritingSession", session_id)

    status_code = (
        status.HTTP_200_OK
        if row["status"] in ("scored", "failed")
        else status.HTTP_202_ACCEPTED   # still processing — client should re-poll
    )

    return JSONResponse(
        status_code=status_code,
        content=EvaluationResult(
            session_id=row["id"],
            status=row["status"],
            exam_type=row["exam_type"],
            score_overall=float(row["score_overall"]) if row["score_overall"] else None,
            score_task_response=float(row["score_task_response"]) if row["score_task_response"] else None,
            score_coherence=float(row["score_coherence"]) if row["score_coherence"] else None,
            score_lexical=float(row["score_lexical"]) if row["score_lexical"] else None,
            score_grammar=float(row["score_grammar"]) if row["score_grammar"] else None,
            cefr_level=row["cefr_level"],
            feedback=row["feedback_json"],
            calibration_version=row["calibration_version"],
            calibration_correlation=float(row["calibration_correlation"]) if row["calibration_correlation"] else None,
            calibration_sample_count=row["calibration_sample_count"],
            appeal_status=row["appeal_status"],
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
        ).model_dump(),
    )
