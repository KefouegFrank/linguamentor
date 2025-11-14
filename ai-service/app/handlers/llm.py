import os
from typing import Any, Dict
import httpx
import backoff
from app.models import LLMPayload
from app.config import settings
from app.logging import log


@backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
async def _openai_chat(payload: LLMPayload) -> Dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        # Fallback mock
        return {
            "model": payload.model or "mock-llm",
            "completion": f"[MOCK COMPLETION] {payload.prompt[:100]}...",
            "provider": "mock",
        }

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": payload.model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": payload.system or "You are a helpful assistant."},
            {"role": "user", "content": payload.prompt},
        ],
        "temperature": payload.temperature or 0.2,
    }

    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {
            "model": body["model"],
            "completion": content,
            "provider": "openai",
        }


async def handle_llm(payload: LLMPayload) -> Dict[str, Any]:
    log.info("handler.llm.start")
    result = await _openai_chat(payload)
    log.info("handler.llm.done")
    return result

