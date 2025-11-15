import time
import json
from typing import Any, Dict, Optional
import httpx
import backoff
from app.config import settings
from app.logging import log
from app.metrics import provider_call_duration_seconds


def _sys_default() -> str:
    return "You are a helpful assistant for language learning. Respond concisely in JSON when requested."


@backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
async def chat_completion(prompt: str, system: Optional[str] = None, model: Optional[str] = None, temperature: Optional[float] = 0.2) -> Dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        return {"provider": "mock", "model": model or "mock-llm", "completion": f"[MOCK] {prompt[:120]}"}

    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system or _sys_default()},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature or 0.2,
    }
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    duration = time.perf_counter() - start
    provider_call_duration_seconds.observe(duration)
    content = data["choices"][0]["message"]["content"]
    return {"provider": "openai", "model": body["model"], "completion": content}


async def grammar_correction(text: str, model: Optional[str] = None) -> Dict[str, Any]:
    prompt = (
        "You will correct grammar and spelling. Return JSON with keys: correctedText, issues[]. "
        "Each issue has type and description. Input:\n\n" + text
    )
    result = await chat_completion(prompt, system=_sys_default(), model=model, temperature=0.0)
    try:
        parsed = json.loads(result["completion"])
    except Exception:
        parsed = {"correctedText": text, "issues": []}
    return {"provider": result["provider"], "model": result["model"], **parsed}


async def translation(text: str, target_language: str, model: Optional[str] = None) -> Dict[str, Any]:
    prompt = f"Translate the following text into {target_language}. Return JSON: translatedText.\n\n{text}"
    result = await chat_completion(prompt, system=_sys_default(), model=model, temperature=0.2)
    try:
        parsed = json.loads(result["completion"])
    except Exception:
        parsed = {"translatedText": text}
    parsed["targetLanguage"] = target_language
    return {"provider": result["provider"], "model": result["model"], **parsed}


async def summarization(text: str, max_words: int = 120, model: Optional[str] = None) -> Dict[str, Any]:
    prompt = f"Summarize in at most {max_words} words. Return JSON: summary.\n\n{text}"
    result = await chat_completion(prompt, system=_sys_default(), model=model, temperature=0.5)
    try:
        parsed = json.loads(result["completion"])
    except Exception:
        parsed = {"summary": text[:max_words]}
    return {"provider": result["provider"], "model": result["model"], **parsed}


async def general_scoring(text: str, rubric_hint: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    prompt = (
        "Score the text based on rubric. Return JSON: score(number 0-10), rubric(object), feedback(string). "
        "Rubric sections: grammar, coherence, vocabulary, structure. Provide numbers 0-10.\n\n"
        + (f"Rubric hint: {rubric_hint}\n" if rubric_hint else "")
        + f"Text:\n{text}"
    )
    result = await chat_completion(prompt, system=_sys_default(), model=model, temperature=0.2)
    try:
        parsed = json.loads(result["completion"])
    except Exception:
        parsed = {
            "score": 5.0,
            "rubric": {"grammar": 5, "coherence": 5, "vocabulary": 5, "structure": 5},
            "feedback": "Basic scoring fallback.",
        }
    return {"provider": result["provider"], "model": result["model"], **parsed}

