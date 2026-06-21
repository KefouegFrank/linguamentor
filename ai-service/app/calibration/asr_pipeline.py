"""
app/calibration/asr_pipeline.py

ASR transcription pipeline for WER validation.

Fetches audio samples from the database, transcribes each using
Groq Whisper Large v3, submits results to wer_transcription_results.

Designed to run offline — triggered manually via the WER validation
router, never during a live user session.
"""

import asyncio
import logging
import time
import uuid as uuid_module
from pathlib import Path

import asyncpg

from app.calibration.wer_engine import compute_wer
from app.config import get_settings

logger = logging.getLogger(__name__)

# Root directory for audio files — relative to monorepo root
AUDIO_ROOT = Path(__file__).parent.parent.parent.parent.parent / "data" / "wer_samples"

# Delay between Groq ASR calls to respect rate limits
# Whisper uses audio-duration tokens, not text tokens —
# a 10-second clip uses ~167 audio tokens at 16kHz
# Free tier: 7200 audio seconds/hour = comfortable for 40 clips
ASR_CALL_DELAY_SECONDS = 3


async def run_asr_pipeline(
    conn: asyncpg.Connection,
    run_id: str,
    accent_targets: list[str] = None,
) -> dict:
    """
    Transcribes all pending audio samples for a WER validation run.

    Fetches samples not yet transcribed in this run, runs each through
    Groq Whisper, computes WER against reference, stores results.

    Args:
        conn:            Database connection
        run_id:          WER validation run ID
        accent_targets:  Filter to specific accents (None = all)

    Returns:
        Summary dict with scored/failed counts per accent
    """
    from groq import Groq

    settings = get_settings()

    if not settings.groq_api_key:
        raise RuntimeError(
            "LM_GROQ_API_KEY not set — required for ASR pipeline"
        )

    client = Groq(api_key=settings.groq_api_key)

    # Fetch pending samples
    query = """
        SELECT
            s.id::text,
            s.accent_target,
            s.audio_path,
            s.reference_text,
            s.word_count
        FROM linguamentor.wer_audio_samples s
        WHERE
            s.id NOT IN (
                SELECT r.sample_id
                FROM linguamentor.wer_transcription_results r
                WHERE r.run_id = $1
            )
    """
    params = [uuid_module.UUID(run_id)]

    if accent_targets:
        query += " AND s.accent_target = ANY($2)"
        params.append(accent_targets)

    query += " ORDER BY s.accent_target, s.id"

    samples = await conn.fetch(query, *params)

    if not samples:
        logger.warning(f"No pending samples for run {run_id}")
        return {"scored": 0, "failed": 0, "total": 0}

    logger.info(
        f"Starting ASR pipeline: {len(samples)} samples | run={run_id[:8]}..."
    )

    scored = 0
    failed = 0

    # Language map — tell Whisper which language to expect
    # This improves accuracy and prevents language misdetection
    language_map = {
        "en-US": "en",
        "en-GB": "en",
        "fr-FR": "fr",
        "fr-CA": "fr",
    }

    for i, sample in enumerate(samples, 1):
        accent    = sample["accent_target"]
        audio_path = AUDIO_ROOT / sample["audio_path"]

        logger.info(
            f"Transcribing [{i}/{len(samples)}] "
            f"{accent} — {sample['audio_path']}"
        )

        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            failed += 1
            continue

        start_time = time.monotonic()

        try:
            with open(audio_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    file=(audio_path.name, audio_file),
                    model="whisper-large-v3",
                    language=language_map.get(accent, "en"),
                    response_format="verbose_json",
                    temperature=0.0,
                )

            latency_ms   = int((time.monotonic() - start_time) * 1000)
            hypothesis   = response.text.strip()

            # Compute WER immediately
            wer_result = compute_wer(sample["reference_text"], hypothesis)

            # Store result
            await conn.execute(
                """
                INSERT INTO linguamentor.wer_transcription_results (
                    id, run_id, sample_id,
                    hypothesis_text, wer,
                    substitutions, insertions, deletions,
                    latency_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                uuid_module.uuid4(),
                uuid_module.UUID(run_id),
                uuid_module.UUID(sample["id"]),
                hypothesis,
                wer_result.wer,
                wer_result.substitutions,
                wer_result.insertions,
                wer_result.deletions,
                latency_ms,
            )

            # Update clips_scored counter
            await conn.execute(
                """
                UPDATE linguamentor.wer_validation_runs
                SET clips_scored = clips_scored + 1
                WHERE id = $1
                """,
                uuid_module.UUID(run_id),
            )

            logger.info(
                f"  WER={wer_result.wer:.4f} ({wer_result.wer:.1%}) | "
                f"S={wer_result.substitutions} I={wer_result.insertions} "
                f"D={wer_result.deletions} | {latency_ms}ms"
            )
            scored += 1

            # Rate limit delay between calls
            if i < len(samples):
                await asyncio.sleep(ASR_CALL_DELAY_SECONDS)

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                f"ASR failed for {sample['audio_path']} "
                f"after {latency_ms}ms: {e}"
            )
            failed += 1

    summary = {
        "run_id": run_id,
        "scored": scored,
        "failed": failed,
        "total":  len(samples),
    }
    logger.info(f"ASR pipeline complete: {summary}")
    return summary
