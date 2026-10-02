"""Tests for configuration."""

from assay.config import Settings


def test_default_settings() -> None:
    """Default settings use SQLite and INFO log level."""
    settings = Settings()
    assert settings.database_url.startswith("sqlite")
    assert settings.log_level == "INFO"
