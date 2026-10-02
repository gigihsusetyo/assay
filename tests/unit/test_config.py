"""Tests for configuration."""

from assay.config import Settings


def test_default_settings(monkeypatch) -> None:
    """Default settings use SQLite and INFO log level.

    We clear ASSAY_DATABASE_URL from the environment so that .env
    does not affect this test.
    """
    monkeypatch.delenv("ASSAY_DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("sqlite")
    assert settings.log_level == "INFO"


def test_database_url_from_env(monkeypatch) -> None:
    """Database URL can be overridden by environment variable."""
    monkeypatch.setenv("ASSAY_DATABASE_URL", "postgresql://user:pass@host/db")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql://user:pass@host/db"
