from typing import Any, Dict
from app.models import TTSPayload
from app.logging import log
from app.router import router


async def handle_tts(payload: TTSPayload) -> Dict[str, Any]:
    log.info("handler.tts.start")
    result = await router.run("tts", payload.model_dump())
    log.info("handler.tts.done")
    return result
