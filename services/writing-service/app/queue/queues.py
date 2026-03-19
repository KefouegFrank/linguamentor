# services/writing-service/app/queue/queues.py
#
# Central BullMQ queue registry.
#
# CRITICAL connection pattern:
# BullMQ Python has a confirmed bug (issue #3401) where passing a shared
# redis.asyncio.Redis instance causes job.data to be empty {} and job.name
# to be None inside the worker processor. The fix confirmed by the community
# is to pass the Redis URL string directly to each Queue and Worker.
# BullMQ Python creates its own internal connections from the URL — this is
# correct behaviour per the official docs pattern.
# Ref: https://github.com/taskforcesh/bullmq/issues/3401

from bullmq import Queue
from app.config import get_settings

# ── Queue name constants ──────────────────────────────────────────────────────
QUEUE_WRITING_EVAL     = "lm:writing:eval"
QUEUE_WRITING_EVAL_DLQ = "lm:writing:eval:dlq"
QUEUE_APPEAL_EVAL      = "lm:writing:appeal"
QUEUE_SRS_GENERATION   = "lm:srs:generation"
QUEUE_PDF_GENERATION   = "lm:pdf:generation"

# ── Default job options ───────────────────────────────────────────────────────
WRITING_EVAL_JOB_OPTIONS = {
    "attempts": 3,
    "backoff": {
        "type": "exponential",
        "delay": 2000,
    },
    "removeOnComplete": {"count": 100},
    "removeOnFail":     {"count": 500},
}

APPEAL_EVAL_JOB_OPTIONS = {
    "attempts": 2,
    "backoff": {
        "type": "fixed",
        "delay": 3000,
    },
    "removeOnComplete": {"count": 200},
    "removeOnFail":     {"count": 200},
}


class QueueRegistry:
    """
    Holds initialised BullMQ Queue instances.
    
    Each Queue gets the Redis URL string directly — not a shared client.
    BullMQ Python creates its own connection pool from the URL.
    This avoids the confirmed shared-connection bug in BullMQ Python ≤2.19.6.
    """

    def __init__(self) -> None:
        settings = get_settings()
        # Use the Redis URL string — BullMQ Python manages its own connections
        conn = {"connection": settings.redis_url}

        self.writing_eval = Queue(
            QUEUE_WRITING_EVAL,
            conn,
        )
        self.writing_eval_dlq = Queue(
            QUEUE_WRITING_EVAL_DLQ,
            conn,
        )
        self.appeal_eval = Queue(
            QUEUE_APPEAL_EVAL,
            conn,
        )
        self.srs_generation = Queue(
            QUEUE_SRS_GENERATION,
            conn,
        )
        self.pdf_generation = Queue(
            QUEUE_PDF_GENERATION,
            conn,
        )

    async def close(self) -> None:
        """Close all queue connections cleanly on shutdown."""
        await self.writing_eval.close()
        await self.writing_eval_dlq.close()
        await self.appeal_eval.close()
        await self.srs_generation.close()
        await self.pdf_generation.close()
