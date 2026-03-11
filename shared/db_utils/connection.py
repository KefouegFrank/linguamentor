"""
shared/db_utils/connection.py

PostgreSQL and Redis connection utilities shared across all Python services.
Import from here — never write connection logic inside a service directly.
"""

import os
import logging
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis
from dotenv import load_dotenv

# Resolve .env from monorepo root regardless of where the service runs from.
# __file__ is always this file's absolute path — walking up 3 levels gets
# to the repo root where .env lives.
_ROOT_DIR = Path(__file__).parent.parent.parent
_ENV_FILE = _ROOT_DIR / ".env"

# override=False — never clobber variables already injected by Vault/k8s
load_dotenv(dotenv_path=_ENV_FILE, override=False)

logger = logging.getLogger(__name__)


def _build_postgres_dsn() -> str:
    host     = os.getenv("LM_DB_HOST")
    port     = os.getenv("LM_DB_PORT", "5432")
    name     = os.getenv("LM_DB_NAME")
    user     = os.getenv("LM_DB_USER")
    password = os.getenv("LM_DB_PASSWORD")

    missing = [
        var for var, val in {
            "LM_DB_HOST": host,
            "LM_DB_NAME": name,
            "LM_DB_USER": user,
            "LM_DB_PASSWORD": password,
        }.items() if not val
    ]

    if missing:
        raise ValueError(
            f"Missing env vars: {', '.join(missing)}\n"
            f".env expected at: {_ENV_FILE} (exists: {_ENV_FILE.exists()})"
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


async def create_postgres_pool(
    min_size: int = 2,
    max_size: int = 10,
) -> asyncpg.Pool:
    """
    Creates a connection pool shared across all requests.
    min_size=2 keeps two connections warm — first requests don't pay
    the connection establishment cost.
    """
    dsn = _build_postgres_dsn()

    try:
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=30.0,
            command_timeout=60.0,
        )
        logger.info(f"PostgreSQL pool created (min={min_size}, max={max_size})")
        return pool

    except asyncpg.PostgresError as e:
        logger.error(f"PostgreSQL pool creation failed: {e}")
        raise


async def create_redis_client() -> aioredis.Redis:
    """
    Returns a shared Redis client. Connection multiplexing is handled
    internally — no per-request pooling needed unlike PostgreSQL.
    """
    redis_url = os.getenv("LM_REDIS_URL")

    if not redis_url:
        raise ValueError(
            f"Missing LM_REDIS_URL\n"
            f".env expected at: {_ENV_FILE} (exists: {_ENV_FILE.exists()})"
        )

    try:
        client = aioredis.from_url(
            redis_url,
            decode_responses=True,      # return str not bytes
            health_check_interval=30,   # detect stale connections proactively
        )
        # from_url() is lazy — ping forces the actual connection
        await client.ping()
        logger.info(f"Redis connected: {redis_url}")
        return client

    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise


async def close_postgres_pool(pool: asyncpg.Pool) -> None:
    # Always call on shutdown — leaves DB connections in a clean state
    await pool.close()
    logger.info("PostgreSQL pool closed")


async def close_redis_client(client: aioredis.Redis) -> None:
    await client.aclose()
    logger.info("Redis client closed")
