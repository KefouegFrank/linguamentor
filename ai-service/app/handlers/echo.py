from typing import Any, Dict
from app.models import (
    TranslationPayload,
    SummarizationPayload,
    GrammarPayload,
    ScorePayload,
)
from app.logging import log


async def handle_echo(payload: Dict[str, Any]) -> Dict[str, Any]:
    log.info("handler.echo")
    # Echo handler for end-to-end testing
    return {"echo": True, "payload_shape": list(payload.keys())}


async def handle_translate(payload: TranslationPayload) -> Dict[str, Any]:
    log.info("handler.translate.start")
    return {
        "translatedText": f"[MOCK] {payload.text[:50]} -> {payload.target_language}",
        "targetLanguage": payload.target_language,
        "provider": "mock",
    }


async def handle_summarize(payload: SummarizationPayload) -> Dict[str, Any]:
    log.info("handler.summarize.start")
    return {
        "summary": f"[MOCK SUMMARY up to {payload.max_words} words]",
        "provider": "mock",
    }


async def handle_grammar(payload: GrammarPayload) -> Dict[str, Any]:
    log.info("handler.grammar.start")
    return {
        "issues": [
            {"type": "spelling", "count": 1},
            {"type": "grammar", "count": 2},
        ],
        "provider": "mock",
    }


async def handle_score(payload: ScorePayload) -> Dict[str, Any]:
    log.info("handler.score.start")
    return {
        "score": 4.2,
        "rubric": payload.rubric or "default",
        "provider": "mock",
    }

