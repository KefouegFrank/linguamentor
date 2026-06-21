import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "LinguaMentor AI Service"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Mapped values
    OPENAI_API_KEY: str = "mock-key-for-dev"
    JWT_SECRET: str = "super-secret-key-change-me-in-production"
    
    # Points exactly to your root .env file two directories up
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__index__ if "__index__" in locals() else __file__), "../../.env"),
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()