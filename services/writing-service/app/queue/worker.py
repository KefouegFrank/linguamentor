# BullMQ worker — consumes writing evaluation jobs.
#
# Each job payload contains ONLY the writing_session_id.
# Essay text is NEVER stored in the queue — only a DB reference.
# This is a hard security requirement: Redis job data is plaintext.
#
# Worker lifecycle:
#   1. Fetch writing_session from DB by session_id
#   2. Load active calibration_baseline (Pearson, version, sample_count)
#   3. Assemble 8-layer prompt
#   4. Call AIProvider (with fallback)
#   5. Validate response schema (Pydantic)
#   6. Determine CEFR level from band score
#   7. Update writing_session → status=scored
#   8. Create AIModelRun record (mandatory — PRD §11.5)
#   9. Update skill_vector (weighted moving average)
#  10. Create ReadinessSnapshot
#
# Error classification:
#   - Schema validation failure → UnrecoverableError (no retry — bad prompt)
#   - AI provider error (rate limit, 5xx) → retryable (exponential backoff)
#   - DB error → retryable
#   - Essay not found in DB → UnrecoverableError (job is orphaned)

import asyncio
import hashlib
import json
import logging
import uuid as uuid_module
from datetime import datetime, timezone

import asyncpg
from bullmq import Worker, Job, UnrecoverableError
from redis.asyncio import Redis as AsyncRedis

from app.calibration.ai_provider import get_ai_provider
from app.calibration.prompt_builder import build_evaluation_prompt
from app.calibration.schemas import ExamType
from app.config import get_settings
from app.queue.queues import (
    QUEUE_WRITING_EVAL,
    QUEUE_WRITING_EVAL_DLQ,
    WRITING_EVAL_JOB_OPTIONS,
)
from app.writing.cefr import band_to_cefr
from app.writing.skill_vector import update_skill_vector

logger = logging.getLogger(__name__)

# P95 target per PRD §9.1 — 6 seconds for async essay scoring
# We set 30s worker timeout: 6s AI call + DB reads/writes + buffer
# If the AI provider is catastrophically slow, we fail gracefully
WORKER_JOB_TIMEOUT_MS = 30_000


async def _load_calibration_baseline(conn: asyncpg.Connection) -> dict:
    """
    Loads the active calibration baseline for use in AIModelRun logging.
    Returns minimal dict — version string + pearson + sample count.
    Falls back to dev values if no baseline exists (Phase 0 not yet complete).
    """
    row = await conn.fetchrow(
        """
        SELECT
            calibration_version,
            pearson_overall,
            essays_count
        FROM linguamentor.calibration_baseline
        ORDER BY approved_at DESC
        LIMIT 1
        """
    )
    if row:
        return {
            "version":       row["calibration_version"],
            "pearson":       float(row["pearson_overall"]),
            "sample_count":  row["essays_count"],
        }
    # No baseline yet — Phase 0 not complete
    settings = get_settings()
    return {
        "version":      settings.calibration_version,
        "pearson":      0.0,
        "sample_count": 0,
    }


async def _fetch_writing_session(
    conn: asyncpg.Connection,
    session_id: str,
) -> dict:
    """Fetches the writing session and joins learner profile for prompt context."""
    row = await conn.fetchrow(
        """
        SELECT
            ws.id::text,
            ws.user_id::text,
            ws.exam_type,
            ws.task_type,
            ws.essay_text,
            ws.word_count,
            ws.status,
            lp.accent_target,
            lp.default_persona,
            lp.cefr_writing,
            lp.target_exam,
            sv.grammar,
            sv.vocabulary,
            sv.coherence,
            sv.pronunciation,
            sv.fluency,
            sv.comprehension
        FROM linguamentor.writing_sessions ws
        JOIN linguamentor.learner_profiles lp ON lp.user_id = ws.user_id
        JOIN linguamentor.skill_vectors sv    ON sv.user_id = ws.user_id
        WHERE ws.id = $1
          AND ws.deleted_at IS NULL
        """,
        uuid_module.UUID(session_id),
    )
    if not row:
        raise UnrecoverableError(
            f"Writing session {session_id} not found — job is orphaned"
        )
    if row["status"] == "scored":
        raise UnrecoverableError(
            f"Writing session {session_id} already scored — duplicate job"
        )
    return dict(row)


