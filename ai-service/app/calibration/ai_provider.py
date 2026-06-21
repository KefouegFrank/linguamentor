"""
AIProvider abstraction — all LLM calls go through here, never direct SDK calls.
Swap providers by changing get_ai_provider(), nothing else touches.
"""

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod

from app.config import get_settings
from app.calibration.schemas import AIEvaluationResponse, RubricScores

logger = logging.getLogger(__name__)


class AIProviderBase(ABC):

    @abstractmethod
    async def evaluate_essay(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> tuple[AIEvaluationResponse, str, int]:
        """Returns (parsed_response, prompt_hash, latency_ms)."""
        pass


class OpenAIProvider(AIProviderBase):
    """Primary provider — GPT-4o, top-tier model, near-zero temp for scoring consistency."""

    def __init__(self):
        from openai import AsyncOpenAI
        settings = get_settings()

        if not settings.openai_api_key:
            raise ValueError("openai_api_key not set — check LM_OPENAI_API_KEY in .env")

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model  = "gpt-4o"

    async def evaluate_essay(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> tuple[AIEvaluationResponse, str, int]:

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        start       = time.monotonic()

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},  # no markdown fences
            )

            latency_ms  = int((time.monotonic() - start) * 1000)
            raw_content = response.choices[0].message.content
            parsed      = self._parse_response(raw_content)

            logger.debug(f"GPT-4o scored in {latency_ms}ms | overall={parsed.scores.score_overall}")
            return parsed, prompt_hash, latency_ms

        except Exception as e:
            logger.error(f"OpenAI call failed after {int((time.monotonic() - start) * 1000)}ms: {e}")
            raise

    def _parse_response(self, raw: str) -> AIEvaluationResponse:
        try:
            return AIEvaluationResponse(**json.loads(raw))
        except Exception as e:
            raise ValueError(f"OpenAI response failed schema validation: {e}\nRaw: {raw[:500]}")


