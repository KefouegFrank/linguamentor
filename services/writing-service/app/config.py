"""
All configuration for the writing service lives here.
Pydantic-settings reads from environment variables automatically —
no manual os.getenv() calls scattered through the codebase.

If a required variable is missing at startup, the service refuses
to start and tells you exactly which variable is missing. That's
the behaviour we want — loud failure at boot beats silent failure
at runtime.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Service configuration — every value comes from environment variables.
    Field names map directly to env var names (case-insensitive).
    """

    # --- App ---
    # Controls log verbosity and enables debug tooling like
    # auto-reload and detailed tracebacks
    app_env: str = "development"
    app_debug: bool = False
    app_port: int = 8001
    # Service name shows up in logs and Jaeger traces —
    # makes it easy to filter by service in production
    service_name: str = "writing-service"

    # --- Database ---
    # Required — no defaults. If these aren't set the service won't start.
    lm_db_host: str
    lm_db_port: int = 5432
    lm_db_name: str
    lm_db_user: str
    lm_db_password: str

    # Computed DSN — built from the individual fields above.
    # Services use this to connect, never build DSN strings themselves.
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.lm_db_user}:{self.lm_db_password}"
            f"@{self.lm_db_host}:{self.lm_db_port}/{self.lm_db_name}"
        )

    # --- Redis ---
    lm_redis_url: str

    # --- AI Providers ---
    # Optional at boot — required at inference time.
    # Services start without them so we can test non-AI endpoints early.
    lm_openai_api_key: str = ""
    lm_anthropic_api_key: str = ""

    # --- Calibration ---
    # Every AI evaluation references this version string.
    # Stored in AIModelRun — the audit trail depends on this being set.
    calibration_version: str = "v1.0-dev"

    model_config = SettingsConfigDict(
        # Tells pydantic-settings where to find the .env file.
        # Services run from their own directory so this resolves correctly.
        env_file=".env",
        env_file_encoding="utf-8",
        # Don't blow up on extra env vars that this service doesn't use —
        # the root .env has variables meant for other services too
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    lru_cache means this only instantiates Settings once per process —
    not on every request. Config doesn't change at runtime so there's
    no reason to re-read it repeatedly.
    """
    return Settings()