async def _create_ai_model_run(
    conn: asyncpg.Connection,
    session: dict,
    prompt_hash: str,
    latency_ms: int,
    calibration: dict,
    provider_name: str,
    input_tokens: int | None,
    output_tokens: int | None,
    response_hash: str,
) -> str:
    """
    Creates the AIModelRun audit record — mandatory per PRD §11.5.
    Called AFTER the AI response is validated — never before.
    Returns the run_id for FK linkage in writing_sessions.
    """
    run_id = uuid_module.uuid4()
    settings = get_settings()

    await conn.execute(
        """
        INSERT INTO linguamentor.ai_model_runs (
            id, model_name, model_version, task_type,
            prompt_hash, input_token_count, output_token_count,
            latency_ms, response_hash,
            user_reference_id,
            calibration_version, calibration_sample_count,
            persona_config, provider_name,
            served_from_cache, created_at
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7,
            $8, $9,
            $10,
            $11, $12,
            $13, $14,
            FALSE, $15
        )
        """,
        run_id,
        _provider_model_name(provider_name),
        "latest",                           # version string — provider-dependent
        "writing_score",                    # task_type per PRD §11.5
        prompt_hash,
        input_tokens,
        output_tokens,
        latency_ms,
        response_hash,
        uuid_module.UUID(session["user_id"]),   # anonymised ref — no PII
        calibration["version"],
        calibration["sample_count"],
        session.get("default_persona", "companion"),
        provider_name.lower(),
        datetime.now(timezone.utc),
    )
    return str(run_id)


def _provider_model_name(provider_class_name: str) -> str:
    """Maps provider class name to canonical model name for AIModelRun logging."""
    return {
        "OpenAIProvider":    "gpt-4o",
        "AnthropicProvider": "claude-3-5-sonnet-20241022",
        "GroqProvider":      "llama-3.3-70b-versatile",
        "GeminiProvider":    "gemini-2.0-flash",
        "MockProvider":      "mock",
    }.get(provider_class_name, provider_class_name.lower())


async def _update_writing_session(
    conn: asyncpg.Connection,
    session_id: str,
    evaluation,       # AIEvaluationResponse
    cefr_level: str,
    ai_model_run_id: str,
    calibration: dict,
) -> None:
    """Updates the writing session to scored status with all evaluation results."""
    await conn.execute(
        """
        UPDATE linguamentor.writing_sessions SET
            status                   = 'scored',
            score_task_response      = $1,
            score_coherence          = $2,
            score_lexical            = $3,
            score_grammar            = $4,
            score_overall            = $5,
            cefr_level               = $6,
            feedback_json            = $7,
            calibration_version      = $8,
            calibration_correlation  = $9,
            calibration_sample_count = $10,
            ai_model_run_id          = $11,
            updated_at               = NOW()
        WHERE id = $12
        """,
        evaluation.scores.score_task_response,
        evaluation.scores.score_coherence_cohesion,
        evaluation.scores.score_lexical_resource,
        evaluation.scores.score_grammatical_range,
        evaluation.scores.score_overall,
        cefr_level,
        json.dumps({
            "rationale_task_response":      evaluation.rationale_task_response,
            "rationale_coherence_cohesion": evaluation.rationale_coherence_cohesion,
            "rationale_lexical_resource":   evaluation.rationale_lexical_resource,
            "rationale_grammatical_range":  evaluation.rationale_grammatical_range,
            "overall_feedback":             evaluation.overall_feedback,
            "low_confidence":               evaluation.low_confidence,
            "low_confidence_reason":        evaluation.low_confidence_reason,
        }),
        calibration["version"],
        calibration["pearson"],
        calibration["sample_count"],
        uuid_module.UUID(ai_model_run_id),
        uuid_module.UUID(session_id),
    )


