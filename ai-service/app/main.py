import asyncio
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.logging import configure_logging, log
from app.worker import worker


app = FastAPI(title="LinguaMentor AI Service", version="1.0.0")


@app.on_event("startup")
async def on_startup():
    configure_logging(settings.LOG_LEVEL)
    log.info("service.start", service=settings.SERVICE_NAME)
    # Start worker background tasks only if enabled and concurrency > 0
    if not settings.DISABLE_WORKER and settings.WORKER_CONCURRENCY > 0:
        asyncio.create_task(worker.start())
    else:
        log.info("worker.disabled", reason="flag or zero concurrency")


@app.on_event("shutdown")
async def on_shutdown():
    log.info("service.shutdown")
    await worker.stop()


@app.get("/health")
async def health():
    """Return service and Redis connectivity status."""
    if settings.DISABLE_WORKER or settings.WORKER_CONCURRENCY <= 0:
        redis_status = "disabled"
    else:
        try:
            ping = await worker.redis.ping()
            redis_status = "ok" if bool(ping) else "error"
        except Exception:
            redis_status = "error"
    return {
        "service": "ok",
        "redis": redis_status,
        "queue": settings.REDIS_QUEUE_NAME,
        "concurrency": settings.WORKER_CONCURRENCY,
        "workerEnabled": not settings.DISABLE_WORKER and settings.WORKER_CONCURRENCY > 0,
        "provider": settings.MODEL_PROVIDER,
    }


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
