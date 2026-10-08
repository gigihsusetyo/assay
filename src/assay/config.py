"""Assay configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class JudgeProviderConfig:
    """Configuration for a single judge provider."""

    def __init__(
        self,
        name: str,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float = 120.0,
    ) -> None:
        self.name = name
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    def __repr__(self) -> str:
        return f"<JudgeProviderConfig(name={self.name!r}, model={self.model!r})>"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ASSAY_",
    )

    database_url: str = "sqlite:///./assay.db"
    log_level: str = "INFO"

    # Primary judge provider
    judge_provider: str | None = None
    judge_model: str | None = None
    judge_api_key: str | None = None
    judge_base_url: str | None = None
    judge_timeout: float = 120.0

    # Additional providers for fallback (numbered)
    judge_provider_2: str | None = None
    judge_model_2: str | None = None
    judge_api_key_2: str | None = None
    judge_base_url_2: str | None = None
    judge_timeout_2: float = 120.0

    judge_provider_3: str | None = None
    judge_model_3: str | None = None
    judge_api_key_3: str | None = None
    judge_base_url_3: str | None = None
    judge_timeout_3: float = 120.0

    judge_provider_4: str | None = None
    judge_model_4: str | None = None
    judge_api_key_4: str | None = None
    judge_base_url_4: str | None = None
    judge_timeout_4: float = 120.0

    # Fallback behavior
    judge_fallback: bool = True

    # Number of times to run the judge per question (majority vote).
    judge_votes: int = 1

    @property
    def judge_enabled(self) -> bool:
        """Judge is enabled only if at least one provider is fully configured."""
        return len(self.judge_providers) > 0

    @property
    def judge_providers(self) -> list[JudgeProviderConfig]:
        """Return all configured providers in order."""
        providers: list[JudgeProviderConfig] = []

        # Primary
        if self.judge_provider and self.judge_model and self.judge_api_key:
            providers.append(
                JudgeProviderConfig(
                    name=self.judge_provider,
                    model=self.judge_model,
                    api_key=self.judge_api_key,
                    base_url=self.judge_base_url or "",
                    timeout=self.judge_timeout,
                )
            )

        # Numbered providers
        for i in range(2, 5):
            name = getattr(self, f"judge_provider_{i}")
            model = getattr(self, f"judge_model_{i}")
            api_key = getattr(self, f"judge_api_key_{i}")
            base_url = getattr(self, f"judge_base_url_{i}")
            timeout = getattr(self, f"judge_timeout_{i}")

            if name and model and api_key:
                providers.append(
                    JudgeProviderConfig(
                        name=name,
                        model=model,
                        api_key=api_key,
                        base_url=base_url or "",
                        timeout=timeout,
                    )
                )

        return providers


settings = Settings()
