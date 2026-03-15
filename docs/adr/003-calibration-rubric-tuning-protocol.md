# ADR-003: Calibration Rubric Tuning Protocol

**Status:** Active  
**Date:** 2026-03-15  
**Author:** TETSOPGUIM Frank  

## Context

Phase 0 requires Pearson correlation ≥ 0.85 between AI scores and 
human examiner consensus across all five metrics before any 
user-facing evaluation feature ships. When a calibration run fails 
this threshold, a structured tuning protocol is required to:

1. Diagnose the failure without guessing
2. Make targeted prompt changes rather than wholesale rewrites  
3. Maintain an audit trail of every iteration
4. Prevent infinite tuning loops that delay the Go/No-Go decision

## Decision: 3-Iteration Maximum with Escalation Gate

### Iteration Protocol

**Step 1 — Run analysis before touching any code**
```bash
curl -s http://localhost:8001/calibration/runs/{run_id}/analysis
```

Read the `primary_issue` and `recommended_action` fields. Do not
adjust the prompt based on intuition — only based on the analysis.

**Step 2 — Identify the correct layer to modify**

| Failure Pattern | Layer to Modify | What to Change |
|---|---|---|
| Single category failing, AI too high | Layer 5 | Add "does NOT qualify" examples for that category |
| Single category failing, AI too low | Layer 5 | Add "qualifies for band X" examples for that category |
| Multiple categories failing, consistent bias | Layer 4 | Tighten task instruction — clarify scoring is independent per category |
| Multiple categories failing, mixed bias | Layer 5 | Restructure descriptor format — numbered descriptors vs prose |
| Overall band failing, categories passing | Prompt schema | Fix score_overall instruction — ensure rounding is explicit |

**Step 3 — Register the new prompt variant**

Before running the next calibration pass, register the change:
```python
from app.calibration.prompt_registry import register_new_variant

register_new_variant(
    version_label="v1.1-tr-rubric",
    description="Added negative examples to Task Response descriptors at Layer 5",
    layer_modified=5,
    change_rationale="Task Response r=0.84, just below threshold. AI scoring 0.3 bands above human on Band 6-7 essays.",
)
```

Update `LM_CALIBRATION_VERSION=v1.1-tr-rubric` in `.env` before running.

**Step 4 — Run calibration and correlate**

New run, new correlation. Never re-use a run_id across prompt versions.

**Step 5 — Evaluate result**

- If r ≥ 0.85 across all categories → proceed to Go/No-Go sign-off
- If r improved but still below 0.85 → iterate (maximum 2 more times)
- If r did not improve or regressed → escalate immediately (see below)

### Maximum Iterations

**3 iterations maximum before product lead escalation.**

Rationale: if three targeted prompt adjustments cannot achieve 0.85,
the problem is not the prompt — it is the model, the essay set, or
the human grading quality. Continuing to iterate without escalation
wastes time and risks overfitting the prompt to the calibration set.

### Escalation Criteria (any one triggers escalation)

- 3 iterations completed without passing threshold
- Any single iteration produces regression (r decreases)
- Analysis reveals systematic bias > 1.0 bands in any category
- Human score variance between examiners > 1.5 bands on any essay

### Escalation Path

1. Document the three run IDs and correlation results
2. Pull outlier essays from each failing category
3. Present to product lead with specific recommendation:
   - Switch to a higher-capability model (GPT-4o instead of LLaMA)
   - Commission additional human grading to identify scoring inconsistencies
   - Adjust the 0.85 threshold with documented justification

## Current Status

**v1.0-launch — PASSED**  
- Overall: r=0.9338  
- Weakest category: Task Response r=0.8921  
- 24/29 essays scored (Band 8.5 tier incomplete — TPD exhaustion)  
- Approved: TETSOPGUIM Frank, 2026-03-15  
- Action: Complete Band 8.5 tier when Groq TPD resets  

## Consequences

- All prompt changes require a registered variant before running
- Maximum 3 tuning iterations prevents indefinite delay
- Escalation path ensures product lead is involved in threshold decisions
- Audit trail via `prompt_registry.py` links every score to exact prompt
