import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies import set_postgres_pool, set_redis_client, set_queue_registry
from app.exceptions import register_exception_handlers
from app.middleware import CorrelationIdMiddleware
from app.queue.queues import QueueRegistry
from app.queue.worker import start_writing_eval_worker

from app.routers import health, calibration, wer_validation
from app.routers import writing
from app.auth.router import router as auth_router, user_router
from app.auth.security import init_jwt_keys

logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG if get_settings().app_debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info(f"Starting {settings.service_name} [{settings.app_env}]")

    from shared.db_utils.connection import (
        create_postgres_pool, create_redis_client,
        close_postgres_pool, close_redis_client,
    )

    init_jwt_keys()
    logger.info("JWT RS256 keys loaded")

    postgres_pool = await create_postgres_pool(min_size=5, max_size=20)
    redis_client  = await create_redis_client()

    # Initialise queue registry — shares the existing Redis client
    queue_registry = QueueRegistry()
    logger.info("BullMQ queue registry initialised")

    set_postgres_pool(postgres_pool)
    set_redis_client(redis_client)
    set_queue_registry(queue_registry)

    # Start the writing evaluation worker
    # The worker runs in the same process as an asyncio task.
    # In production this would be a separate Kubernetes worker pod,
    # but for Phase 1 co-location keeps deployment simple.
    settings = get_settings()
    worker, shutdown_event = await start_writing_eval_worker(
    postgres_pool=postgres_pool,
    redis_url=settings.redis_url,
    )
    logger.info("Writing evaluation worker started")

    logger.info(f"{settings.service_name} startup complete — ready to serve")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info(f"Shutting down {settings.service_name}...")

    # Signal the worker to stop accepting new jobs
    shutdown_event.set()
    await worker.close()
    logger.info("Writing evaluation worker stopped")

    await queue_registry.close()
    await close_postgres_pool(postgres_pool)
    await close_redis_client(redis_client)

    logger.info(f"{settings.service_name} shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="LinguaMentor Writing Service",
        description="Rubric-aligned essay scoring and CEFR classification",
        version="0.1.0",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3001"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(calibration.router)
    app.include_router(wer_validation.router)
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(writing.router)   # ← new

    return app


app = create_app()
