# Central queue registry — all BullMQ queue names and default job options.
#
# Architecture decision: the writing-service owns its queues. The gateway
# forwards requests to this service which then enqueues. This keeps queue
# logic co-located with the business logic that processes it, and avoids
# coupling the gateway to our internal job data structures.
#
# Queue naming convention: lm:{service}:{purpose}
# This namespacing prevents key collisions if multiple services share Redis.

from bullmq import Queue
from redis.asyncio import Redis as AsyncRedis

# ── Queue name constants ──────────────────────────────────────────────────────
# Never use raw strings elsewhere — always import from here.

QUEUE_WRITING_EVAL    = "lm:writing:eval"       # essay scoring jobs
QUEUE_WRITING_EVAL_DLQ = "lm:writing:eval:dlq"  # dead letter — exhausted retries
QUEUE_APPEAL_EVAL     = "lm:writing:appeal"     # score appeal secondary eval
QUEUE_SRS_GENERATION  = "lm:srs:generation"     # daily session pre-gen (Phase 2)
QUEUE_PDF_GENERATION  = "lm:pdf:generation"     # PDF report export (Phase 3)

# ── Default job options ───────────────────────────────────────────────────────
# Applied to all writing evaluation jobs unless overridden at enqueue time.
#
# attempts=3: initial attempt + 2 retries
# backoff exponential with 2s base: retries at 2s, 4s, 8s
# This covers transient AI provider rate limits (typically 1-5s backoff needed)
# removeOnComplete=100: keep last 100 completed jobs for debugging/audit
# removeOnFail=500: keep last 500 failed jobs — important for support cases

WRITING_EVAL_JOB_OPTIONS = {
    "attempts": 3,
    "backoff": {
        "type": "exponential",
        "delay": 2000,      # 2s base → retries at 2s, 4s, 8s
    },
    "removeOnComplete": {"count": 100},
    "removeOnFail":     {"count": 500},
}

APPEAL_EVAL_JOB_OPTIONS = {
    "attempts": 2,          # one retry for appeals — PRD §42 60s SLA
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
    Created once at app startup and injected via FastAPI dependency.

    We pass the existing redis.asyncio.Redis client to each Queue —
    this reuses the connection pool rather than opening new connections.
    BullMQ Python 2.5.0+ supports this pattern natively.
    """

    def __init__(self, redis_client: AsyncRedis) -> None:
        connection = {"connection": redis_client}

        self.writing_eval = Queue(
            QUEUE_WRITING_EVAL,
            connection,
        )
        self.writing_eval_dlq = Queue(
            QUEUE_WRITING_EVAL_DLQ,
            connection,
        )
        self.appeal_eval = Queue(
            QUEUE_APPEAL_EVAL,
            connection,
        )
        # Phase 2/3 queues — registered now so the namespace is reserved
        # Workers are not started until those phases are built
        self.srs_generation = Queue(
            QUEUE_SRS_GENERATION,
            connection,
        )
        self.pdf_generation = Queue(
            QUEUE_PDF_GENERATION,
            connection,
        )

    async def close(self) -> None:
        """Close all queue connections cleanly on shutdown."""
        await self.writing_eval.close()
        await self.writing_eval_dlq.close()
        await self.appeal_eval.close()
        await self.srs_generation.close()
        await self.pdf_generation.close()
