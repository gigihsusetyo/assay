"""Assay configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ASSAY_",
    )

    database_url: str = "sqlite:///./assay.db"
    log_level: str = "INFO"

    # LLM-as-judge configuration (BYOK — Bring Your Own Key)
    judge_provider: str | None = None
    judge_model: str | None = None
    judge_api_key: str | None = None
    judge_base_url: str | None = None
    judge_timeout: float = 60.0

    @property
    def judge_enabled(self) -> bool:
        """Judge is enabled only if provider, model, and API key are set."""
        return bool(self.judge_provider and self.judge_model and self.judge_api_key)


settings = Settings()
