"""
Shared database connection utilities for all LinguaMentor Python microservices.
Every service imports from here — never creates its own connection logic.

This ensures:
- One place to change connection parameters
- Consistent error handling across all services  
- Connection pooling done correctly everywhere
"""

import os
import logging
from pathlib import Path
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from dotenv import load_dotenv


# Walk up the directory tree from this file's location to find the .env file
# at the monorepo root. This works correctly regardless of which directory
# the script is run from — the path is always relative to THIS file, not
# to the caller's working directory.
#
# Path(__file__) = .../shared/db_utils/connection.py
# .parent        = .../shared/db_utils/
# .parent.parent = .../shared/
# .parent.parent.parent = .../ (monorepo root — where .env lives)
_ROOT_DIR = Path(__file__).parent.parent.parent
_ENV_FILE = _ROOT_DIR / ".env"


# override=False means we never overwrite variables already set in the
# environment — important in production where Vault/Kubernetes sets them
load_dotenv(dotenv_path=_ENV_FILE, override=False)

# Module-level logger — every service should log, never use print() in production
logger = logging.getLogger(__name__)


def _build_postgres_dsn() -> str:
    """
    Constructs the PostgreSQL Data Source Name (DSN) connection string
    from environment variables.

    DSN format: postgresql://user:password@host:port/dbname

    Raises:
        ValueError: if any required environment variable is missing.
    """
    # Read each required variable — fail loudly if missing.
    # Silent failures here cause confusing errors deep inside service logic.
    host = os.getenv("LM_DB_HOST")
    port = os.getenv("LM_DB_PORT", "5432")  # 5432 is the PostgreSQL default
    name = os.getenv("LM_DB_NAME")
    user = os.getenv("LM_DB_USER")
    password = os.getenv("LM_DB_PASSWORD")

    # Collect all missing variables before raising — better than failing
    # on the first missing variable and making the developer fix one at a time
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
            f"Missing required database environment variables: {', '.join(missing)}\n"
            f"Expected .env file at: {_ENV_FILE}\n"
            f".env file exists: {_ENV_FILE.exists()}"
            # The last line tells the developer exactly whether the file
            # was found — eliminates guessing during debugging
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


async def create_postgres_pool(
    min_size: int = 2,
    max_size: int = 10,
) -> asyncpg.Pool:
    """
    Creates and returns an asyncpg connection pool.

    A connection pool maintains multiple open database connections
    and reuses them across requests. This is critical for performance —
    opening a new connection for every request adds 50-100ms of latency.

    Args:
        min_size: Minimum connections kept open (default 2).
        max_size: Maximum connections allowed simultaneously (default 10).
                  Set based on expected concurrency per service.

    Returns:
        asyncpg.Pool: A ready-to-use async connection pool.

    Raises:
        asyncpg.PostgresError: If the connection cannot be established.
    """
    dsn = _build_postgres_dsn()

    try:
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            # Fail fast if database is unreachable at startup rather than
            # silently returning a broken pool that fails on first use
            timeout=30.0,
            command_timeout=60.0,
        )
        logger.info(
            "PostgreSQL connection pool created successfully "
            f"(min={min_size}, max={max_size})"
        )
        return pool

    except asyncpg.PostgresError as e:
        # Log full context before re-raising so operators can diagnose quickly
        logger.error(f"Failed to create PostgreSQL connection pool: {e}")
        raise


async def create_redis_client() -> aioredis.Redis:
    """
    Creates and returns an async Redis client.

    Uses the LM_REDIS_URL environment variable which follows the format:
        redis://host:port               (no auth — local dev)
        redis://:password@host:port     (with auth — production)

    Returns:
        aioredis.Redis: A ready-to-use async Redis client.

    Raises:
        ValueError: If LM_REDIS_URL environment variable is missing.
        redis.RedisError: If the connection cannot be established.
    """
    redis_url = os.getenv("LM_REDIS_URL")

    if not redis_url:
        raise ValueError(
            f"Missing required environment variable: LM_REDIS_URL\n"
            f"Expected .env file at: {_ENV_FILE}\n"
            f".env file exists: {_ENV_FILE.exists()}"
        )

    try:
        # decode_responses=True: Redis returns Python strings instead of
        # raw bytes — far easier to work with throughout the codebase
        client = aioredis.from_url(
            redis_url,
            decode_responses=True,
            # Proactively checks connection health every 30 seconds.
            # Detects and replaces stale connections before they cause errors.
            health_check_interval=30,
        )

        # Verify the connection is actually working.
        # from_url() does not connect immediately — ping forces it.
        await client.ping()

        logger.info(f"Redis client connected successfully: {redis_url}")
        return client

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


async def close_postgres_pool(pool: asyncpg.Pool) -> None:
    """
    Gracefully closes the PostgreSQL connection pool.

    Always call this on application shutdown to release database
    connections cleanly. Failing to do this leaves connections open
    on the database server, eventually exhausting the connection limit.
    """
    await pool.close()
    logger.info("PostgreSQL connection pool closed")


async def close_redis_client(client: aioredis.Redis) -> None:
    """
    Gracefully closes the Redis client connection.

    Always call this on application shutdown.
    """
    await client.aclose()
    logger.info("Redis client connection closed")
