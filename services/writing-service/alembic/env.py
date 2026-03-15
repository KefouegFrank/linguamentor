"""
alembic/env.py

Alembic migration environment — configured for async asyncpg driver.

Key decisions:
- Database URL loaded from app settings, not hardcoded in alembic.ini
- All models imported here so Base.metadata is fully populated
  before autogenerate compares against the live DB
- Uses asyncio.run() + run_sync() pattern — the only way to run
  Alembic's synchronous migration context against an async engine
- include_schemas=True is critical — without it, Alembic ignores
  our 'linguamentor' schema and generates wrong migrations
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Path setup — must run before any app imports
# ---------------------------------------------------------------------------
# Alembic runs from services/writing-service/alembic/ by default.
# We need the monorepo root on sys.path to import 'shared',
# and the service root to import 'app'.
_SERVICE_DIR = Path(__file__).parent.parent          # services/writing-service/
_MONOREPO_ROOT = _SERVICE_DIR.parent.parent          # linguamentor/

sys.path.insert(0, str(_MONOREPO_ROOT))
sys.path.insert(0, str(_SERVICE_DIR))

# ---------------------------------------------------------------------------
# App imports — after path setup
# ---------------------------------------------------------------------------
from app.config import get_settings
from app.models.base import Base

# Import ALL models so SQLAlchemy knows about their tables.
# If a model isn't imported here, autogenerate won't see it
# and will generate a migration to DROP the table.
from app.models.domain import (  # noqa: F401 — imported for side effects
    User,
    RefreshToken,
    LearnerProfile,
    SkillVector,
    AIModelRun,
    WritingSession,
    SpeakingSession,
    DailySession,
    ScoreAppeal,
    ExamAttempt,
    ExamSection,
    ReadinessSnapshot,
    ShareEvent,
)

# ---------------------------------------------------------------------------
# Alembic config object
# ---------------------------------------------------------------------------
config = context.config

# Wire up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point autogenerate at our declarative base
target_metadata = Base.metadata

# Override the database URL from app settings — not from alembic.ini.
# This keeps migration environment and application in perfect sync.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
))


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    """
    The synchronous core that Alembic's context.run_migrations() needs.
    Called via connection.run_sync() from the async context.

    include_schemas=True is essential — without it, Alembic operates
    only on the 'public' schema and generates incorrect migrations for
    our 'linguamentor' schema tables.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        # Tell Alembic which schemas to watch — prevents it from
        # touching PostgreSQL system schemas or any future schemas
        # we don't own
        include_name=lambda name, type_, parent_names: (
            name in ("linguamentor", None) if type_ == "schema"
            else True
        ),
        # Render server defaults in generated migrations so
        # autogenerate detects server_default changes too
        render_as_batch=False,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Creates an async engine and runs migrations inside run_sync().
    NullPool is correct here — Alembic migrations are one-shot,
    connection pooling would just add overhead and risk leaks.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """
    Offline mode — generate SQL without connecting to the database.
    Useful for reviewing what a migration will do before running it,
    or for environments where direct DB access isn't available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Entry point for online migrations — wraps the async runner."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
