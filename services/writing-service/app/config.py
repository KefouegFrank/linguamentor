"""
Service configuration — all values come from environment variables.
Pydantic-settings handles the reading and type coercion automatically.
Loud failure at boot beats silent failure at runtime.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # App
    app_env:      str  = "development"
    app_debug:    bool = False
    app_port:     int  = 8001
    service_name: str  = "writing-service"

    # Database — no defaults, service won't start if any of them are missing
    db_host:     str
    db_port:     int = 5432
    db_name:     str
    db_user:     str
    db_password: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        
    # Redis
    redis_url: str

    # AI providers — optional at boot, required at inference time
    openai_api_key:    str = ""
    anthropic_api_key: str = ""
    gemini_api_key:    str = ""
    groq_api_key:      str = ""

    # Stamped on every AIModelRun row for audit trail
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
