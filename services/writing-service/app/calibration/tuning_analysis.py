"""
Diagnostic analysis for failed or borderline calibration runs.

When a calibration run fails to clear 0.85 — or passes but with
a category close to the threshold — this tool identifies exactly
where the AI diverged from human graders and provides actionable
guidance on which prompt layer to adjust.

The analysis answers four questions:
  1. Which rubric categories diverged most?
  2. Which band ranges show the largest AI-human gap?
  3. Are there systematic biases (AI consistently high or low)?
  4. Which specific essays are the worst outliers?
"""

import logging
import math
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)

# Threshold below which a category is considered to need tuning
TUNING_THRESHOLD = 0.85

# Maximum band gap before an essay is flagged as an outlier
OUTLIER_GAP_THRESHOLD = 1.5


@dataclass
class CategoryAnalysis:
    """Detailed analysis for one rubric category."""
    category:           str
    pearson_r:          float
    mean_ai_score:      float
    mean_human_score:   float
    mean_absolute_error: float
    bias:               float       # positive = AI scores higher than human
    outlier_essays:     list[dict]  # essays where gap > OUTLIER_GAP_THRESHOLD
    passed:             bool
    tuning_guidance:    str


@dataclass
class TuningReport:
    """Complete diagnostic report for one calibration run."""
    run_id:             str
    categories:         list[CategoryAnalysis]
    primary_issue:      str         # the single most actionable finding
    recommended_layer:  int         # which prompt layer to modify
    recommended_action: str         # specific change to make


