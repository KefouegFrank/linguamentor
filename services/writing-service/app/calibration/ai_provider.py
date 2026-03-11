"""
app/calibration/ai_provider.py

AIProvider abstraction — all LLM calls go through here, never direct SDK calls.
Swap providers by changing get_ai_provider(), nothing else touches.
"""

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod

from app.config import get_settings
from app.calibration.schemas import AIEvaluationResponse

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


def get_ai_provider() -> AIProviderBase:
    """
    Single entry point for provider selection.
    Calling code never instantiates a provider directly — always comes here.
    """
    settings = get_settings()

    if settings.openai_api_key:
        logger.debug("AI provider: OpenAI")
        return OpenAIProvider()

    if settings.anthropic_api_key:
        logger.warning("OpenAI key missing — falling back to Anthropic")
        return AnthropicProvider()

    raise RuntimeError(
        "No AI provider configured. "
        "Set LM_OPENAI_API_KEY or LM_ANTHROPIC_API_KEY in .env"
    )
