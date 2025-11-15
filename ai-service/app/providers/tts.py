import time
from typing import Any, Dict, Optional
import httpx
import backoff
from app.config import settings
from app.logging import log
from app.metrics import provider_call_duration_seconds


@backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
async def elevenlabs_tts(text: str, voice: Optional[str] = None, language: Optional[str] = None) -> bytes:
    if not settings.ELEVENLABS_API_KEY:
        return b"MOCK-AUDIO"
    voice_id = voice or "Bella"
    headers = {"xi-api-key": settings.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    body = {"text": text, "voice_settings": {"stability": 0.3, "similarity_boost": 0.7}}
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", headers=headers, json=body)
        resp.raise_for_status()
        audio = resp.content
    duration = time.perf_counter() - start
    provider_call_duration_seconds.observe(duration)
    return audio

