"""
SQLAlchemy ORM model definitions — for Alembic autogenerate ONLY.
These mirror the schema in 003_core_platform_schema.sql exactly.

Runtime queries use raw asyncpg, not these models.
If you change a column here, Alembic detects the diff and generates
a migration. If you change the DB without updating this file, Alembic
will try to undo your change — so always keep these in sync.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.models.base import Base


# ---------------------------------------------------------------------------
# DOMAIN 1: IDENTITY & AUTH
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(320), nullable=False, unique=True)
    display_name = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, server_default="learner")
    subscription_tier = Column(String(20), nullable=False, server_default="free")
    voice_recording_consent = Column(Boolean, nullable=False, server_default="false")
    retraining_opt_out = Column(Boolean, nullable=False, server_default="false")
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    device_label = Column(String(100))
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# DOMAIN 2: LEARNER PROFILE
# ---------------------------------------------------------------------------

class LearnerProfile(Base):
    __tablename__ = "learner_profiles"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="CASCADE"), nullable=False, unique=True)
    target_language = Column(String(10), nullable=False, server_default="en")
    target_exam = Column(String(30))
    exam_date = Column(Date)
    accent_target = Column(String(10), nullable=False, server_default="en-US")
    default_persona = Column(String(20), nullable=False, server_default="companion")
    track = Column(String(20), nullable=False, server_default="fluency")
    cefr_writing = Column(String(5))
    cefr_speaking = Column(String(5))
    cefr_listening = Column(String(5))
    cefr_reading = Column(String(5))
    weakness_tags = Column(JSONB, nullable=False, server_default="[]")
    current_streak = Column(Integer, nullable=False, server_default="0")
    longest_streak = Column(Integer, nullable=False, server_default="0")
    last_session_date = Column(Date)
    placement_completed = Column(Boolean, nullable=False, server_default="false")
    placement_completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SkillVector(Base):
    __tablename__ = "skill_vectors"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="CASCADE"), nullable=False, unique=True)
    grammar = Column(Numeric(4, 3), nullable=False, server_default="0.0")
    vocabulary = Column(Numeric(4, 3), nullable=False, server_default="0.0")
    coherence = Column(Numeric(4, 3), nullable=False, server_default="0.0")
    pronunciation = Column(Numeric(4, 3), nullable=False, server_default="0.0")
    fluency = Column(Numeric(4, 3), nullable=False, server_default="0.0")
    comprehension = Column(Numeric(4, 3), nullable=False, server_default="0.0")
    # SRS interval tracking per dimension
    grammar_last_practiced_at = Column(DateTime(timezone=True))
    grammar_repetition_interval = Column(Integer, nullable=False, server_default="1")
    vocabulary_last_practiced_at = Column(DateTime(timezone=True))
    vocabulary_repetition_interval = Column(Integer, nullable=False, server_default="1")
    coherence_last_practiced_at = Column(DateTime(timezone=True))
    coherence_repetition_interval = Column(Integer, nullable=False, server_default="1")
    pronunciation_last_practiced_at = Column(DateTime(timezone=True))
    pronunciation_repetition_interval = Column(Integer, nullable=False, server_default="1")
    fluency_last_practiced_at = Column(DateTime(timezone=True))
    fluency_repetition_interval = Column(Integer, nullable=False, server_default="1")
    comprehension_last_practiced_at = Column(DateTime(timezone=True))
    comprehension_repetition_interval = Column(Integer, nullable=False, server_default="1")
    version = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# DOMAIN 6: AI INFRASTRUCTURE (defined before evaluation tables need FK)
# ---------------------------------------------------------------------------

class AIModelRun(Base):
    __tablename__ = "ai_model_runs"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(100))
    task_type = Column(String(50), nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    input_token_count = Column(Integer)
    output_token_count = Column(Integer)
    latency_ms = Column(Integer)
    streaming_first_token_ms = Column(Integer)
    response_hash = Column(String(64))
    user_reference_id = Column(UUID(as_uuid=True))  
    calibration_version = Column(String(50))
    calibration_sample_count = Column(Integer)      
    persona_config = Column(String(20))
    provider_name = Column(String(50))
    served_from_cache = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# DOMAIN 3: AI EVALUATION
# ---------------------------------------------------------------------------

class WritingSession(Base):
    __tablename__ = "writing_sessions"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    exam_type = Column(String(30), nullable=False)
    task_type = Column(String(30))
    essay_text = Column(Text, nullable=False)
    word_count = Column(Integer)
    status = Column(String(20), nullable=False, server_default="pending")
    score_task_response = Column(Numeric(4, 2))
    score_coherence = Column(Numeric(4, 2))
    score_lexical = Column(Numeric(4, 2))
    score_grammar = Column(Numeric(4, 2))
    score_overall = Column(Numeric(4, 2))
    cefr_level = Column(String(5))
    feedback_json = Column(JSONB)
    calibration_version = Column(String(50))
    calibration_correlation = Column(Numeric(4, 3))
    calibration_sample_count = Column(Integer)      
    ai_model_run_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.ai_model_runs.id", ondelete="SET NULL"))
    appeal_status = Column(String(20), nullable=False, server_default="none")
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SpeakingSession(Base):
    __tablename__ = "speaking_sessions"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    exam_type = Column(String(30))
    accent_target = Column(String(10), nullable=False, server_default="en-US")
    persona = Column(String(20), nullable=False, server_default="companion")
    duration_seconds = Column(Integer)
    pronunciation_score = Column(Numeric(4, 3))
    fluency_score = Column(Numeric(4, 3))
    grammar_score = Column(Numeric(4, 3))
    socratic_turns = Column(Integer, nullable=False, server_default="0")
    weakness_dimension = Column(String(30))
    audio_s3_key = Column(String(500))
    transcript_text = Column(Text)
    feedback_json = Column(JSONB)
    ai_model_run_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.ai_model_runs.id", ondelete="SET NULL"))
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# DOMAIN 4: ADAPTIVE ENGINE
# ---------------------------------------------------------------------------

class DailySession(Base):
    __tablename__ = "daily_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "session_date", name="uq_daily_sessions_user_date"),
        {"schema": "linguamentor"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    target_dimension = Column(String(30), nullable=False)
    content_json = Column(JSONB, nullable=False)
    session_date = Column(Date, nullable=False)
    completed = Column(Boolean, nullable=False, server_default="false")
    completed_at = Column(DateTime(timezone=True))
    skill_delta = Column(Numeric(5, 4))
    srs_priority_score = Column(Numeric(5, 4))        
    ai_model_run_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.ai_model_runs.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ScoreAppeal(Base):
    __tablename__ = "score_appeals"
    __table_args__ = (
        UniqueConstraint("writing_session_id", name="uq_appeals_writing_session"),
        UniqueConstraint("speaking_session_id", name="uq_appeals_speaking_session"),
        {"schema": "linguamentor"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    writing_session_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.writing_sessions.id"))
    speaking_session_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.speaking_sessions.id"))
    status = Column(String(20), nullable=False, server_default="pending")
    original_score = Column(Numeric(4, 2), nullable=False)
    secondary_score = Column(Numeric(4, 2))
    score_delta = Column(Numeric(4, 2))
    escalated_to_human = Column(Boolean, nullable=False, server_default="false")
    secondary_ai_model_run_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.ai_model_runs.id", ondelete="SET NULL"))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# DOMAIN 5: EXAM & PROGRESS
# ---------------------------------------------------------------------------

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    exam_type = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, server_default="init")
    overall_score = Column(Numeric(4, 2))
    cefr_level = Column(String(5))
    section_results_json = Column(JSONB)
    pdf_report_s3_key = Column(String(500))
    appeal_status = Column(String(20), nullable=False, server_default="none")
    last_autosave_at = Column(DateTime(timezone=True))
    deleted_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ExamSection(Base):
    __tablename__ = "exam_sections"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_attempt_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.exam_attempts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    section_type = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, server_default="not_started")
    prompt_text = Column(Text)
    response_text = Column(Text)
    score = Column(Numeric(4, 2))
    writing_session_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.writing_sessions.id"))
    speaking_session_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.speaking_sessions.id"))
    time_limit_seconds = Column(Integer)
    time_used_seconds = Column(Integer)
    submitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReadinessSnapshot(Base):
    __tablename__ = "readiness_snapshots"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    readiness_index = Column(Numeric(5, 4), nullable=False)
    projected_band = Column(Numeric(4, 2))
    confidence_interval = Column(Numeric(4, 2))
    delta_from_previous = Column(Numeric(5, 4))
    skill_vector_snapshot = Column(JSONB, nullable=False)
    trigger_event = Column(String(50))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ShareEvent(Base):
    __tablename__ = "share_events"
    __table_args__ = {"schema": "linguamentor"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.users.id", ondelete="RESTRICT"), nullable=False)
    exam_attempt_id = Column(UUID(as_uuid=True), ForeignKey("linguamentor.exam_attempts.id"))
    band_score = Column(Numeric(4, 2), nullable=False)
    delta = Column(Numeric(4, 2))                     
    platform = Column(String(30), nullable=False)
    converted_signup = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
