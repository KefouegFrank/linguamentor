"""
shared/db_utils/connection.py

PostgreSQL and Redis connection utilities shared across all Python services.
Import from here — never write connection logic inside a service directly.

POOL CONFIGURATION (PRD §9.1 — Performance SLAs):
  min_size=5:
    Keep 5 connections warm at all times. Prevents cold connection
    establishment on first-morning traffic bursts. PostgreSQL connection
    establishment costs ~50-100ms — unacceptable for a P95 < 300ms SLA.

  max_size=20:
    Writing eval workers hold connections for up to 6s (LLM wait time).
    At 10 concurrent evaluations, 10 connections are occupied for up to 6s.
    max_size=20 gives 2x headroom above that worst case before connection
    requests start queuing.

  max_inactive_connection_lifetime=300.0 (5 minutes):
    Recycle idle connections after 5 minutes. Prevents PostgreSQL from
    accumulating stale connections that consume server resources during
    off-peak hours. asyncpg re-establishes transparently on next request.

  timeout=30.0:
    Connection acquisition timeout. If the pool is exhausted and a new
    connection cannot be established within 30s, raise immediately rather
    than hanging the request indefinitely.

  command_timeout=60.0:
    Per-query timeout. No single query should take more than 60s.
    Catches runaway queries before they block the entire pool.

  statement_cache_size=100 (asyncpg default):
    asyncpg automatically prepares and caches the 100 most recently used
    queries per connection. This gives near-zero parse overhead for hot
    queries like the writing session status update.
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

# override=False — never clobber variables already injected by Vault/k8s.
# In production, Vault injects secrets as env vars at pod startup before
# the Python process starts. override=False ensures Vault wins.
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
            "LM_DB_HOST":     host,
            "LM_DB_NAME":     name,
            "LM_DB_USER":     user,
            "LM_DB_PASSWORD": password,
        }.items() if not val
    ]

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f".env file expected at: {_ENV_FILE}\n"
            f".env file exists: {_ENV_FILE.exists()}\n"
            f"In production, these are injected by HashiCorp Vault."
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


async def create_postgres_pool(
    min_size: int = 5,
    max_size: int = 20,
) -> asyncpg.Pool:
    """
    Creates an asyncpg connection pool shared across all requests in a service.

    This function is called ONCE at application startup via the FastAPI
    lifespan context manager in each service's main.py. The resulting
    pool is stored module-level in dependencies.py and injected into
    route handlers via FastAPI's dependency injection system.

    Never call this per-request — connection pool creation is expensive
    and you would exhaust PostgreSQL's max_connections immediately.

    Args:
        min_size: Minimum warm connections. Default 5 — keeps connections
                  ready for first-morning traffic without cold latency.
        max_size: Maximum connections. Default 20 — 2x headroom above the
                  worst-case concurrent AI evaluation load (10 workers × 6s hold).

    Raises:
        ValueError: If required environment variables are missing at startup.
        asyncpg.PostgresError: If PostgreSQL is unreachable during startup.
            In Kubernetes, this causes the pod to fail its readiness probe
            and restart — correct behaviour for dependency unavailability.
    """
    dsn = _build_postgres_dsn()

    try:
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,

            # Connection acquisition timeout.
            # If all connections are busy and a new one can't be established
            # within 30s, raise TooManyConnectionsError immediately.
            # Better to fail fast with a 503 than hang the request forever.
            timeout=30.0,

            # Per-query execution timeout.
            # No individual SQL statement should take longer than 60s.
            # Catches runaway queries before they block other requests.
            # Long-running batch jobs (calibration scoring) should use
            # explicit per-query timeouts to override this.
            command_timeout=60.0,

            # Recycle idle connections after 5 minutes.
            # Prevents PostgreSQL from holding stale connections during
            # off-peak hours. asyncpg re-establishes transparently.
            # 300s matches the default PostgreSQL tcp_keepalives_idle setting.
            max_inactive_connection_lifetime=300.0,

            # asyncpg automatically prepares and caches the N most recent
            # queries per connection. 100 covers all hot paths comfortably
            # without excessive memory usage per connection.
            # Prepared statements reduce per-query parse + plan overhead
            # to near zero for repeated query patterns (status polling, etc.)
            statement_cache_size=100,

            # Connection init: set search_path so every query in every
            # service automatically targets the linguamentor schema
            # without needing schema-qualified table names in SQL.
            # This must match the search_path set in init-db.sql.
            init=_init_connection,
        )

        logger.info(
            f"PostgreSQL connection pool created | "
            f"min={min_size} max={max_size} | "
            f"host={os.getenv('LM_DB_HOST')}:{os.getenv('LM_DB_PORT', '5432')} | "
            f"db={os.getenv('LM_DB_NAME')}"
        )
        return pool

    except asyncpg.PostgresError as e:
        logger.critical(
            f"PostgreSQL pool creation FAILED — service cannot start. "
            f"Error: {e}. "
            f"Check that Docker containers are running: "
            f"docker compose -f infrastructure/docker-compose.yml ps"
        )
        raise


async def _init_connection(conn: asyncpg.Connection) -> None:
    """
    Called by asyncpg on every new connection in the pool, immediately
    after the connection is established and before it's used.

    Sets the search_path so all queries can reference tables without
    schema prefixes. This matches the database-level default set in
    init-db.sql:
        ALTER DATABASE linguamentor SET search_path TO linguamentor, public;

    We set it here too as a defence-in-depth measure — if the database
    default is ever lost (e.g. DB restore without init-db.sql), the
    pool connections still work correctly.

    Also registers custom type codecs here if needed in future
    (e.g. custom JSONB → Python dict codec, UUID handling).
    """
    await conn.execute("SET search_path TO linguamentor, public")


async def create_redis_client() -> aioredis.Redis:
    """
    Returns a shared Redis client for a service.

    Unlike PostgreSQL, Redis connections aren't pooled per-request —
    the redis-py async client handles connection multiplexing internally
    using a connection pool under the hood. You get one client object
    shared across all requests in the service.

    Configuration choices:
        decode_responses=True:
            Redis stores bytes natively. decode_responses=True makes the
            client return Python str objects automatically. All LinguaMentor
            Redis values are UTF-8 strings (JSON, JWTs, session state).
            Never set to False unless working with binary audio blobs —
            those go to S3, not Redis (PRD §3 data architecture).

        health_check_interval=30:
            asyncio-redis checks the connection every 30s by sending a
            PING. Detects stale connections (e.g. Redis restart, network
            blip) proactively rather than on the next command. Without this,
            a service can hold a dead Redis connection for hours.

        socket_connect_timeout=5:
            Fail fast if Redis is unreachable at connection time.
            Surfaces infra problems immediately on startup rather than
            on the first Redis command under production load.

        retry_on_timeout=True:
            Automatically retry a command once if a socket timeout occurs.
            Handles transient network blips without surfacing errors to callers.

        socket_keepalive=True:
            Enable TCP keepalives on the Redis socket. Prevents NAT/firewall
            devices (common in cloud environments) from silently dropping
            idle connections after a few minutes.

    Raises:
        ValueError: If LM_REDIS_URL is not set.
        redis.ConnectionError: If Redis is unreachable.
            In Kubernetes, causes pod to fail readiness probe and restart.
    """
    redis_url = os.getenv("LM_REDIS_URL")

    if not redis_url:
        raise ValueError(
            f"Missing required environment variable: LM_REDIS_URL\n"
            f".env file expected at: {_ENV_FILE}\n"
            f".env file exists: {_ENV_FILE.exists()}\n"
            f"Expected format: redis://localhost:6379\n"
            f"In production, this is injected by HashiCorp Vault."
        )

    try:
        client = aioredis.from_url(
            redis_url,

            # Return str, not bytes — all LinguaMentor Redis values are UTF-8
            decode_responses=True,

            # Proactive connection health check every 30 seconds
            health_check_interval=30,

            # Fail fast on connection attempt if Redis is down
            socket_connect_timeout=5,

            # Retry once on timeout — handles transient network blips
            retry_on_timeout=True,

            # TCP keepalives — prevents silent connection drops in cloud
            socket_keepalive=True,
        )

        # from_url() is lazy — PING forces the actual TCP connection.
        # This ensures the service fails at startup if Redis is down,
        # not silently on the first cache write under production load.
        await client.ping()

        logger.info(f"Redis client connected | url={redis_url}")
        return client

    except Exception as e:
        logger.critical(
            f"Redis connection FAILED — service cannot start. "
            f"Error: {e}. "
            f"Check that Docker containers are running: "
            f"docker compose -f infrastructure/docker-compose.yml ps"
        )
        raise


async def close_postgres_pool(pool: asyncpg.Pool) -> None:
    """
    Gracefully closes all connections in the pool.

    Called during FastAPI lifespan shutdown. Waits for in-flight
    queries to complete before closing. PostgreSQL logs clean disconnects
    rather than abrupt TCP resets — important for observability.

    In Kubernetes, this runs when the pod receives SIGTERM (graceful
    shutdown signal). The default terminationGracePeriodSeconds=30
    gives 30s for in-flight requests to complete before SIGKILL.
    """
    await pool.close()
    logger.info("PostgreSQL connection pool closed cleanly")


async def close_redis_client(client: aioredis.Redis) -> None:
    """
    Closes the Redis client connection.

    aclose() (formerly aclose()) is the correct async close method
    for redis-py ≥ 5.x. It flushes pending commands and closes the
    underlying connection pool gracefully.
    """
    await client.aclose()
    logger.info("Redis client closed cleanly")
