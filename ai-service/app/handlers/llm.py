from typing import Any, Dict
from app.models import LLMPayload
from app.logging import log
from app.router import router


async def handle_llm(payload: LLMPayload) -> Dict[str, Any]:
    log.info("handler.llm.start")
    result = await router.run("llm", payload.model_dump())
    log.info("handler.llm.done")
    return result
