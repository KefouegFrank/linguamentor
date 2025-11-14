from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class JobEnvelope(BaseModel):
    jobId: str = Field(..., description="Backend job ID")
    type: Literal[
        "asr",
        "tts",
        "llm",
        "translate",
        "summarize",
        "grammar",
        "score",
        "echo",
    ]
    payload: Dict[str, Any]


class ASRPayload(BaseModel):
    audio_s3_key: str
    language: Optional[str] = None
    user_id: Optional[str] = None


class TTSPayload(BaseModel):
    text: str
    voice: Optional[str] = None
    language: Optional[str] = None
    user_id: Optional[str] = None


class LLMPayload(BaseModel):
    prompt: str
    system: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.2
    user_id: Optional[str] = None


class TranslationPayload(BaseModel):
    text: str
    target_language: str
    user_id: Optional[str] = None


class SummarizationPayload(BaseModel):
    text: str
    max_words: Optional[int] = 120
    user_id: Optional[str] = None


class GrammarPayload(BaseModel):
    text: str
    user_id: Optional[str] = None


class ScorePayload(BaseModel):
    text: str
    rubric: Optional[str] = None
    user_id: Optional[str] = None

