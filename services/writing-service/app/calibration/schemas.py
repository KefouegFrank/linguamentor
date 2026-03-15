"""
Pydantic models for the calibration pipeline.

Every AI response is validated against these schemas before anything
gets written to the database. If the LLM returns malformed JSON or
missing fields, we catch it here — not halfway through a database
write that leaves partial data behind.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class ExamType(str, Enum):
    """
    Supported exam types — mirrors the CHECK constraint in the DB schema.
    Using an Enum means typos fail at the Python layer, not the DB layer.
    """
    IELTS_ACADEMIC  = "ielts_academic"
    IELTS_GENERAL   = "ielts_general"
    TOEFL_IBT       = "toefl_ibt"
    DELF_B1         = "delf_b1"
    DELF_B2         = "delf_b2"


class RubricScores(BaseModel):
    """
    The four rubric category scores the AI must return for every essay.
    Mirrors calibration_ai_scores and calibration_human_scores columns
    exactly — same names, same scale, same constraints.

    Scores are on the IELTS 0.0-9.0 band scale in 0.5 increments.
    DELF percentage scores are converted to this scale before storage
    so all exam types are comparable in one unified table.
    """
    score_task_response:      float = Field(ge=0.0, le=9.0)
    score_coherence_cohesion: float = Field(ge=0.0, le=9.0)
    score_lexical_resource:   float = Field(ge=0.0, le=9.0)
    score_grammatical_range:  float = Field(ge=0.0, le=9.0)
    score_overall:            float = Field(ge=0.0, le=9.0)


    @field_validator(
        "score_task_response",
        "score_coherence_cohesion",
        "score_lexical_resource",
        "score_grammatical_range",
        "score_overall",
    )
    @classmethod
    def must_be_half_band_increment(cls, v: float) -> float:
        """
        IELTS scores are awarded in 0.5 increments only.
        If the model returns an arithmetic mean like 8.875, we round
        to the nearest 0.5 rather than rejecting — the scoring intent
        is correct, only the rounding convention is off.
        Auto-rounding is the correct professional decision here:
        rejecting a valid score of 8.875 (clearly meaning 9.0) wastes
        API calls and produces no better calibration data.
        """
        rounded = round(v * 2) / 2
        return max(0.0, min(9.0, rounded))


class AIEvaluationResponse(BaseModel):
    """
    The complete structured response the AI must return for each essay.

    This schema is injected into the prompt as the required output format.
    Every response is validated against it before scores are stored.
    If validation fails, we retry with a correction instruction — never
    store a partially valid response.
    """
    scores:     RubricScores

    # Per-category rationale — used during rubric tuning to understand
    # why the AI scored the way it did when it diverges from human graders
    rationale_task_response:      str = Field(min_length=10)
    rationale_coherence_cohesion: str = Field(min_length=10)
    rationale_lexical_resource:   str = Field(min_length=10)
    rationale_grammatical_range:  str = Field(min_length=10)

    # Overall feedback summary — stored in raw_response for debugging
    overall_feedback: str = Field(min_length=20)

    # Confidence flag — if the AI is uncertain about a score it sets
    # this to True. We log these for manual review during tuning.
    low_confidence: bool = False
    low_confidence_reason: Optional[str] = None


class CalibrationEssayRecord(BaseModel):
    """
    Represents one essay fetched from calibration_essays for scoring.
    Used to pass data cleanly between pipeline stages.
    """
    id:           str
    exam_type:    ExamType
    task_prompt:  str
    essay_text:   str
    word_count:   int


class HumanConsensusScore(BaseModel):
    """
    The consensus human score for one essay —
    average of two agreeing examiners.
    Used by the Pearson computation engine in C3.
    """
    essay_id:                 str
    score_task_response:      float
    score_coherence_cohesion: float
    score_lexical_resource:   float
    score_grammatical_range:  float
    score_overall:            float
