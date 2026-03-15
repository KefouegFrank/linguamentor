"""
FastAPI dependency functions for database and Redis access.

FastAPI's dependency injection system calls these functions
automatically when a route declares them as parameters.
The connection pool is created once at startup and reused —
routes just borrow a connection, use it, and return it.
"""

from typing import AsyncGenerator
import asyncpg
import redis.asyncio as aioredis
from fastapi import Depends

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import decode_access_token, is_token_blacklisted


# These module-level variables hold the pool/client created at startup.
# They're set by the lifespan function in main.py and read here.
# None until the app starts — routes should never be called before startup.
_postgres_pool: asyncpg.Pool | None = None
_redis_client: aioredis.Redis | None = None
_bearer_scheme = HTTPBearer()


def set_postgres_pool(pool: asyncpg.Pool) -> None:
    """Called once at startup to register the pool with the dependency layer."""
    global _postgres_pool
    _postgres_pool = pool


def set_redis_client(client: aioredis.Redis) -> None:
    """Called once at startup to register the Redis client."""
    global _redis_client
    _redis_client = client


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency that yields a database connection from the pool.

    Usage in a route:
        @router.post("/evaluate")
        async def evaluate(conn: asyncpg.Connection = Depends(get_db)):
            result = await conn.fetchval("SELECT ...")

    The connection is automatically returned to the pool when the
    request finishes — even if an exception is raised.
    """
    if _postgres_pool is None:
        # This should never happen in normal operation.
        # If it does, the lifespan function in main.py has a bug.
        raise RuntimeError("Database pool not initialised — check app lifespan")

    async with _postgres_pool.acquire() as connection:
        yield connection
        # asyncpg releases the connection back to the pool here automatically


async def get_redis() -> aioredis.Redis:
    """
    FastAPI dependency that returns the shared Redis client.

    Unlike PostgreSQL, Redis connections aren't pooled per-request —
    the client handles connection multiplexing internally.

    Usage in a route:
        @router.get("/session")
        async def get_session(redis: aioredis.Redis = Depends(get_redis)):
            value = await redis.get("lm:session:abc123")
    """
    if _redis_client is None:
        raise RuntimeError("Redis client not initialised — check app lifespan")
    return _redis_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """
    FastAPI dependency that validates the JWT and returns the current user.

    Usage in a protected route:
        @router.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            return {"user_id": user["sub"]}

    The API Gateway verifies tokens before forwarding to this service.
    This dependency is a defence-in-depth check inside the service.
    Raises 401 if token is missing, invalid, expired, or blacklisted.
    """
    token = credentials.credentials

    # Check blacklist first — fast Redis lookup before expensive JWT decode
    if await is_token_blacklisted(token, redis):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


async def require_pro(
    user: dict = Depends(get_current_user),
) -> dict:
    """
    Dependency that requires Pro subscription tier.
    Use on Pro-gated endpoints (PRD §5.1).

    Usage:
        @router.post("/exam/start")
        async def start_exam(user: dict = Depends(require_pro)):
            ...
    """
    if user.get("tier") != "pro":
        raise HTTPException(
            status_code=403,
            detail="This feature requires a Pro subscription",
        )
    return user
