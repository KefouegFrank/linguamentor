# Updates the 6-dimensional skill vector after each writing session.
#
# Formula (PRD §23.1):
#   new_score = (previous × 0.8) + (recent × 0.2)
#
# This is an Exponential Moving Average (EMA) with α=0.2.
# It prevents a single exceptional or poor session from wildly
# shifting the vector — the learner's true level emerges over time.
#
# Dimension mapping — writing evaluation covers 4 of the 6 dimensions:
#   grammar      ← score_grammatical_range  (direct mapping)
#   vocabulary   ← score_lexical_resource   (direct mapping)
#   coherence    ← score_coherence_cohesion (direct mapping)
#   fluency      ← score_overall            (proxy — writing fluency)
#   pronunciation ← not updated by writing (speaking only)
#   comprehension ← not updated by writing (reading/listening only)
#
# All skill vector values are normalised 0.0–1.0.
# IELTS band scores are on 0–9 scale — divide by 9 to normalise.

import logging
import uuid as uuid_module
from datetime import datetime, timezone

import asyncpg

from app.calibration.schemas import ExamType

logger = logging.getLogger(__name__)

EMA_ALPHA = 0.2         # weight of new observation
EMA_PREV  = 1 - EMA_ALPHA   # 0.8 — weight of history


def _normalise(band_score: float) -> float:
    """Normalises IELTS band (0–9) to 0.0–1.0 skill vector scale."""
    return round(min(max(band_score / 9.0, 0.0), 1.0), 4)


def _ema(previous: float, recent: float) -> float:
    """Exponential moving average: new = (prev × 0.8) + (recent × 0.2)"""
    return round((previous * EMA_PREV) + (recent * EMA_ALPHA), 4)


async def update_skill_vector(
    conn: asyncpg.Connection,
    user_id: str,
    evaluation,         # AIEvaluationResponse from calibration/schemas.py
    exam_type: ExamType,
) -> None:
    """
    Updates skill vector dimensions after a writing evaluation.

    Uses optimistic concurrency via the version column — if two sessions
    complete simultaneously (unlikely but possible), the second update
    reads the already-updated vector from the first.

    The version counter is incremented on every update — used by the
    adaptive engine to detect stale reads.
    """
    scores = evaluation.scores

    # Fetch current vector
    row = await conn.fetchrow(
        """
        SELECT
            grammar, vocabulary, coherence,
            pronunciation, fluency, comprehension,
            version
        FROM linguamentor.skill_vectors
        WHERE user_id = $1
        """,
        uuid_module.UUID(user_id),
    )

    if not row:
        logger.error(f"Skill vector not found for user {user_id[:8]}...")
        return

    # Normalise new scores from IELTS band to 0-1
    new_grammar     = _normalise(float(scores.score_grammatical_range))
    new_vocabulary  = _normalise(float(scores.score_lexical_resource))
    new_coherence   = _normalise(float(scores.score_coherence_cohesion))
    new_fluency     = _normalise(float(scores.score_overall))

    # Apply EMA — writing updates 4 of 6 dimensions
    updated_grammar    = _ema(float(row["grammar"]),    new_grammar)
    updated_vocabulary = _ema(float(row["vocabulary"]), new_vocabulary)
    updated_coherence  = _ema(float(row["coherence"]),  new_coherence)
    updated_fluency    = _ema(float(row["fluency"]),    new_fluency)
    # pronunciation and comprehension unchanged by writing

    now = datetime.now(timezone.utc)

    result = await conn.execute(
        """
        UPDATE linguamentor.skill_vectors SET
            grammar                      = $1,
            vocabulary                   = $2,
            coherence                    = $3,
            fluency                      = $4,
            grammar_last_practiced_at    = $5,
            vocabulary_last_practiced_at = $5,
            coherence_last_practiced_at  = $5,
            fluency_last_practiced_at    = $5,
            version                      = version + 1,
            updated_at                   = $5
        WHERE user_id = $6
          AND version  = $7
        """,
        updated_grammar,
        updated_vocabulary,
        updated_coherence,
        updated_fluency,
        now,
        uuid_module.UUID(user_id),
        row["version"],     # optimistic concurrency — only update if version matches
    )

    if result == "UPDATE 0":
        # Version mismatch — another session updated it simultaneously
        # This is non-fatal — the vector reflects the other session's data
        logger.warning(
            f"Skill vector version conflict for user {user_id[:8]}... "
            f"— concurrent update detected, skipping"
        )
        return

    logger.debug(
        f"Skill vector updated | user={user_id[:8]}... | "
        f"grammar={updated_grammar} vocab={updated_vocabulary} "
        f"coherence={updated_coherence} fluency={updated_fluency}"
    )
