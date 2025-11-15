import json
import hashlib
from typing import Any, Dict
from redis.asyncio import from_url as redis_from_url

from app.config import settings
from app.logging import log, _hash_value
from app.safety import check_text_safety, check_prompt_safety, SafetyError
from app.metrics import record_cache_hit, record_cache_miss
from app.providers import llm as llm_providers
from app.providers import asr as asr_providers
from app.providers import tts as tts_providers
from app.s3_utils import download_presigned, upload_presigned


def _cache_key(job_type: str, payload: Dict[str, Any]) -> str:
    s = json.dumps({"type": job_type, "payload": payload}, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class AIModelRouter:
    def __init__(self):
        self.redis = redis_from_url(settings.REDIS_URL)

    async def _get_cache(self, key: str) -> Dict[str, Any] | None:
        try:
            raw = await self.redis.get(f"ai-cache:{key}")
            if not raw:
                return None
            return json.loads(raw)
        except Exception:
            return None

    async def _set_cache(self, key: str, value: Dict[str, Any]) -> None:
        try:
            await self.redis.setex(f"ai-cache:{key}", 86400, json.dumps(value))
        except Exception:
            pass

    async def run(self, job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Safety checks based on job type
        try:
            if job_type in {"llm", "translate", "summarize", "grammar", "score"}:
                text = payload.get("text") or payload.get("prompt") or ""
                if text:
                    check_text_safety(job_type, text)
                prompt = payload.get("prompt") or ""
                if prompt:
                    check_prompt_safety(prompt)
        except SafetyError as se:
            raise ValueError(str(se))

        # Caching for specific job types
        cacheable = job_type in {"translate", "summarize", "grammar", "score", "llm"}
        key = _cache_key(job_type, payload) if cacheable else None
        if cacheable:
            cached = await self._get_cache(key)  # type: ignore[arg-type]
            if cached:
                record_cache_hit(job_type)
                return cached
            else:
                record_cache_miss(job_type)

        provider = settings.MODEL_PROVIDER.lower()

        if job_type == "llm":
            result = await llm_providers.chat_completion(
                prompt=payload.get("prompt", ""),
                system=payload.get("system"),
                model=payload.get("model"),
                temperature=payload.get("temperature"),
            )
        elif job_type == "translate":
            result = await llm_providers.translation(
                text=payload.get("text", ""),
                target_language=payload.get("target_language", "en"),
                model=payload.get("model"),
            )
        elif job_type == "summarize":
            result = await llm_providers.summarization(
                text=payload.get("text", ""),
                max_words=payload.get("max_words", 120),
                model=payload.get("model"),
            )
        elif job_type == "grammar":
            result = await llm_providers.grammar_correction(
                text=payload.get("text", ""),
                model=payload.get("model"),
            )
        elif job_type == "score":
            audio_url = payload.get("audio_url")
            if audio_url:
                # Speaking: ASR -> transcript -> LLM scoring
                asr_res = None
                if settings.DEEPGRAM_API_KEY:
                    asr_res = await asr_providers.deepgram_transcribe(audio_url, payload.get("language"))
                else:
                    asr_res = await asr_providers.assemblyai_transcribe(audio_url, payload.get("language"))
                transcript = asr_res.get("text", "")
                check_text_safety("score_speaking", transcript)
                score_res = await llm_providers.general_scoring(
                    text=transcript,
                    rubric_hint=payload.get("rubric"),
                    model=payload.get("model"),
                )
                result = {**score_res, "transcript": transcript}
            else:
                # Writing: direct LLM scoring
                result = await llm_providers.general_scoring(
                    text=payload.get("text", ""),
                    rubric_hint=payload.get("rubric"),
                    model=payload.get("model"),
                )
        elif job_type == "asr":
            audio_url = payload.get("audio_url")
            if not audio_url:
                # Expect presigned URL provided by backend; if missing, fail fast
                raise ValueError("Missing audio_url for ASR job.")
            # Try Deepgram then AssemblyAI
            if settings.DEEPGRAM_API_KEY:
                result = await asr_providers.deepgram_transcribe(audio_url, payload.get("language"))
            else:
                result = await asr_providers.assemblyai_transcribe(audio_url, payload.get("language"))
        elif job_type == "tts":
            upload_url = payload.get("upload_url")
            if not upload_url:
                raise ValueError("Missing upload_url for TTS job.")
            # Generate audio via ElevenLabs by default
            audio_bytes = await tts_providers.elevenlabs_tts(
                text=payload.get("text", ""),
                voice=payload.get("voice"),
                language=payload.get("language"),
            )
            url, status = await upload_presigned(upload_url, audio_bytes, content_type="audio/mpeg")
            result = {
                "provider": "elevenlabs" if settings.ELEVENLABS_API_KEY else "mock",
                "model": "tts",
                "audio_url": url,
                "status": status,
            }
        else:
            raise ValueError(f"Unsupported job type: {job_type}")

        # Normalize & set cache
        result.setdefault("provider", provider)
        result.setdefault("model", payload.get("model") or "default")
        if cacheable:
            await self._set_cache(key, result)  # type: ignore[arg-type]
        return result


router = AIModelRouter()
