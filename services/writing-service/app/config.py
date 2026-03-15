"""
Service configuration — all values come from environment variables.
Pydantic-settings handles the reading and type coercion automatically.
no manual os.getenv() calls scattered through the codebase.

If a required variable is missing at startup, the service refuses
to start and tells you exactly which variable is missing.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Service configuration — every value comes from environment variables.
    Field names map directly to env var names (case-insensitive).
    pydantic-settings strips the LM_ prefix via env_prefix below.
    """

    # --- App ---
    app_env: str = "development"
    app_debug: bool = False
    app_port: int = 8001
    service_name: str = "writing-service"

    # --- Database ---
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

        
    # Redis
    redis_url: str
    
    # --- JWT (RS256 — asymmetric, PRD §37.1) ---
    # Paths to PEM files — loaded at startup, not stored as raw strings
    # Private key: signs tokens (writing-service signs during auth)
    # Public key: verifies tokens (all services verify)
    lm_jwt_private_key_path: str = ""
    lm_jwt_public_key_path: str = ""
    lm_jwt_access_token_expire_minutes: int = 15    # PRD §37.1 — 15 min access token
    lm_jwt_refresh_token_expire_days: int = 7       # PRD §37.1 — 7 day refresh token

    @property
    def jwt_private_key(self) -> str:
        """Reads the RS256 private key from disk. Cached after first read."""
        if not self.lm_jwt_private_key_path:
            raise ValueError("LM_JWT_PRIVATE_KEY_PATH is not configured")
        path = Path(self.lm_jwt_private_key_path)
        if not path.exists():
            raise ValueError(f"JWT private key not found at: {path.resolve()}")
        return path.read_text()

    @property
    def jwt_public_key(self) -> str:
        """Reads the RS256 public key from disk."""
        if not self.lm_jwt_public_key_path:
            raise ValueError("LM_JWT_PUBLIC_KEY_PATH is not configured")
        path = Path(self.lm_jwt_public_key_path)
        if not path.exists():
            raise ValueError(f"JWT public key not found at: {path.resolve()}")
        return path.read_text()
    
    # --- AI Providers ---
    openai_api_key:    str = ""
    anthropic_api_key: str = ""
    gemini_api_key:    str = ""
    groq_api_key:      str = ""

    # --- Calibration ---
    calibration_version: str = "v1.0-dev"
    
    #Testing
    # Enables MockProvider which returns synthetic scores without
    # calling any external AI service. Useful for local testing and CI.
    use_mock_provider: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # LM_APP_DEBUG → app_debug, LM_DB_HOST → db_host, etc.
        env_prefix="LM_",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    # Cached — config is read once per process, not on every request
    return Settings()
