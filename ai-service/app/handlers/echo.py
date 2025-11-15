from typing import Any, Dict
from app.models import (
    TranslationPayload,
    SummarizationPayload,
    GrammarPayload,
    ScorePayload,
)
from app.logging import log
from app.router import router


async def handle_echo(payload: Dict[str, Any]) -> Dict[str, Any]:
    log.info("handler.echo")
    # Echo handler for end-to-end testing
    return {"echo": True, "payload_shape": list(payload.keys())}


async def handle_translate(payload: TranslationPayload) -> Dict[str, Any]:
    log.info("handler.translate.start")
    result = await router.run("translate", payload.model_dump())
    log.info("handler.translate.done")
    return result


async def handle_summarize(payload: SummarizationPayload) -> Dict[str, Any]:
    log.info("handler.summarize.start")
    result = await router.run("summarize", payload.model_dump())
    log.info("handler.summarize.done")
    return result


async def handle_grammar(payload: GrammarPayload) -> Dict[str, Any]:
    log.info("handler.grammar.start")
    result = await router.run("grammar", payload.model_dump())
    log.info("handler.grammar.done")
    return result


async def handle_score(payload: ScorePayload) -> Dict[str, Any]:
    log.info("handler.score.start")
    result = await router.run("score", payload.model_dump())
    log.info("handler.score.done")
    return result
