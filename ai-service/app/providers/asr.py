import time
from typing import Any, Dict, Optional
import httpx
import backoff
from app.config import settings
from app.logging import log
from app.metrics import provider_call_duration_seconds


@backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
async def deepgram_transcribe(audio_url: str, language: Optional[str] = None) -> Dict[str, Any]:
    if not settings.DEEPGRAM_API_KEY:
        return {"provider": "mock", "text": "[MOCK TRANSCRIPT]", "language": language or "en", "confidence": 0.9}
    headers = {"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"}
    params = {"language": language or "en"}
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post("https://api.deepgram.com/v1/listen", headers=headers, params=params, json={"url": audio_url})
        resp.raise_for_status()
        data = resp.json()
    duration = time.perf_counter() - start
    provider_call_duration_seconds.observe(duration)
    alt = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0]
    return {"provider": "deepgram", "text": alt.get("transcript", ""), "language": language or "en", "confidence": alt.get("confidence", 0.0)}


@backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
async def assemblyai_transcribe(audio_url: str, language: Optional[str] = None) -> Dict[str, Any]:
    if not settings.ASSEMBLYAI_API_KEY:
        return {"provider": "mock", "text": "[MOCK TRANSCRIPT]", "language": language or "en", "confidence": 0.9}
    headers = {"Authorization": settings.ASSEMBLYAI_API_KEY}
    body = {"audio_url": audio_url}
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post("https://api.assemblyai.com/v2/transcript", headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    duration = time.perf_counter() - start
    provider_call_duration_seconds.observe(duration)
    return {"provider": "assemblyai", "text": data.get("text", ""), "language": language or "en", "confidence": 0.0}

