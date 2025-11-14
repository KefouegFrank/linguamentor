from typing import Any, Dict
from app.models import ASRPayload
from app.logging import log


async def handle_asr(payload: ASRPayload) -> Dict[str, Any]:
    # Placeholder ASR implementation. Integrate Whisper/Coqui/Vosk here.
    log.info("handler.asr.start", audio_key=payload.audio_s3_key)
    # Never log raw audio; produce a mock transcript.
    result = {
        "text": "[MOCK TRANSCRIPT] audio processed",
        "language": payload.language or "en",
        "confidence": 0.9,
        "provider": "mock",
    }
    log.info("handler.asr.done")
    return result

