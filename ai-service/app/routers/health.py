"""
app/routers/health.py

Health and readiness endpoints — required on every LinguaMentor service
before it's considered deployable (non-negotiable per PRD).

/health  → is the process alive?
/ready   → is the process ready to serve traffic?

These aren't the same thing and Kubernetes treats them differently:
- Liveness probe hits /health — if it fails, Kubernetes restarts the pod
- Readiness probe hits /ready — if it fails, Kubernetes stops sending
  traffic to this pod but doesn't restart it

That distinction matters: a service that's alive but waiting for the
DB to come back should return /health=200 but /ready=503.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
import asyncpg
import redis.asyncio as aioredis

from app.dependencies import get_db, get_redis
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 if the service process is running. "
                "Does not check dependencies.",
)
async def health() -> JSONResponse:
    """
    Liveness check — just confirms the process is up and responding.
    No dependency checks here intentionally: if the DB is down, the
    process is still alive and Kubernetes shouldn't restart it.
    """
    settings = get_settings()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "service": settings.service_name,
            "version": settings.calibration_version,
        },
    )


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Returns 200 only if all dependencies are reachable. "
                "Used by Kubernetes to gate traffic.",
)
async def ready(
    conn: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> JSONResponse:
    """
    Readiness check — confirms the service can actually do work.
    Checks both PostgreSQL and Redis before returning 200.
    Returns 503 if either dependency is unreachable.
    """
    checks = {}

    # Check PostgreSQL
    try:
        await conn.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"failed: {e}"

    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"failed: {e}"

    # If anything failed, return 503 so Kubernetes stops sending traffic here
    all_healthy = all(v == "ok" for v in checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "degraded",
            "checks": checks,
        },
    )