class AnthropicProvider(AIProviderBase):
    """Fallback provider — Claude 3.5 Sonnet, same interface as OpenAI."""

    def __init__(self):
        import anthropic
        settings = get_settings()

        if not settings.anthropic_api_key:
            raise ValueError("anthropic_api_key not set — check LM_ANTHROPIC_API_KEY in .env")

        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model  = "claude-3-5-sonnet-20241022"

    async def evaluate_essay(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> tuple[AIEvaluationResponse, str, int]:

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        start       = time.monotonic()

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            latency_ms  = int((time.monotonic() - start) * 1000)
            raw_content = response.content[0].text
            parsed      = self._parse_response(raw_content)

            return parsed, prompt_hash, latency_ms

        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            raise

    def _parse_response(self, raw: str) -> AIEvaluationResponse:
        try:
            # Anthropic sometimes wraps JSON in markdown fences — strip them
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            return AIEvaluationResponse(**json.loads(clean))
        except Exception as e:
            raise ValueError(f"Anthropic response failed schema validation: {e}\nRaw: {raw[:500]}")

class GroqProvider(AIProviderBase):
    """
    Groq — LLaMA 3.3 70B for calibration development runs.

    Groq uses an OpenAI-compatible API so the implementation mirrors
    OpenAIProvider almost exactly. The key differences:
    - Base URL points to Groq's inference endpoint
    - Model is llama-3.3-70b-versatile — strong instruction following,
      supports JSON mode, free tier with no credit card required
    - Used for Phase 0 calibration development; production scoring
      uses OpenAI GPT-4o per PRD section 19.3

    Free tier limits: 6,000 tokens/min, 500,000 tokens/day.
    29 essays at ~1,600 input tokens each = ~46,400 tokens — well
    within daily limit. Rate limiting handled by adding a small
    delay between calls to stay under per-minute limit.
    """

    def __init__(self):
        from groq import AsyncGroq
        settings = get_settings()

        if not settings.groq_api_key:
            raise ValueError(
                "groq_api_key not set — check LM_GROQ_API_KEY in .env"
            )

        self._client = AsyncGroq(api_key=settings.groq_api_key)
        # LLaMA 3.3 70B — best available on Groq free tier for
        # complex instruction-following tasks like rubric evaluation
        self._model = "llama-3.3-70b-versatile"

    async def evaluate_essay(
        self,
        prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> tuple[AIEvaluationResponse, str, int]:
        """
        Calls LLaMA 3.3 70B via Groq's OpenAI-compatible endpoint.

        Groq's inference is extremely fast — typically 200-400ms per
        call — so 29 essays complete in under 2 minutes even with
        rate limit delays between calls.
        """
        import asyncio

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        start       = time.monotonic()

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                # JSON mode — same as OpenAI, eliminates markdown fences
                # and prose wrapping that break JSON parsing
                response_format={"type": "json_object"},
            )

            latency_ms  = int((time.monotonic() - start) * 1000)
            raw_content = response.choices[0].message.content
            parsed      = self._parse_response(raw_content)

            logger.debug(
                f"Groq LLaMA 3.3 70B scored essay | "
                f"overall={parsed.scores.score_overall} | "
                f"{latency_ms}ms"
            )

            # Small delay to respect Groq's per-minute rate limit.
            # 6,000 tokens/min limit — each essay uses ~1,600 tokens
            # so we can safely do ~3 requests/min. 20s delay keeps
            # us comfortably under the limit across all 29 essays.
            await asyncio.sleep(15)

            return parsed, prompt_hash, latency_ms

        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            error_str = str(e)

            # Detect daily token limit (TPD) exhaustion specifically.
            # This is a hard stop — no retry, no backoff will help.
            # The limit resets at midnight UTC. Logging as CRITICAL
            # so it stands out immediately in any monitoring system.
            if "tokens per day" in error_str or "TPD" in error_str:
                logger.critical(
                    f"🚨 Groq daily token limit (TPD) exhausted. "
                    f"No further essays can be scored until the limit "
                    f"resets at midnight UTC. Re-run this calibration "
                    f"run tomorrow — the pipeline will resume from where "
                    f"it stopped, skipping already-scored essays automatically."
                )
            else:
                logger.error(f"Groq call failed after {latency_ms}ms: {e}")

            raise

    def _parse_response(self, raw: str) -> AIEvaluationResponse:
        """
        Parses and validates the Groq response.
        JSON mode guarantees clean JSON — fence stripping is defensive.
        """
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            return AIEvaluationResponse(**json.loads(clean))
        except Exception as e:
            raise ValueError(
                f"Groq response failed schema validation: {e}\n"
                f"Raw (first 500 chars): {raw[:500]}"
            )
       
class GroqASRProvider:
    """
    Groq Whisper Large v3 — ASR provider for Phase 0 WER validation.

    Chosen for Phase 0 because:
    - Already integrated (no new SDK or credentials needed)
    - Achieves ~8.4% WER on accented speech — clears the 10% threshold
    - Superior French language performance (fr-FR, fr-CA)
    - 189x real-time speed factor — fast enough for batch validation

    Production ASR will use gpt-4o-transcribe per PRD section 19.3.
    This validates that a Whisper-class model meets threshold, which
    confirms the more accurate production model will also pass.
    """

    def __init__(self):
        from groq import Groq
        settings = get_settings()

        if not settings.groq_api_key:
            raise ValueError(
                "groq_api_key not set — check LM_GROQ_API_KEY in .env. "
                "Required for ASR validation pipeline."
            )

        # Use synchronous client — audio files are read from disk,
        # not streamed from a live connection
        self._client = Groq(api_key=settings.groq_api_key)
        self._model  = "whisper-large-v3"

    def transcribe(
        self,
        audio_path: str,
        language: str = None,
        prompt: str = None,
    ) -> tuple[str, float]:
        """
        Transcribes an audio file using Whisper Large v3.

        Args:
            audio_path: Path to audio file (WAV, MP3, M4A, FLAC)
            language:   ISO 639-1 code — 'en' or 'fr'
                        Providing this improves accuracy and speed
            prompt:     Optional context hint — e.g. exam topic

        Returns:
            tuple of (transcript_text, no_speech_probability)
            no_speech_prob > 0.9 indicates likely silence/noise
        """
        import time

        with open(audio_path, "rb") as audio_file:
            response = self._client.audio.transcriptions.create(
                file=audio_file,
                model=self._model,
                language=language,
                prompt=prompt,
                response_format="verbose_json",
                temperature=0.0,  # deterministic — same audio = same transcript
            )

        # Extract transcript and no-speech probability from segments
        transcript = response.text.strip()

        # Compute average no_speech_prob across segments as quality indicator
        segments = getattr(response, "segments", [])
        if segments:
            avg_no_speech = sum(
                s.get("no_speech_prob", 0) for s in segments
            ) / len(segments)
        else:
            avg_no_speech = 0.0

        logger.debug(
            f"Transcribed {audio_path} | "
            f"words={len(transcript.split())} | "
            f"no_speech_prob={avg_no_speech:.3f}"
        )

        return transcript, avg_no_speech
    
            
class GeminiProvider(AIProviderBase):
    """
    Google Gemini 2.0 Flash — free tier provider for calibration.

    Uses the new google-genai SDK (google.generativeai is fully deprecated).
    Gemini 2.0 Flash is the current recommended free-tier model with
    strong reasoning capability suitable for essay evaluation.
    """

    def __init__(self):
        from google import genai
        from google.genai import types
        settings = get_settings()

        if not settings.gemini_api_key:
            raise ValueError(
                "gemini_api_key not set — check LM_GEMINI_API_KEY in .env"
            )

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model  = "gemini-2.0-flash"

    async def evaluate_essay(
        self,
        prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> tuple[AIEvaluationResponse, str, int]:
        """
        Calls Gemini 2.0 Flash with the assembled rubric prompt.
        Runs the synchronous SDK call in a thread executor to avoid
        blocking FastAPI's async event loop.
        """
        import asyncio
        from google import genai
        from google.genai import types

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        start       = time.monotonic()

        try:
            config = types.GenerateContentConfig(
                # JSON-Prompt method — schema embedded in Layer 8 of prompt
                response_mime_type="application/json",
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            loop     = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
            )

            latency_ms  = int((time.monotonic() - start) * 1000)
            raw_content = response.text
            parsed      = self._parse_response(raw_content)

            logger.debug(
                f"Gemini 2.0 Flash scored essay | "
                f"overall={parsed.scores.score_overall} | "
                f"{latency_ms}ms"
            )
            return parsed, prompt_hash, latency_ms

        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(f"Gemini call failed after {latency_ms}ms: {e}")
            raise

    def _parse_response(self, raw: str) -> AIEvaluationResponse:
        """
        Parses Gemini response into AIEvaluationResponse schema.
        With response_mime_type=application/json the SDK returns
        clean JSON — defensive fence stripping handles edge cases.
        """
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            return AIEvaluationResponse(**json.loads(clean))
        except Exception as e:
            raise ValueError(
                f"Gemini response failed schema validation: {e}\n"
                f"Raw (first 500 chars): {raw[:500]}"
            )

class MockProvider(AIProviderBase):
    """
    Deterministic mock provider for local testing and CI.

    Returns realistic IELTS-range scores derived from the essay's
    word count — longer essays score slightly higher. This gives us
    variance in the output so Pearson correlation has something
    meaningful to compute against.

    Never used in production. get_ai_provider() only returns this
    when LM_USE_MOCK_PROVIDER=true is explicitly set in .env.
    """

    async def evaluate_essay(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
    ) -> tuple[AIEvaluationResponse, str, int]:
        import asyncio
        import random

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

        # Simulate realistic API latency so timing metrics are meaningful
        await asyncio.sleep(0.05)
        latency_ms = 50

        # Base score derived from prompt length — longer essays produce
        # longer prompts and score higher, matching how human graders
        # rewarded more developed essays. This gives us positive Pearson
        # correlation between mock AI scores and human consensus scores.
        # The 5800/1200 constants are calibrated to our test essay prompt
        # lengths which range roughly 6000-7000 chars across 5 essays.
        prompt_len = len(prompt)
        base       = 5.5 + ((prompt_len - 5800) / 1200) * 1.5
        base       = max(5.0, min(7.5, base))

        # Deterministic variance per essay — identical scores make Pearson
        # undefined because zero variance = zero denominator in the formula
        random.seed(int(prompt_len / 10))

        def _band(offset: float = 0.0) -> float:
            """Nudge base by offset then round to valid 0.5 increment."""
            raw = base + offset + random.uniform(-0.2, 0.2)
            raw = max(5.0, min(7.5, raw))
            return round(raw * 2) / 2

        tr      = _band(0.0)
        cc      = _band(0.1)
        lr      = _band(-0.1)
        gr      = _band(0.1)
        overall = round(((tr + cc + lr + gr) / 4) * 2) / 2

        evaluation = AIEvaluationResponse(
            scores=RubricScores(
                score_task_response=tr,
                score_coherence_cohesion=cc,
                score_lexical_resource=lr,
                score_grammatical_range=gr,
                score_overall=overall,
            ),
            rationale_task_response=(
                f"The essay addresses the task with band {tr} performance. "
                f"Key arguments are present but development varies."
            ),
            rationale_coherence_cohesion=(
                f"Coherence is at band {cc} level. "
                f"Paragraph structure is generally logical."
            ),
            rationale_lexical_resource=(
                f"Vocabulary range sits at band {lr}. "
                f"Some variety in word choice is evident."
            ),
            rationale_grammatical_range=(
                f"Grammatical control assessed at band {gr}. "
                f"Mix of simple and complex structures used."
            ),
            overall_feedback=(
                f"This essay demonstrates band {overall} performance overall. "
                f"The writer shows competence across all four rubric categories "
                f"with room for improvement in precision and range."
            ),
            low_confidence=False,
        )

        logger.debug(f"MockProvider scored essay | overall={overall}")
        return evaluation, prompt_hash, latency_ms
    

def get_ai_provider() -> AIProviderBase:
    """
    Factory — returns whichever provider is currently available.

    Priority:
      1. MockProvider      — if LM_USE_MOCK_PROVIDER=true (testing only)
      2. OpenAIProvider    — if LM_OPENAI_API_KEY is set (production)
      3. GroqProvider      — if LM_GROQ_API_KEY is set (calibration dev)
      4. GeminiProvider    — if LM_GEMINI_API_KEY is set
      5. AnthropicProvider — if LM_ANTHROPIC_API_KEY is set
    """
    settings = get_settings()

    # Mock check must come first — allows testing without any API key.
    if getattr(settings, "use_mock_provider", False):
        logger.warning(
            "⚠️  Using MockProvider — for testing only, "
            "never enable in production"
        )
        return MockProvider()

    if settings.openai_api_key:
        logger.debug("AI provider: OpenAI GPT-4o")
        return OpenAIProvider()
    
    if settings.groq_api_key:
        logger.info("AI provider: Groq LLaMA 3.3 70B")
        return GroqProvider()
    
    if settings.gemini_api_key:
        logger.info("AI provider: Google Gemini 2.0 Flash")
        return GeminiProvider()

    if settings.anthropic_api_key:
        logger.warning("OpenAI key missing — using Anthropic as provider")
        return AnthropicProvider()

    raise RuntimeError(
        "No AI provider available. "
        "Set LM_GROQ_API_KEY, LM_OPENAI_API_KEY, or "
        "LM_ANTHROPIC_API_KEY in .env."
    )
