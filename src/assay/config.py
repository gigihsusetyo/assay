"""Assay configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ASSAY_",
    )

    database_url: str = "postgresql+psycopg://assay:assay@localhost:5432/assay"
    log_level: str = "INFO"


settings = Settings()
