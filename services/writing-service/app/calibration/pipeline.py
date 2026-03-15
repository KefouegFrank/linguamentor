"""
Drives the calibration scoring run from start to finish.

Flow per run:
  1. fetch_pending_essays()    — find essays ready for AI scoring
  2. score_essay()             — prompt → LLM → validate → store
  3. run_calibration_scoring() — loops 1+2, tracks progress
  4. create_calibration_run()  — registers a new run before it starts

Runs offline. Never touches a live user session.
If a single essay fails, we log it and keep going —
a partial run with 95% essays scored is more useful than
an aborted run with 0.

Key asyncpg rule applied throughout this file:
Never use $N::uuid casts inside SQL strings when passing run/essay IDs.
Always convert Python str IDs to uuid.UUID objects before passing them
as parameters — asyncpg handles the PostgreSQL type mapping natively.
$N::uuid inside a subquery causes silent parameter binding failures on
some platforms that result in zero rows returned with no error raised.
"""

import json
import logging
import uuid as uuid_module
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
    Returns essays that are graded by humans but not yet scored
    by the AI in this specific run.

    We fetch already-scored essay IDs in a separate query first,
    then exclude them in Python — avoids the asyncpg subquery
    parameter binding issue where NOT IN (subquery with $N) silently
    returns no rows on some platforms without raising any error.
    """
    # Step 1 — fetch IDs already scored in this run.
    # Flat query, no subquery parameter binding, no surprises.
    scored_rows = await conn.fetch(
        """
        SELECT essay_id::text
        FROM linguamentor.calibration_ai_scores
        WHERE run_id = $1
        """,
        uuid_module.UUID(run_id),
    )
    already_scored = {row["essay_id"] for row in scored_rows}

    # Step 2 — fetch all grading-complete essays for this exam type.
    # No run_id subquery here — clean, predictable parameter binding.
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
        ORDER BY ce.created_at
        LIMIT $2
        """,
        exam_type.value,
        limit,
    )

    # Step 3 — exclude already-scored essays in Python.
    # Simple set lookup — fast, transparent, no SQL type coercion issues.
    essays = [
        CalibrationEssayRecord(
            id=row["id"],
            exam_type=ExamType(row["exam_type"]),
            task_prompt=row["task_prompt"],
            essay_text=row["essay_text"],
            word_count=row["word_count"],
        )
        for row in rows
        if row["id"] not in already_scored
    ]

    logger.info(
        f"Found {len(essays)} essays pending AI scoring "
        f"[run={run_id[:8]}... exam={exam_type.value}] "
        f"({len(already_scored)} already scored in this run)"
    )
    return essays


async def score_essay(
    conn: asyncpg.Connection,
    essay: CalibrationEssayRecord,
    run_id: str,
) -> bool:
    """
    Scores one essay end-to-end: prompt → LLM → validate → store.

    Returns True on success, False on any failure.
    We never let one bad essay kill the whole run.
    """
    settings = get_settings()

    try:
        # Assemble the 8-layer prompt in calibration mode —
        # adds a note to the task instruction layer telling the LLM
        # this is a validation run, not a live user session
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
                id,
                essay_id,
                run_id,
                score_task_response,
                score_coherence_cohesion,
                score_lexical_resource,
                score_grammatical_range,
                score_overall,
                model_name,
                model_version,
                prompt_hash,
                raw_response,
                latency_ms,
                scored_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14
            )
            """,
            uuid_module.uuid4(),                        # id — generate fresh
            uuid_module.UUID(essay.id),                 # essay_id — native UUID
            uuid_module.UUID(run_id),                   # run_id — native UUID
            evaluation.scores.score_task_response,
            evaluation.scores.score_coherence_cohesion,
            evaluation.scores.score_lexical_resource,
            evaluation.scores.score_grammatical_range,
            evaluation.scores.score_overall,
            "gpt-4o",
            # calibration_version ties this score to the exact prompt
            # config used — critical for the audit trail
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

        logger.info(
            f"Scored essay {essay.id[:8]}... | "
            f"overall={evaluation.scores.score_overall} | "
            f"{latency_ms}ms"
        )
        return True

    except Exception as e:
        # Log full error but don't reraise — caller tracks failed count
        logger.error(f"Failed to score essay {essay.id[:8]}...: {e}")
        return False


async def run_calibration_scoring(
    conn: asyncpg.Connection,
    run_id: str,
    exam_type: ExamType,
) -> dict:
    """
    Main loop — scores every pending essay for this run.

    Updates essays_scored in the DB after each essay so a monitoring
    dashboard can show live progress rather than waiting for completion.
    """
    logger.info(
        f"Calibration scoring started "
        f"[run={run_id[:8]}... exam={exam_type.value}]"
    )

    essays = await fetch_pending_essays(conn, run_id, exam_type)

    if not essays:
        logger.warning(
            "No essays ready for scoring. "
            "Check that grading_complete = TRUE on calibration_essays."
        )
        return {"run_id": run_id, "scored": 0, "failed": 0, "total": 0}

    scored = 0
    failed = 0

    for i, essay in enumerate(essays, 1):
        logger.info(f"Processing essay {i}/{len(essays)} — {essay.id[:8]}...")

        if await score_essay(conn, essay, run_id):
            scored += 1
        else:
            failed += 1

        # Write progress after every essay — lets us monitor long runs
        # without waiting for the whole thing to finish
        await conn.execute(
            """
            UPDATE linguamentor.calibration_runs
            SET essays_scored = $1
            WHERE id = $2
            """,
            scored,
            uuid_module.UUID(run_id),
        )

    # Mark the run complete with a final timestamp
    await conn.execute(
        """
        UPDATE linguamentor.calibration_runs
        SET completed_at = $1
        WHERE id = $2
        """,
        datetime.now(timezone.utc),
        uuid_module.UUID(run_id),
    )

    summary = {
        "run_id": run_id,
        "scored": scored,
        "failed": failed,
        "total":  len(essays),
    }
    logger.info(f"Calibration scoring complete: {summary}")
    return summary


async def create_calibration_run(
    conn: asyncpg.Connection,
    exam_type: ExamType,
    run_label: str,
    notes: str = "",
) -> str:
    """
    Registers a new calibration run in the DB before scoring starts.
    Returns the run_id as a string — everything in this run references it.
    """
    run_id = str(uuid_module.uuid4())

    await conn.execute(
        """
        INSERT INTO linguamentor.calibration_runs (
            id, run_label, exam_type, notes, started_at
        ) VALUES (
            $1, $2, $3, $4, $5
        )
        """,
        uuid_module.UUID(run_id),   # native UUID — no ::uuid cast in SQL
        run_label,
        exam_type.value,
        notes,
        datetime.now(timezone.utc),
    )

    logger.info(
        f"Calibration run registered: {run_id[:8]}... "
        f"[{exam_type.value}] label='{run_label}'"
    )
    return run_id
