from typing import Any, Dict
from app.models import ASRPayload
from app.logging import log
from app.router import router


async def handle_asr(payload: ASRPayload) -> Dict[str, Any]:
    log.info("handler.asr.start", audio_key=payload.audio_s3_key)
    result = await router.run("asr", payload.model_dump())
    log.info("handler.asr.done")
    return result
