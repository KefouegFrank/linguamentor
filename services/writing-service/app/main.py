"""
app/main.py

Entry point for the writing service.

The lifespan function handles startup and shutdown — database pools,
Redis clients, and anything else that needs to be initialised once
and cleaned up on exit. FastAPI's lifespan context manager replaced
the old @app.on_event pattern and is the current best practice.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import calibration

from app.config import get_settings
from app.dependencies import set_postgres_pool, set_redis_client
from app.exceptions import register_exception_handlers
from app.routers import health


# Configure before anything else so early startup errors are captured.
# In production, Loki picks up stdout logs from the container.
logging.basicConfig(
    level=logging.DEBUG if get_settings().app_debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages the full lifecycle of the service.

    Everything before `yield` runs at startup.
    Everything after `yield` runs at shutdown.

    FastAPI guarantees the shutdown block runs even if an exception
    occurs during the request lifecycle — so connections always close cleanly.
    """
    settings = get_settings()
    logger.info(f"Starting {settings.service_name} [{settings.app_env}]")

    # --- Startup ---
    # Import here to avoid circular imports at module load time
    from shared.db_utils.connection import create_postgres_pool, create_redis_client

    # Create the connection pool once — all requests share it.
    # min_size=2 keeps two connections warm so the first requests
    # don't pay the connection establishment cost.
    postgres_pool = await create_postgres_pool(min_size=2, max_size=10)
    redis_client = await create_redis_client()

    # Register with the dependency layer so routes can access them
    set_postgres_pool(postgres_pool)
    set_redis_client(redis_client)

    logger.info(f"{settings.service_name} startup complete — ready to serve")

    yield  # <-- service is running and handling requests here

    # --- Shutdown ---
    # This block runs when the process receives SIGTERM (normal k8s shutdown)
    # or when you Ctrl+C in development. Clean shutdown prevents connection
    # leaks on the database server.
    logger.info(f"Shutting down {settings.service_name}...")

    from shared.db_utils.connection import close_postgres_pool, close_redis_client
    await close_postgres_pool(postgres_pool)
    await close_redis_client(redis_client)

    logger.info(f"{settings.service_name} shutdown complete")



def create_app() -> FastAPI:
    """
    Factory function that creates and configures the FastAPI app.

    Using a factory function (rather than a module-level app instance)
    makes the service easier to test — tests can call create_app()
    to get a fresh instance with test configuration.
    """
    settings = get_settings()

    app = FastAPI(
        title="LinguaMentor Writing Service",
        description="Rubric-aligned essay scoring and CEFR classification",
        version="0.1.0",
        # Disable docs in production — no need to expose API schema publicly
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )

    # CORS — allows the Next.js frontend to call this service via the gateway.
    # In production, origins will be locked to the actual domain.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3001"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register centralised exception handlers
    register_exception_handlers(app)

    # Register routers
    # Each router handles a domain — health, evaluation, appeals, etc.
    # prefix="" means /health and /ready are at the root, not /health/health
    app.include_router(health.router)
    
    app.include_router(calibration.router)

    return app


# Create the app instance that uvicorn will serve
app = create_app()