async def _create_readiness_snapshot(
    conn: asyncpg.Connection,
    user_id: str,
    session: dict,
    new_overall_score: float,
) -> None:
    """
    Creates a ReadinessSnapshot after each evaluation.
    Formula (Phase 1 simplified — full formula in Phase 4):
      readiness_index = weighted average of skill_vector dimensions
    Phase 4 will add trend_factor and confidence_interval.
    """
    sv = {
        "grammar":       float(session.get("grammar", 0) or 0),
        "vocabulary":    float(session.get("vocabulary", 0) or 0),
        "coherence":     float(session.get("coherence", 0) or 0),
        "pronunciation": float(session.get("pronunciation", 0) or 0),
        "fluency":       float(session.get("fluency", 0) or 0),
        "comprehension": float(session.get("comprehension", 0) or 0),
    }

    # Simple weighted average for Phase 1
    # Writing-focused weights — grammar and coherence weighted higher
    weights = {
        "grammar":       0.25,
        "vocabulary":    0.20,
        "coherence":     0.25,
        "pronunciation": 0.10,
        "fluency":       0.10,
        "comprehension": 0.10,
    }
    readiness_index = sum(sv[k] * weights[k] for k in sv)

    # Fetch previous snapshot for delta calculation
    prev = await conn.fetchval(
        """
        SELECT readiness_index FROM linguamentor.readiness_snapshots
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        uuid_module.UUID(user_id),
    )
    delta = round(readiness_index - float(prev), 4) if prev else None

    # Project band from overall score (0-9 IELTS scale → 0-1 normalised)
    projected_band = new_overall_score

    await conn.execute(
        """
        INSERT INTO linguamentor.readiness_snapshots (
            id, user_id,
            readiness_index, projected_band, confidence_interval,
            delta_from_previous, skill_vector_snapshot,
            trigger_event, created_at
        ) VALUES (
            $1, $2,
            $3, $4, $5,
            $6, $7,
            $8, NOW()
        )
        """,
        uuid_module.uuid4(),
        uuid_module.UUID(user_id),
        round(readiness_index, 4),
        projected_band,
        0.5,        # Phase 1 placeholder — ±0.5 band confidence interval
        delta,
        json.dumps(sv),
        "session_complete",
    )


async def _route_to_dlq(
    session_id: str,
    job_id: str,
    reason: str,
    redis_client: AsyncRedis,
) -> None:
    """
    Routes an exhausted job to the DLQ for manual inspection.
    Stores minimal metadata — session_id + reason + timestamp.
    Operations team can inspect and manually retry from here.
    """
    from bullmq import Queue
    dlq = Queue(QUEUE_WRITING_EVAL_DLQ, {"connection": redis_client})
    try:
        await dlq.add(
            "failed_eval",
            {
                "original_job_id": job_id,
                "session_id":      session_id,
                "reason":          reason,
                "failed_at":       datetime.now(timezone.utc).isoformat(),
            },
            {
                "removeOnComplete": {"count": 1000},
                "removeOnFail":     {"count": 1000},
            },
        )
        logger.error(
            f"Job {job_id} routed to DLQ | session={session_id} | reason={reason}"
        )
    except Exception as e:
        logger.error(f"Failed to route job to DLQ: {e}")
    finally:
        await dlq.close()


def _make_processor(
    postgres_pool: asyncpg.Pool,
    redis_client:  AsyncRedis,
):
    """
    Factory that returns the BullMQ processor function.
    Uses closure to inject the DB pool and Redis client without globals.
    """
    async def process(job: Job, job_token: str) -> dict:
        session_id = job.data.get("session_id")
        if not session_id:
            raise UnrecoverableError("Job payload missing session_id")

        logger.info(
            f"Processing writing eval job | "
            f"job_id={job.id} session={session_id[:8]}..."
        )

        async with postgres_pool.acquire() as conn:
            # ── 1. Mark session as processing ─────────────────────────────
            await conn.execute(
                """
                UPDATE linguamentor.writing_sessions
                SET status = 'processing', updated_at = NOW()
                WHERE id = $1 AND status = 'pending'
                """,
                uuid_module.UUID(session_id),
            )

            # ── 2. Fetch session + learner context ────────────────────────
            session = await _fetch_writing_session(conn, session_id)

            # ── 3. Load calibration baseline ──────────────────────────────
            calibration = await _load_calibration_baseline(conn)

            # ── 4. Assemble 8-layer prompt ────────────────────────────────
            try:
                exam_type = ExamType(session["exam_type"])
            except ValueError:
                raise UnrecoverableError(
                    f"Unknown exam type: {session['exam_type']}"
                )

            # Build a minimal task_prompt if not stored on the session
            # In Phase 3 (exam simulation), task_prompt is stored separately
            task_prompt = (
                f"Write an essay on the {session['exam_type'].upper()} task. "
                f"(Full prompt stored separately in Phase 3)"
            )

            prompt = build_evaluation_prompt(
                exam_type=exam_type,
                task_prompt=task_prompt,
                essay_text=session["essay_text"],
                calibration_mode=False,
            )

            # ── 5. Call AI provider ───────────────────────────────────────
            try:
                provider      = get_ai_provider()
                evaluation, prompt_hash, latency_ms = await provider.evaluate_essay(prompt)
            except ValueError as e:
                # Schema validation failure — bad prompt, no retry
                raise UnrecoverableError(f"AI response schema invalid: {e}")
            except Exception as e:
                # Network/rate limit/provider error — retryable
                logger.warning(
                    f"AI provider error (attempt {job.attemptsMade + 1}/3): {e}"
                )
                # Mark back to pending so retries don't see 'processing'
                await conn.execute(
                    """
                    UPDATE linguamentor.writing_sessions
                    SET status = 'pending', updated_at = NOW()
                    WHERE id = $1
                    """,
                    uuid_module.UUID(session_id),
                )
                raise  # BullMQ will retry with exponential backoff

            # ── 6. Compute response hash for audit trail ──────────────────
            response_str = json.dumps({
                "scores": evaluation.scores.model_dump(),
                "feedback": evaluation.overall_feedback,
            }, sort_keys=True)
            response_hash = hashlib.sha256(response_str.encode()).hexdigest()

            # ── 7. Determine CEFR level ───────────────────────────────────
            cefr_level = band_to_cefr(float(evaluation.scores.score_overall))

            # ── 8. Create AIModelRun record (mandatory — PRD §11.5) ───────
            provider_name = provider.__class__.__name__
            ai_model_run_id = await _create_ai_model_run(
                conn=conn,
                session=session,
                prompt_hash=prompt_hash,
                latency_ms=latency_ms,
                calibration=calibration,
                provider_name=provider_name,
                input_tokens=None,      # populated when provider exposes token counts
                output_tokens=None,
                response_hash=response_hash,
            )

            # ── 9. Update writing session → scored ────────────────────────
            await _update_writing_session(
                conn=conn,
                session_id=session_id,
                evaluation=evaluation,
                cefr_level=cefr_level,
                ai_model_run_id=ai_model_run_id,
                calibration=calibration,
            )

            # ── 10. Update skill vector (weighted moving average) ─────────
            await update_skill_vector(
                conn=conn,
                user_id=session["user_id"],
                evaluation=evaluation,
                exam_type=exam_type,
            )

            # ── 11. Create ReadinessSnapshot ──────────────────────────────
            await _create_readiness_snapshot(
                conn=conn,
                user_id=session["user_id"],
                session=session,
                new_overall_score=float(evaluation.scores.score_overall),
            )

        logger.info(
            f"Writing eval complete | job={job.id} | "
            f"session={session_id[:8]}... | "
            f"band={evaluation.scores.score_overall} | "
            f"cefr={cefr_level} | {latency_ms}ms"
        )

        return {
            "session_id": session_id,
            "score_overall": evaluation.scores.score_overall,
            "cefr_level": cefr_level,
        }

    return process


async def start_writing_eval_worker(
    redis_client: AsyncRedis,
    postgres_pool: asyncpg.Pool,
) -> tuple[Worker, asyncio.Event]:
    """
    Starts the writing evaluation BullMQ worker.
    Returns (worker, shutdown_event) — caller sets shutdown_event to stop.

    Concurrency=3: process 3 essays simultaneously.
    With max_size=20 DB connections and P95 6s AI latency,
    3 concurrent workers is conservative but safe for Phase 1.
    Scale to 10+ in production with dedicated worker pods.
    """
    settings = get_settings()
    shutdown_event = asyncio.Event()

    processor = _make_processor(postgres_pool, redis_client)

    worker = Worker(
        QUEUE_WRITING_EVAL,
        processor,
        {
            "connection":  redis_client,
            "concurrency": 3,
            "lockDuration": WORKER_JOB_TIMEOUT_MS,
        },
    )

    # ── Worker event handlers ─────────────────────────────────────────────────

    def on_completed(job: Job, result: dict) -> None:
        logger.info(
            f"[worker] completed | job={job.id} | "
            f"session={result.get('session_id', '')[:8]}..."
        )

    def on_failed(job: Job | None, err: Exception) -> None:
        if job is None:
            logger.error(f"[worker] job failed with no job reference: {err}")
            return

        session_id = job.data.get("session_id", "unknown")
        attempts_made = getattr(job, "attemptsMade", 0)
        max_attempts = 3

        logger.error(
            f"[worker] failed | job={job.id} | "
            f"session={session_id[:8]}... | "
            f"attempt={attempts_made}/{max_attempts} | "
            f"error={err}"
        )

        # Route to DLQ when all retries exhausted
        if attempts_made >= max_attempts:
            asyncio.create_task(
                _route_to_dlq(
                    session_id=session_id,
                    job_id=str(job.id),
                    reason=str(err),
                    redis_client=redis_client,
                )
            )
            # Mark the session as failed in DB for client polling
            asyncio.create_task(
                _mark_session_failed(
                    postgres_pool=postgres_pool,
                    session_id=session_id,
                    reason=str(err),
                )
            )

    worker.on("completed", on_completed)
    worker.on("failed", on_failed)

    logger.info(
        f"Writing eval worker started | "
        f"queue={QUEUE_WRITING_EVAL} | concurrency=3"
    )

    return worker, shutdown_event


async def _mark_session_failed(
    postgres_pool: asyncpg.Pool,
    session_id: str,
    reason: str,
) -> None:
    """Marks a writing session as failed after all retries exhausted."""
    try:
        async with postgres_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE linguamentor.writing_sessions
                SET status = 'failed', updated_at = NOW()
                WHERE id = $1
                """,
                uuid_module.UUID(session_id),
            )
    except Exception as e:
        logger.error(f"Failed to mark session {session_id} as failed: {e}")
