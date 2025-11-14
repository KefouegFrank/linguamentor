from typing import Any, Dict
from pydantic import ValidationError
from app.models import (
    JobEnvelope,
    ASRPayload,
    TTSPayload,
    LLMPayload,
    TranslationPayload,
    SummarizationPayload,
    GrammarPayload,
    ScorePayload,
)
from app.logging import log, _hash_value


async def handle_job(envelope: JobEnvelope) -> Dict[str, Any]:
    """Dispatch job to the appropriate handler by type."""
    try:
        job_type = envelope.type
        payload = envelope.payload
        log.info("job.received", job_id=envelope.jobId, type=job_type)

        if job_type == "llm":
            data = LLMPayload(**payload)
            from .llm import handle_llm

            return await handle_llm(data)
        elif job_type == "asr":
            data = ASRPayload(**payload)
            from .asr import handle_asr

            return await handle_asr(data)
        elif job_type == "tts":
            data = TTSPayload(**payload)
            from .tts import handle_tts

            return await handle_tts(data)
        elif job_type == "translate":
            data = TranslationPayload(**payload)
            from .echo import handle_translate

            return await handle_translate(data)
        elif job_type == "summarize":
            data = SummarizationPayload(**payload)
            from .echo import handle_summarize

            return await handle_summarize(data)
        elif job_type == "grammar":
            data = GrammarPayload(**payload)
            from .echo import handle_grammar

            return await handle_grammar(data)
        elif job_type == "score":
            data = ScorePayload(**payload)
            from .echo import handle_score

            return await handle_score(data)
        elif job_type == "echo":
            from .echo import handle_echo

            return await handle_echo(payload)
        else:
            raise ValueError(f"Unsupported job type: {job_type}")
    except ValidationError as ve:
        log.error(
            "job.payload.invalid",
            job_id=envelope.jobId,
            type=envelope.type,
            error=str(ve),
            payload_hash=_hash_value(envelope.payload),
        )
        raise

