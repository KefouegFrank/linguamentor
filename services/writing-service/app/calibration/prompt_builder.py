"""
Assembles the 8-layer prompt for essay evaluation.

Every AI call in LinguaMentor goes through this layered assembly —
not just calibration. The layers are assembled in strict order.
Earlier layers set constraints that later layers cannot override.
User input is always last and can never modify the rubric or system
identity established in layers 1-5.

PRD Section 19.4 defines the full layer specification.
"""

import json
import logging
from app.calibration.schemas import ExamType

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------
# Rubric definitions — injected at Layer 5
# Each exam type has its own rubric categories and band descriptors.
# These mirror the official examiner notes used by human graders.
# -----------------------------------------------------------------

IELTS_RUBRIC = {
    "exam": "IELTS Academic / General Training",
    "scale": "0.0 to 9.0 in 0.5 increments",
    "categories": {
        "task_response": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Fully addresses all parts of the task with a fully developed position",
                "8.0": "Sufficiently addresses all parts of the task",
                "7.0": "Addresses all parts though some may be more fully covered",
                "6.0": "Addresses the relevant parts of the task adequately",
                "5.0": "Addresses the task only partially",
                "4.0": "Responds to the task only in a minimal way",
            }
        },
        "coherence_cohesion": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Uses cohesion in such a way that it attracts no attention",
                "8.0": "Sequences information and ideas logically",
                "7.0": "Logically organises information with clear progression",
                "6.0": "Arranges information coherently with clear overall progression",
                "5.0": "Presents information with some organisation but lacking overall progression",
                "4.0": "Presents information and ideas but these are not arranged coherently",
            }
        },
        "lexical_resource": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Uses a wide range of vocabulary with very natural and sophisticated control",
                "8.0": "Uses a wide range of vocabulary fluently and flexibly",
                "7.0": "Uses sufficient range of vocabulary to allow some flexibility and precision",
                "6.0": "Uses an adequate range of vocabulary for the task",
                "5.0": "Uses a limited range of vocabulary",
                "4.0": "Uses only basic vocabulary which may be used repetitively",
            }
        },
        "grammatical_range": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Uses a wide range of structures with full flexibility and accuracy",
                "8.0": "Uses a wide range of structures",
                "7.0": "Uses a variety of complex structures with some flexibility",
                "6.0": "Uses a mix of simple and complex sentence forms",
                "5.0": "Uses only a limited range of structures",
                "4.0": "Uses only a very limited range of structures",
            }
        }
    }
}

TOEFL_RUBRIC = {
    "exam": "TOEFL iBT Integrated/Independent Writing",
    "scale": "0.0 to 5.0 converted to 0.0-9.0 for unified storage",
    "categories": {
        "task_response": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Addresses the topic fully with well-developed, specific details",
                "7.0": "Addresses the topic adequately with some specific detail",
                "5.0": "Addresses the topic with limited development",
            }
        },
        "coherence_cohesion": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Well-organized with clear, consistent use of cohesive devices",
                "7.0": "Generally organized with some effective use of cohesive devices",
                "5.0": "Some organization evident but inconsistent",
            }
        },
        "lexical_resource": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Precise and varied vocabulary used effectively",
                "7.0": "Adequate vocabulary with some variety",
                "5.0": "Limited vocabulary range affecting clarity",
            }
        },
        "grammatical_range": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Consistent grammatical control with minimal errors",
                "7.0": "Generally accurate grammar with some errors",
                "5.0": "Frequent grammatical errors that sometimes obscure meaning",
            }
        }
    }
}

