import os
from typing import Optional

try:
    # Load environment variables from a local .env file if present
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; ignore if not installed
    pass


class Settings:
    """Service configuration loaded from environment variables.

    All values have sensible defaults for local development. In production,
    override via environment variables or container orchestration.
    """

    # Core service
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "ai-service")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info").lower()
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    # Disable worker entirely (e.g., for local API-only runs)
    DISABLE_WORKER: bool = os.getenv("DISABLE_WORKER", "false").strip().lower() in {"1", "true", "yes", "on"}
    DISABLE_WORKER: bool = os.getenv("DISABLE_WORKER", "false").lower() in {"1", "true", "yes"}

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    REDIS_QUEUE_NAME: str = os.getenv("REDIS_QUEUE_NAME", "ai-jobs")

    # Backend
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://backend:4000")
    INTERNAL_SERVICE_TOKEN: Optional[str] = os.getenv("INTERNAL_SERVICE_TOKEN")

    # AI providers
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "openai")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

    # HTTP client
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))


settings = Settings()

