"""
app/calibration/correlation.py

Pearson correlation engine for Phase 0 calibration validation.

Takes AI scores and human consensus scores for the same essay set,
computes correlation per rubric category and overall, and writes
results back to the calibration_runs table.

The 0.85 threshold is non-negotiable — defined in PRD section 60
and the Calibration Brief. This file is where that gate is enforced.

Same asyncpg rule as pipeline.py: all UUID parameters are passed as
native uuid.UUID objects, never as strings with ::uuid SQL casts.
"""

import logging
import math
import uuid as uuid_module
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)

# The gate. Every category and overall must clear this.
# Defined once here — referenced everywhere else.
PEARSON_THRESHOLD = 0.85
# Maximum acceptable mean absolute error between AI and human scores.
# 0.5 bands = one half-band increment — the smallest meaningful IELTS
# difference. If the AI is consistently more than 0.5 bands off on
# average, the scores are misleading regardless of correlation strength.
MAE_THRESHOLD = 0.5


@dataclass
class CategoryCorrelation:
    """
    Correlation result for one rubric category.
    Keeps the data clean when passing results between functions.
    """
    category:  str
    pearson_r: float
    n_samples: int
    passed:    bool

    def __str__(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return (
            f"{self.category:<30} "
            f"r={self.pearson_r:.4f} "
            f"n={self.n_samples} "
            f"{status}"
        )


@dataclass
class CorrelationReport:
    """
    Full correlation results for one calibration run.
    All categories must pass for passed_overall to be True.
    """
    run_id:             str
    task_response:      CategoryCorrelation
    coherence_cohesion: CategoryCorrelation
    lexical_resource:   CategoryCorrelation
    grammatical_range:  CategoryCorrelation
    overall_score:      CategoryCorrelation
    passed_overall:     bool

    def summary(self) -> str:
        """Human-readable summary for logs and the Go/No-Go report."""
        lines = [
            f"\n{'='*60}",
            f"  CALIBRATION CORRELATION REPORT",
            f"  Run: {self.run_id[:8]}...",
            f"  Threshold: r >= {PEARSON_THRESHOLD}",
            f"{'='*60}",
            str(self.task_response),
            str(self.coherence_cohesion),
            str(self.lexical_resource),
            str(self.grammatical_range),
            str(self.overall_score),
            f"{'─'*60}",
            f"  VERDICT: {'✅ PASSED — Ready for Go/No-Go review' if self.passed_overall else '❌ FAILED — Rubric tuning required'}",
            f"{'='*60}",
        ]
        return "\n".join(lines)


def _pearson_r(x: list[float], y: list[float]) -> float:
    """
    Computes Pearson correlation coefficient between two score lists.

    Implemented directly rather than pulling in numpy/scipy —
    keeps the dependency footprint small and makes the math explicit.

    Formula:
        r = Σ((xi - x̄)(yi - ȳ)) / sqrt(Σ(xi - x̄)² · Σ(yi - ȳ)²)

    Returns 0.0 if standard deviation of either list is zero —
    a flat score distribution means correlation is undefined, and
    is itself a calibration problem worth investigating separately.
    """
    n = len(x)

    if n != len(y):
        raise ValueError(
            f"Score lists must be the same length. "
            f"Got x={n}, y={len(y)}"
        )

    if n < 2:
        raise ValueError(
            f"Need at least 2 samples to compute correlation. Got {n}. "
            f"Collect more calibration essays before running correlation."
        )

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    dev_x = [xi - mean_x for xi in x]
    dev_y = [yi - mean_y for yi in y]

    numerator = sum(dx * dy for dx, dy in zip(dev_x, dev_y))

    sum_sq_x = sum(dx ** 2 for dx in dev_x)
    sum_sq_y = sum(dy ** 2 for dy in dev_y)
    denominator = math.sqrt(sum_sq_x * sum_sq_y)

    if denominator == 0.0:
        # Both lists are constant — the AI is outputting the same score
        # for every essay, which means the rubric prompt is not working.
        logger.warning(
            "Pearson denominator is zero — score distribution is flat. "
            "The AI may be outputting identical scores for all essays. "
            "Inspect raw_response in calibration_ai_scores for clues."
        )
        return 0.0

    return numerator / denominator


async def fetch_score_pairs(
    conn: asyncpg.Connection,
    run_id: str,
) -> dict[str, tuple[list[float], list[float]]]:
    """
    Fetches paired AI and human consensus scores for every essay
    scored in this run.

    Consensus = average of the two non-adjudicating human graders.
    Essays where graders disagreed by more than 1.0 band were sent
    to an adjudicating examiner — that score has is_adjudicating = TRUE
    and is handled separately in the consensus computation.

    Returns a dict keyed by rubric category.
    Value is (ai_scores, human_scores) — parallel lists, same order.
    Index i in ai_scores pairs with index i in human_scores.
    """
    rows = await conn.fetch(
        """
        SELECT
            ai.essay_id::text,

            ai.score_task_response       AS ai_task_response,
            ai.score_coherence_cohesion  AS ai_coherence_cohesion,
            ai.score_lexical_resource    AS ai_lexical_resource,
            ai.score_grammatical_range   AS ai_grammatical_range,
            ai.score_overall             AS ai_overall,

            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_task_response END)      AS human_task_response,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_coherence_cohesion END) AS human_coherence_cohesion,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_lexical_resource END)   AS human_lexical_resource,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_grammatical_range END)  AS human_grammatical_range,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_overall END)            AS human_overall

        FROM linguamentor.calibration_ai_scores ai
        JOIN linguamentor.calibration_human_scores hs
            ON hs.essay_id = ai.essay_id
        WHERE
            ai.run_id = $1
        GROUP BY
            ai.essay_id,
            ai.score_task_response,
            ai.score_coherence_cohesion,
            ai.score_lexical_resource,
            ai.score_grammatical_range,
            ai.score_overall
        HAVING
            COUNT(CASE WHEN hs.is_adjudicating = FALSE THEN 1 END) >= 2
        ORDER BY
            ai.essay_id
        """,
        uuid_module.UUID(run_id),   # native UUID — no ::uuid cast in SQL
    )

    if not rows:
        raise ValueError(
            f"No paired scores found for run {run_id}. "
            f"Ensure both AI scoring and human grading are complete "
            f"before running correlation."
        )

    categories = {
        "task_response":      ([], []),
        "coherence_cohesion": ([], []),
        "lexical_resource":   ([], []),
        "grammatical_range":  ([], []),
        "overall":            ([], []),
    }

    for row in rows:
        # Skip essays where human consensus is still incomplete —
        # means graders disagreed and no adjudicator has resolved it yet
        if any(row[f"human_{cat}"] is None for cat in categories):
            logger.warning(
                f"Skipping essay {row['essay_id'][:8]}... — "
                f"human consensus incomplete (adjudication pending)"
            )
            continue

        for cat in categories:
            ai_list, human_list = categories[cat]
            ai_list.append(float(row[f"ai_{cat}"]))
            human_list.append(float(row[f"human_{cat}"]))

    n_complete = len(categories["overall"][0])
    logger.info(
        f"Score pairs ready for correlation: "
        f"{len(rows)} fetched, {n_complete} with complete human consensus"
    )

    return categories

async def compute_correlation(
    conn: asyncpg.Connection,
    run_id: str,
) -> CorrelationReport:
    """
    Computes Pearson correlation AND Mean Absolute Error for all rubric
    categories in this run, then writes results back to calibration_runs.

    Two gates must both pass for passed_overall to be True:
    1. Pearson gate: r >= 0.85 for all five categories
    2. MAE gate: overall MAE <= 0.5 bands

    Pearson alone is insufficient — a model can have strong directional
    correlation while scoring systematically 1+ bands too high or low.
    The MAE gate catches this systematic bias before it reaches learners.
    """
    logger.info(f"Computing Pearson correlation for run {run_id[:8]}...")

    score_pairs = await fetch_score_pairs(conn, run_id)

    def _compute_category(name: str, col: str) -> CategoryCorrelation:
        ai_scores, human_scores = score_pairs[col]
        r = _pearson_r(ai_scores, human_scores)
        return CategoryCorrelation(
            category=name,
            pearson_r=round(r, 4),
            n_samples=len(ai_scores),
            passed=(r >= PEARSON_THRESHOLD),
        )

    task_response      = _compute_category("Task Response",        "task_response")
    coherence_cohesion = _compute_category("Coherence & Cohesion", "coherence_cohesion")
    lexical_resource   = _compute_category("Lexical Resource",     "lexical_resource")
    grammatical_range  = _compute_category("Grammatical Range",    "grammatical_range")
    overall_score      = _compute_category("Overall Band",         "overall")

    # ── Gate 1: Pearson ───────────────────────────────────────────
    # All five categories must reach r >= 0.85
    pearson_passed = all([
        task_response.passed,
        coherence_cohesion.passed,
        lexical_resource.passed,
        grammatical_range.passed,
        overall_score.passed,
    ])

    # ── Gate 2: MAE ───────────────────────────────────────────────
    # AI must be within 0.5 bands of human consensus on average.
    # Computed on overall band scores — the number learners see.
    overall_ai, overall_human = score_pairs["overall"]
    n_overall   = len(overall_ai)
    overall_mae = sum(
        abs(a - b) for a, b in zip(overall_ai, overall_human)
    ) / n_overall
    overall_mae = round(overall_mae, 3)
    mae_passed  = overall_mae <= MAE_THRESHOLD

    # ── Combined verdict ──────────────────────────────────────────
    passed_overall = pearson_passed and mae_passed

    # Log specific failure reason so the developer knows exactly what to fix
    if pearson_passed and not mae_passed:
        logger.warning(
            f"⚠️  Pearson gate PASSED but MAE gate FAILED. "
            f"Overall MAE={overall_mae:.3f} bands exceeds threshold of {MAE_THRESHOLD}. "
            f"The AI has strong directional accuracy but is scoring "
            f"{overall_mae:.2f} bands off on average — this will mislead learners. "
            f"Apply Layer 4 bias correction and re-run calibration."
        )
    elif not pearson_passed and mae_passed:
        logger.warning(
            f"⚠️  MAE gate PASSED but Pearson gate FAILED. "
            f"Scores are close to human consensus but not moving in the "
            f"same direction consistently. Review outlier essays."
        )
    elif not pearson_passed and not mae_passed:
        logger.warning(
            f"❌ Both gates FAILED. MAE={overall_mae:.3f}, "
            f"check individual category Pearson values above."
        )

    # ── Persist results ───────────────────────────────────────────
    await conn.execute(
        """
        UPDATE linguamentor.calibration_runs SET
            pearson_task_response       = $1,
            pearson_coherence_cohesion  = $2,
            pearson_lexical_resource    = $3,
            pearson_grammatical_range   = $4,
            pearson_overall             = $5,
            passed_threshold            = $6,
            notes = COALESCE(notes, '') || $7
        WHERE id = $8
        """,
        task_response.pearson_r,
        coherence_cohesion.pearson_r,
        lexical_resource.pearson_r,
        grammatical_range.pearson_r,
        overall_score.pearson_r,
        passed_overall,
        f" | MAE={overall_mae:.3f} | MAE_passed={mae_passed} | Pearson_passed={pearson_passed}",
        uuid_module.UUID(run_id),
    )

    report = CorrelationReport(
        run_id=run_id,
        task_response=task_response,
        coherence_cohesion=coherence_cohesion,
        lexical_resource=lexical_resource,
        grammatical_range=grammatical_range,
        overall_score=overall_score,
        passed_overall=passed_overall,
    )

    # Append MAE to the summary log
    summary = report.summary()
    mae_line = (
        f"\n  MAE (overall): {overall_mae:.3f} bands "
        f"({'✅ PASS' if mae_passed else '❌ FAIL'} — threshold: {MAE_THRESHOLD})"
    )
    logger.info(summary + mae_line)

    return report

async def store_calibration_baseline(
    conn: asyncpg.Connection,
    run_id: str,
    report: CorrelationReport,
    approved_by: str,
) -> str:
    """
    Writes the immutable calibration baseline record.

    Only callable when passed_overall is True and the product lead
    has signed off. The calibration_version 'v1.0-launch' stored here
    appears on every user score report in production — it is the anchor
    of the scoring transparency promise shown to every learner.
    """
    if not report.passed_overall:
        raise ValueError(
            "Cannot store baseline — correlation has not passed threshold. "
            "All categories must reach r >= 0.85 before baseline is recorded."
        )

    essays_count = await conn.fetchval(
        """
        SELECT essays_scored
        FROM linguamentor.calibration_runs
        WHERE id = $1
        """,
        uuid_module.UUID(run_id),
    )

    await conn.execute(
        """
        INSERT INTO linguamentor.calibration_baseline (
            id,
            calibration_version,
            run_id,
            pearson_overall,
            pearson_task_response,
            pearson_coherence_cohesion,
            pearson_lexical_resource,
            pearson_grammatical_range,
            essays_count,
            approved_by,
            approved_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW()
        )
        """,
        uuid_module.uuid4(),                        # id
        "v1.0-launch",                              # calibration_version
        uuid_module.UUID(run_id),                   # run_id — native UUID
        report.overall_score.pearson_r,
        report.task_response.pearson_r,
        report.coherence_cohesion.pearson_r,
        report.lexical_resource.pearson_r,
        report.grammatical_range.pearson_r,
        essays_count,
        approved_by,
    )

    logger.info(
        f"✅ Calibration baseline stored: v1.0-launch | "
        f"r={report.overall_score.pearson_r} | "
        f"approved_by={approved_by}"
    )

    return "v1.0-launch"