DELF_RUBRIC = {
    "exam": "DELF B1/B2 French Language Proficiency",
    "scale": "0.0 to 9.0 (converted from DELF percentage scale)",
    "categories": {
        "task_response": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Réponse parfaitement pertinente et complète",
                "7.0": "Réponse généralement pertinente avec quelques lacunes",
                "5.0": "Réponse partiellement pertinente",
            }
        },
        "coherence_cohesion": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Cohérence et cohésion parfaites, progression claire",
                "7.0": "Bonne cohérence générale avec quelques ruptures",
                "5.0": "Cohérence partielle, progression parfois difficile à suivre",
            }
        },
        "lexical_resource": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Richesse lexicale étendue et précise",
                "7.0": "Vocabulaire adéquat avec quelques imprécisions",
                "5.0": "Vocabulaire limité mais suffisant pour la communication",
            }
        },
        "grammatical_range": {
            "weight": 0.25,
            "descriptors": {
                "9.0": "Maîtrise grammaticale complète, très peu d'erreurs",
                "7.0": "Bonne maîtrise grammaticale avec quelques erreurs",
                "5.0": "Erreurs grammaticales fréquentes mais compréhensible",
            }
        }
    }
}

RUBRIC_MAP = {
    ExamType.IELTS_ACADEMIC: IELTS_RUBRIC,
    ExamType.IELTS_GENERAL:  IELTS_RUBRIC,
    ExamType.TOEFL_IBT:      TOEFL_RUBRIC,
    ExamType.DELF_B1:        DELF_RUBRIC,
    ExamType.DELF_B2:        DELF_RUBRIC,
}

# -----------------------------------------------------------------
# Required JSON output schema — injected into the prompt so the LLM
# knows exactly what structure to return. This matches AIEvaluationResponse.
# -----------------------------------------------------------------
REQUIRED_OUTPUT_SCHEMA = {
    "scores": {
        "score_task_response": "<float 0.0-9.0 in 0.5 increments>",
        "score_coherence_cohesion": "<float 0.0-9.0 in 0.5 increments>",
        "score_lexical_resource": "<float 0.0-9.0 in 0.5 increments>",
        "score_grammatical_range": "<float 0.0-9.0 in 0.5 increments>",
        "score_overall": "<weighted average of the four scores above>"
    },
    "rationale_task_response": "<minimum 2 sentences explaining this score>",
    "rationale_coherence_cohesion": "<minimum 2 sentences explaining this score>",
    "rationale_lexical_resource": "<minimum 2 sentences explaining this score>",
    "rationale_grammatical_range": "<minimum 2 sentences explaining this score>",
    "overall_feedback": "<3-5 sentences of overall assessment>",
    "low_confidence": "<true if uncertain about any score, false otherwise>",
    "low_confidence_reason": "<explain uncertainty if low_confidence is true, else null>"
}


