"""Configuration management using pydantic-settings."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None

    # Embedding Configuration
    EMBEDDING_MODEL: str = "all-mpnet-base-v2"

    # Chunking Configuration
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100

    # Vector Database Configuration
    VECTOR_DB_PATH: str = "./data/faiss_index"

    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = False

    # CORS Configuration
    CORS_ORIGINS: list[str] = ["*"]


# Global settings instance
settings = Settings()
