"""
Versioned registry of rubric prompt configurations.

Every prompt variant used in a calibration run is registered here
with a version label, description, and the specific changes made
from the previous version. When a run fails the 0.85 threshold,
the tuning protocol specifies which layer to modify and how to
register the new variant before re-running.

The prompt_hash stored in calibration_ai_scores ties each score
to the exact prompt that produced it. This registry makes that
hash human-readable — you can look up any hash and know exactly
what prompt configuration was used.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Optional
from app.calibration.schemas import ExamType

logger = logging.getLogger(__name__)


@dataclass
class PromptVariant:
    """
    Describes one versioned prompt configuration.

    version_label:  human-readable identifier e.g. 'v1.0-launch', 'v1.1-tr-rubric'
    description:    what changed from the previous version and why
    layer_modified: which of the 8 prompt layers was changed (None = initial version)
    change_rationale: what correlation failure motivated this change
    """
    version_label:    str
    description:      str
    layer_modified:   Optional[int]  = None
    change_rationale: Optional[str]  = None
    notes:            list[str]      = field(default_factory=list)


# Registry of all prompt variants used in calibration history.
# Add a new entry here whenever a prompt change is made before re-running.
# Never delete entries — this is an immutable audit trail.
PROMPT_VARIANT_REGISTRY: dict[str, PromptVariant] = {
    "v1.0-launch": PromptVariant(
        version_label="v1.0-launch",
        description=(
            "Initial calibration prompt. 8-layer structure with IELTS Academic "
            "rubric injected at Layer 5. Band descriptors for bands 4.0-9.0 "
            "across all four categories."
        ),
        layer_modified=None,
        change_rationale=None,
        notes=[
            "Achieved r=0.9338 overall on 24 essays across bands 4.5-8.0",
            "Task Response weakest at r=0.8921 — still above 0.85 threshold",
            "Band 8.5 tier incomplete due to Groq TPD exhaustion",
            "Pearson gate PASSED. MAE gate not yet implemented at time of run.",
            "Post-hoc analysis: overall MAE=1.177 — systematic +1.1 band overscoring detected",
            "Approved by TETSOPGUIM Frank — superseded by v1.1-bias-correction",
        ]
    ),

    "v1.1-bias-correction": PromptVariant(
        version_label="v1.1-bias-correction",
        description=(
            "Layer 4 bias correction. Added explicit anti-inflation anchors: "
            "realistic band distribution reminder (most test-takers score 5.0-7.0), "
            "lower-band-on-doubt rule, explicit prohibition on generosity rounding. "
            "Layer 5 rubric descriptors unchanged."
        ),
        layer_modified=4,
        change_rationale=(
            "v1.0-launch post-hoc analysis showed AI scoring 1.0-1.4 bands above "
            "human consensus across all categories (overall MAE=1.177). "
            "Pearson gate passed (r=0.9338) confirming strong directional accuracy, "
            "but systematic positive bias would mislead learners about their true band. "
            "MAE gate added at threshold 0.5 — this version must pass both gates."
        ),
        notes=[
            "Target: MAE ≤ 0.5 bands overall",
            "Pearson must remain ≥ 0.85 — bias fix must not reduce correlation",
            "Layer 4 modified only — rubric descriptors unchanged at Layer 5",
            "Run after Groq TPD resets — includes Band 8.5 tier completion",
        ]
    ),
}

def get_variant_by_label(label: str) -> Optional[PromptVariant]:
    """Returns the prompt variant for a given version label."""
    return PROMPT_VARIANT_REGISTRY.get(label)


def register_new_variant(
    version_label: str,
    description: str,
    layer_modified: int,
    change_rationale: str,
    notes: list[str] = None,
) -> PromptVariant:
    """
    Registers a new prompt variant before a tuning run.

    Called by the developer before running calibration with a modified
    prompt. The version_label must match the LM_CALIBRATION_VERSION
    value set in .env for the tuning run so scores can be traced back
    to this registry entry.

    Raises ValueError if the label already exists — variants are
    immutable once registered.
    """
    if version_label in PROMPT_VARIANT_REGISTRY:
        raise ValueError(
            f"Prompt variant '{version_label}' already exists. "
            f"Choose a new version label for this tuning iteration."
        )

    variant = PromptVariant(
        version_label=version_label,
        description=description,
        layer_modified=layer_modified,
        change_rationale=change_rationale,
        notes=notes or [],
    )
    PROMPT_VARIANT_REGISTRY[version_label] = variant
    logger.info(f"Registered new prompt variant: {version_label}")
    return variant


def compute_prompt_fingerprint(prompt: str) -> str:
    """
    Returns SHA-256 hash of a prompt string.
    Matches the prompt_hash stored in calibration_ai_scores.
    Use this to verify a prompt variant produces the expected hash.
    """
    return hashlib.sha256(prompt.encode()).hexdigest()