async def analyse_run(
    conn: asyncpg.Connection,
    run_id: str,
) -> TuningReport:
    """
    Produces a full diagnostic analysis of a calibration run.

    Fetches all AI-human score pairs, computes per-category statistics,
    identifies outlier essays, and generates specific tuning guidance.
    """
    import uuid as uuid_module

    rows = await conn.fetch(
        """
        SELECT
            ai.essay_id::text,
            ce.approximate_band,

            ai.score_task_response       AS ai_tr,
            ai.score_coherence_cohesion  AS ai_cc,
            ai.score_lexical_resource    AS ai_lr,
            ai.score_grammatical_range   AS ai_gr,
            ai.score_overall             AS ai_overall,

            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_task_response END)      AS h_tr,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_coherence_cohesion END) AS h_cc,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_lexical_resource END)   AS h_lr,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_grammatical_range END)  AS h_gr,
            AVG(CASE WHEN hs.is_adjudicating = FALSE
                THEN hs.score_overall END)            AS h_overall

        FROM linguamentor.calibration_ai_scores ai
        JOIN linguamentor.calibration_essays ce ON ce.id = ai.essay_id
        JOIN linguamentor.calibration_human_scores hs ON hs.essay_id = ai.essay_id
        WHERE ai.run_id = $1
        GROUP BY
            ai.essay_id, ce.approximate_band,
            ai.score_task_response, ai.score_coherence_cohesion,
            ai.score_lexical_resource, ai.score_grammatical_range,
            ai.score_overall
        HAVING COUNT(CASE WHEN hs.is_adjudicating = FALSE THEN 1 END) >= 2
        ORDER BY ce.approximate_band
        """,
        uuid_module.UUID(run_id),
    )

    if not rows:
        raise ValueError(f"No scored essays found for run {run_id}")

    # Build parallel lists per category for analysis
    cat_data = {
        "task_response":      {"ai": [], "human": [], "label": "Task Response",       "layer": 5},
        "coherence_cohesion": {"ai": [], "human": [], "label": "Coherence & Cohesion","layer": 5},
        "lexical_resource":   {"ai": [], "human": [], "label": "Lexical Resource",    "layer": 5},
        "grammatical_range":  {"ai": [], "human": [], "label": "Grammatical Range",   "layer": 5},
        "overall":            {"ai": [], "human": [], "label": "Overall Band",        "layer": 4},
    }
    essay_details = []

    for row in rows:
        for cat, cols in [
            ("task_response",      ("ai_tr",      "h_tr")),
            ("coherence_cohesion", ("ai_cc",      "h_cc")),
            ("lexical_resource",   ("ai_lr",      "h_lr")),
            ("grammatical_range",  ("ai_gr",      "h_gr")),
            ("overall",            ("ai_overall", "h_overall")),
        ]:
            ai_val = float(row[cols[0]])
            h_val  = float(row[cols[1]]) if row[cols[1]] else None
            if h_val is not None:
                cat_data[cat]["ai"].append(ai_val)
                cat_data[cat]["human"].append(h_val)

        essay_details.append({
            "essay_id": row["essay_id"],
            "band":     float(row["approximate_band"]) if row["approximate_band"] else None,
            "ai_overall":    float(row["ai_overall"]),
            "human_overall": float(row["h_overall"]) if row["h_overall"] else None,
            "gap": abs(float(row["ai_overall"]) - float(row["h_overall"]))
                   if row["h_overall"] else None,
        })

    categories = []
    worst_r = 1.0
    worst_cat = None

    for cat_key, data in cat_data.items():
        ai_scores    = data["ai"]
        human_scores = data["human"]
        n            = len(ai_scores)

        if n < 2:
            continue

        # Pearson r
        mean_ai    = sum(ai_scores) / n
        mean_human = sum(human_scores) / n
        dev_ai     = [x - mean_ai for x in ai_scores]
        dev_human  = [x - mean_human for x in human_scores]
        num        = sum(a * b for a, b in zip(dev_ai, dev_human))
        den        = math.sqrt(sum(a**2 for a in dev_ai) * sum(b**2 for b in dev_human))
        r          = (num / den) if den > 0 else 0.0

        # Bias — positive means AI scores higher
        bias = mean_ai - mean_human

        # Mean absolute error
        mae = sum(abs(a - b) for a, b in zip(ai_scores, human_scores)) / n

        # Outliers — essays where gap > threshold
        outliers = [
            e for e in essay_details
            if e["gap"] and e["gap"] > OUTLIER_GAP_THRESHOLD
        ]

        # Generate tuning guidance
        if r >= TUNING_THRESHOLD:
            guidance = f"Passing (r={r:.4f}). No tuning required."
        elif bias > 0.5:
            guidance = (
                f"AI scoring {bias:+.2f} bands above human consensus. "
                f"Tighten the Layer 5 rubric descriptors for {data['label']} — "
                f"add explicit examples of what does NOT qualify for high bands."
            )
        elif bias < -0.5:
            guidance = (
                f"AI scoring {bias:+.2f} bands below human consensus. "
                f"Expand the Layer 5 rubric descriptors for {data['label']} — "
                f"add explicit examples of what qualifies for mid-high bands."
            )
        else:
            guidance = (
                f"Low correlation (r={r:.4f}) without clear bias direction. "
                f"Review outlier essays for systematic pattern before adjusting prompt."
            )

        if r < worst_r:
            worst_r   = r
            worst_cat = data["label"]

        categories.append(CategoryAnalysis(
            category=data["label"],
            pearson_r=round(r, 4),
            mean_ai_score=round(mean_ai, 3),
            mean_human_score=round(mean_human, 3),
            mean_absolute_error=round(mae, 3),
            bias=round(bias, 3),
            outlier_essays=outliers,
            passed=(r >= TUNING_THRESHOLD),
            tuning_guidance=guidance,
        ))

    # Determine primary issue and recommended action
    failing = [c for c in categories if not c.passed]

    if not failing:
        primary_issue      = "All categories passing — no tuning required."
        recommended_layer  = 0
        recommended_action = "None"
    elif len(failing) == 1:
        f = failing[0]
        primary_issue = (
            f"{f.category} is the only failing category (r={f.pearson_r}). "
            f"Bias: {f.bias:+.3f} bands. "
            f"Targeted Layer 5 rubric adjustment for this category only."
        )
        recommended_layer  = 5
        recommended_action = f.tuning_guidance
    else:
        primary_issue = (
            f"{len(failing)} categories failing. "
            f"Worst: {worst_cat} (r={worst_r:.4f}). "
            f"Systematic prompt issue — review Layer 4 task instruction and "
            f"Layer 5 rubric coverage before adjusting individual categories."
        )
        recommended_layer  = 4
        recommended_action = (
            "Review Layer 4 task instruction for ambiguity. "
            "If bias is consistently positive across categories, add "
            "examples of what does not qualify for high bands. "
            "If bias is mixed, the model may be misinterpreting the rubric "
            "structure — consider restructuring Layer 5 descriptor format."
        )

    report = TuningReport(
        run_id=run_id,
        categories=categories,
        primary_issue=primary_issue,
        recommended_layer=recommended_layer,
        recommended_action=recommended_action,
    )

    # Log full report
    lines = [
        f"\n{'='*65}",
        f"  TUNING ANALYSIS REPORT — Run {run_id[:8]}...",
        f"{'='*65}",
    ]
    for c in report.categories:
        status = "✅" if c.passed else "❌"
        lines.append(
            f"{status} {c.category:<28} "
            f"r={c.pearson_r:.4f}  "
            f"bias={c.bias:+.3f}  "
            f"MAE={c.mean_absolute_error:.3f}"
        )
    lines += [
        f"{'─'*65}",
        f"  PRIMARY ISSUE: {report.primary_issue}",
        f"  RECOMMENDED: Layer {report.recommended_layer} — {report.recommended_action}",
        f"{'='*65}",
    ]
    logger.info("\n".join(lines))

    return report