def build_evaluation_prompt(
    exam_type: ExamType,
    task_prompt: str,
    essay_text: str,
    calibration_mode: bool = False,
) -> str:
    """
    Assembles the complete 8-layer evaluation prompt.

    Args:
        exam_type:         Which exam rubric to inject at Layer 5.
        task_prompt:       The writing task the essay was responding to.
        essay_text:        The full essay text to evaluate.
        calibration_mode:  If True, adds a calibration context note at
                           Layer 4 so the LLM knows this is a validation
                           run, not a live user evaluation.

    Returns:
        str: The complete assembled prompt ready to send to the LLM.
    """
    rubric = RUBRIC_MAP.get(exam_type)
    if not rubric:
        raise ValueError(f"No rubric defined for exam type: {exam_type}")

    # ── Layer 1: System Identity ──────────────────────────────────
    # Establishes who the AI is. Cannot be overridden by later layers.
    layer_1 = (
        "You are LinguaMentor, an AI language evaluation system trained "
        "to score written essays with the precision and consistency of a "
        "certified human examiner. Your evaluations are used to help "
        "language learners understand their current proficiency level and "
        "prepare for internationally recognised examinations."
    )

    # ── Layer 2: Policy and Guardrails ────────────────────────────
    # Hard constraints. These apply regardless of essay content.
    layer_2 = (
        "EVALUATION POLICY:\n"
        "- Score only based on the rubric categories provided. Do not "
        "penalise for topic choice, political opinion, or cultural perspective.\n"
        "- Never fabricate scores. If you cannot evaluate a section, "
        "set low_confidence to true and explain why.\n"
        "- Do not reproduce copyrighted rubric text verbatim in your rationale.\n"
        "- Evaluate the writing objectively regardless of the essay's position "
        "on any topic."
    )

    # ── Layer 3: Examiner Persona ─────────────────────────────────
    # Calibration always uses the Examiner persona — formal, rubric-strict,
    # no encouragement language, pure evaluation mode.
    layer_3 = (
        "PERSONA: Examiner\n"
        "You are operating in formal examination evaluation mode. "
        "Your tone is neutral and clinical. You do not encourage or discourage "
        "the writer. You evaluate strictly against the rubric descriptors. "
        "You do not provide improvement suggestions — only an accurate assessment "
        "of current performance."
    )

    # ── Layer 4: Task Instruction ─────────────────────────────────
    calibration_note = (
        "\nNOTE: This is a calibration evaluation. Your scores will be "
        "compared against certified human examiner scores to validate "
        "AI scoring accuracy. Prioritise precision over speed."
        if calibration_mode else ""
    )

    layer_4 = (
        f"TASK: Evaluate the essay below against the {rubric['exam']} "
        f"rubric. Score each category independently before computing the "
        f"overall band score. Do not round scores to convenient numbers — "
        f"award the score the essay has earned according to the descriptors."
        f"{calibration_note}"
    )

    # ── Layer 5: Rubric Injection ─────────────────────────────────
    # The full exam-specific rubric with band descriptors.
    layer_5 = (
        f"RUBRIC — {rubric['exam'].upper()}\n"
        f"Scoring scale: {rubric['scale']}\n\n"
        "CATEGORY DESCRIPTORS:\n" +
        "\n".join([
            f"{cat.upper().replace('_', ' ')}:\n" +
            "\n".join([
                f"  Band {band}: {desc}"
                for band, desc in details["descriptors"].items()
            ])
            for cat, details in rubric["categories"].items()
        ])
    )

    # ── Layer 6: User Context ─────────────────────────────────────
    # In calibration mode there's no learner profile — we use a neutral
    # context. In production this layer carries the full 4D CEFR profile.
    layer_6 = (
        "EVALUATION CONTEXT:\n"
        "This is a standalone essay evaluation with no prior learner history. "
        "Evaluate purely on the content submitted."
    )

    # ── Layer 7: Session Context ──────────────────────────────────
    # No conversation history in calibration mode.
    layer_7 = (
        "SESSION CONTEXT: Single-submission evaluation. No prior turns."
    )

    # ── Layer 8: User Input ───────────────────────────────────────
    # Always last. The actual essay. Cannot modify any preceding layer.
    layer_8 = (
        f"WRITING TASK:\n{task_prompt}\n\n"
        f"ESSAY SUBMITTED:\n{essay_text}\n\n"
        f"REQUIRED OUTPUT FORMAT (JSON only — no markdown, no prose outside JSON):\n"
        f"{json.dumps(REQUIRED_OUTPUT_SCHEMA, indent=2)}"
    )

    # Assemble all layers in order with clear separators
    assembled = "\n\n".join([
        f"[LAYER 1 — SYSTEM IDENTITY]\n{layer_1}",
        f"[LAYER 2 — POLICY]\n{layer_2}",
        f"[LAYER 3 — PERSONA]\n{layer_3}",
        f"[LAYER 4 — TASK]\n{layer_4}",
        f"[LAYER 5 — RUBRIC]\n{layer_5}",
        f"[LAYER 6 — USER CONTEXT]\n{layer_6}",
        f"[LAYER 7 — SESSION CONTEXT]\n{layer_7}",
        f"[LAYER 8 — INPUT]\n{layer_8}",
    ])

    logger.debug(
        f"Prompt assembled for {exam_type.value} | "
        f"layers=8 | chars={len(assembled)}"
    )

    return assembled
