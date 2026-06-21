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
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import decode_access_token, is_token_blacklisted
from app.queue.queues import QueueRegistry

_postgres_pool: asyncpg.Pool | None = None
_redis_client: aioredis.Redis | None = None
_queue_registry: QueueRegistry | None = None
_bearer_scheme = HTTPBearer()


def set_postgres_pool(pool: asyncpg.Pool) -> None:
    global _postgres_pool
    _postgres_pool = pool


def set_redis_client(client: aioredis.Redis) -> None:
    global _redis_client
    _redis_client = client


def set_queue_registry(registry: QueueRegistry) -> None:
    global _queue_registry
    _queue_registry = registry


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    if _postgres_pool is None:
        raise RuntimeError("Database pool not initialised")
    async with _postgres_pool.acquire() as connection:
        yield connection


async def get_redis() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client not initialised")
    return _redis_client


def get_queue_registry() -> QueueRegistry:
    if _queue_registry is None:
        raise RuntimeError("Queue registry not initialised")
    return _queue_registry


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    token = credentials.credentials
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
    if user.get("tier") != "pro":
        raise HTTPException(
            status_code=403,
            detail="This feature requires a Pro subscription",
        )
    return user
