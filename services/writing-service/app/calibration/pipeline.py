"""
app/calibration/pipeline.py

Offline calibration scoring pipeline — fetches essays, scores via AI,
stores results. Never runs during a live user session.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from app.calibration.schemas import CalibrationEssayRecord, ExamType
from app.calibration.prompt_builder import build_evaluation_prompt
from app.calibration.ai_provider import get_ai_provider
from app.config import get_settings

logger = logging.getLogger(__name__)


async def fetch_pending_essays(
    conn: asyncpg.Connection,
    run_id: str,
    exam_type: ExamType,
    limit: int = 100,
) -> list[CalibrationEssayRecord]:
    """
    Returns essays ready for AI scoring — grading_complete and not yet
    scored in this run. The NOT IN subquery prevents double-scoring
    if the pipeline is restarted mid-run.
    """
    rows = await conn.fetch(
        """
        SELECT
            ce.id::text,
            ce.exam_type,
            ce.task_prompt,
            ce.essay_text,
            ce.word_count
        FROM linguamentor.calibration_essays ce
        WHERE
            ce.grading_complete = TRUE
            AND ce.exam_type = $1
            AND ce.id NOT IN (
                SELECT essay_id
                FROM linguamentor.calibration_ai_scores
                WHERE run_id = $2::uuid
            )
        ORDER BY ce.created_at
        LIMIT $3
        """,
        exam_type.value,
        run_id,
        limit,
    )

    essays = [
        CalibrationEssayRecord(
            id=row["id"],
            exam_type=ExamType(row["exam_type"]),
            task_prompt=row["task_prompt"],
            essay_text=row["essay_text"],
            word_count=row["word_count"],
        )
        for row in rows
    ]

    logger.info(f"Fetched {len(essays)} pending essays [{exam_type.value}] run={run_id}")
    return essays


async def score_essay(
    conn: asyncpg.Connection,
    essay: CalibrationEssayRecord,
    run_id: str,
) -> bool:
    """
    Scores one essay and writes the result to calibration_ai_scores.
    Returns True on success, False on failure — failures are logged
    but don't abort the run, we want maximum essay coverage.
    """
    settings = get_settings()

    try:
        prompt = build_evaluation_prompt(
            exam_type=essay.exam_type,
            task_prompt=essay.task_prompt,
            essay_text=essay.essay_text,
            calibration_mode=True,
        )

        provider = get_ai_provider()
        evaluation, prompt_hash, latency_ms = await provider.evaluate_essay(
            prompt=prompt,
            temperature=0.1,
        )

        await conn.execute(
            """
            INSERT INTO linguamentor.calibration_ai_scores (
                id, essay_id, run_id,
                score_task_response, score_coherence_cohesion,
                score_lexical_resource, score_grammatical_range,
                score_overall, model_name, model_version,
                prompt_hash, raw_response, latency_ms, scored_at
            ) VALUES (
                $1, $2, $3::uuid, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14
            )
            """,
            str(uuid.uuid4()),
            essay.id,
            run_id,
            evaluation.scores.score_task_response,
            evaluation.scores.score_coherence_cohesion,
            evaluation.scores.score_lexical_resource,
            evaluation.scores.score_grammatical_range,
            evaluation.scores.score_overall,
            "gpt-4o",
            settings.calibration_version,
            prompt_hash,
            json.dumps({
                "rationale_task_response":      evaluation.rationale_task_response,
                "rationale_coherence_cohesion": evaluation.rationale_coherence_cohesion,
                "rationale_lexical_resource":   evaluation.rationale_lexical_resource,
                "rationale_grammatical_range":  evaluation.rationale_grammatical_range,
                "overall_feedback":             evaluation.overall_feedback,
                "low_confidence":               evaluation.low_confidence,
                "low_confidence_reason":        evaluation.low_confidence_reason,
            }),
            latency_ms,
            datetime.now(timezone.utc),
        )

        logger.info(f"Scored {essay.id} | overall={evaluation.scores.score_overall} | {latency_ms}ms")
        return True

    except Exception as e:
        logger.error(f"Failed to score essay {essay.id}: {e}")
        return False


async def run_calibration_scoring(
    conn: asyncpg.Connection,
    run_id: str,
    exam_type: ExamType,
) -> dict:
    """Scores all pending essays for a run, updates progress after each one."""
    logger.info(f"Calibration run started: {run_id} [{exam_type.value}]")

    essays = await fetch_pending_essays(conn, run_id, exam_type)

    if not essays:
        logger.warning(f"No pending essays for run {run_id} — check grading_complete flag")
        return {"run_id": run_id, "scored": 0, "failed": 0}

    scored = 0
    failed = 0

    for i, essay in enumerate(essays, 1):
        logger.info(f"Essay {i}/{len(essays)} — {essay.id}")
        success = await score_essay(conn, essay, run_id)

        if success:
            scored += 1
        else:
            failed += 1

        # Update after each essay so monitoring shows live progress
        await conn.execute(
            "UPDATE linguamentor.calibration_runs SET essays_scored = $1 WHERE id = $2::uuid",
            scored, run_id,
        )

    await conn.execute(
        "UPDATE linguamentor.calibration_runs SET completed_at = $1 WHERE id = $2::uuid",
        datetime.now(timezone.utc), run_id,
    )

    summary = {"run_id": run_id, "scored": scored, "failed": failed, "total": len(essays)}
    logger.info(f"Calibration run complete: {summary}")
    return summary


async def create_calibration_run(
    conn: asyncpg.Connection,
    exam_type: ExamType,
    run_label: str,
    notes: str = "",
) -> str:
    """Registers a new run in the DB and returns its UUID."""
    run_id = str(uuid.uuid4())

    await conn.execute(
        """
        INSERT INTO linguamentor.calibration_runs (
            id, run_label, exam_type, notes, started_at
        ) VALUES ($1::uuid, $2, $3, $4, $5)
        """,
        run_id,
        run_label,
        exam_type.value,
        notes,
        datetime.now(timezone.utc),
    )

    logger.info(f"Created calibration run {run_id} [{exam_type.value}]")
    return run_id
