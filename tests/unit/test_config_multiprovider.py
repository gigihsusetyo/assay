"""Unit tests for multi-provider judge configuration."""

from assay.config import JudgeProviderConfig, Settings


def _clear_judge_env(monkeypatch) -> None:
    """Remove all ASSAY_JUDGE_* vars so each test starts clean."""
    for key in [
        "ASSAY_JUDGE_PROVIDER", "ASSAY_JUDGE_MODEL",
        "ASSAY_JUDGE_API_KEY", "ASSAY_JUDGE_BASE_URL", "ASSAY_JUDGE_TIMEOUT",
        "ASSAY_JUDGE_PROVIDER_2", "ASSAY_JUDGE_MODEL_2",
        "ASSAY_JUDGE_API_KEY_2", "ASSAY_JUDGE_BASE_URL_2", "ASSAY_JUDGE_TIMEOUT_2",
        "ASSAY_JUDGE_PROVIDER_3", "ASSAY_JUDGE_MODEL_3",
        "ASSAY_JUDGE_API_KEY_3", "ASSAY_JUDGE_BASE_URL_3", "ASSAY_JUDGE_TIMEOUT_3",
        "ASSAY_JUDGE_PROVIDER_4", "ASSAY_JUDGE_MODEL_4",
        "ASSAY_JUDGE_API_KEY_4", "ASSAY_JUDGE_BASE_URL_4", "ASSAY_JUDGE_TIMEOUT_4",
        "ASSAY_JUDGE_FALLBACK", "ASSAY_JUDGE_VOTES",
    ]:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# judge_enabled
# ---------------------------------------------------------------------------


def test_judge_disabled_when_no_providers(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.judge_enabled is False
    assert settings.judge_providers == []


def test_judge_enabled_with_primary_provider(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY", "gsk_test")
    monkeypatch.setenv("ASSAY_JUDGE_BASE_URL", "https://api.groq.com/openai/v1")

    settings = Settings(_env_file=None)
    assert settings.judge_enabled is True
    assert len(settings.judge_providers) == 1
    assert settings.judge_providers[0].name == "groq"
    assert settings.judge_providers[0].model == "openai/gpt-oss-120b"


def test_judge_disabled_when_model_missing(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY", "gsk_test")
    # model missing

    settings = Settings(_env_file=None)
    assert settings.judge_enabled is False


def test_judge_disabled_when_api_key_missing(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL", "openai/gpt-oss-120b")
    # api_key missing

    settings = Settings(_env_file=None)
    assert settings.judge_enabled is False


# ---------------------------------------------------------------------------
# Multi-provider ordering
# ---------------------------------------------------------------------------


def test_multiple_providers_in_order(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL", "m1")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY", "k1")
    monkeypatch.setenv("ASSAY_JUDGE_BASE_URL", "https://p1")

    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER_2", "gemini")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL_2", "m2")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY_2", "k2")
    monkeypatch.setenv("ASSAY_JUDGE_BASE_URL_2", "https://p2")

    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER_3", "tokenharbor")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL_3", "m3")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY_3", "k3")
    monkeypatch.setenv("ASSAY_JUDGE_BASE_URL_3", "https://p3")

    settings = Settings(_env_file=None)
    providers = settings.judge_providers
    assert len(providers) == 3
    assert providers[0].name == "groq"
    assert providers[1].name == "gemini"
    assert providers[2].name == "tokenharbor"


def test_skips_incomplete_provider_in_middle(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL", "m1")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY", "k1")

    # Provider 2: missing api_key -> skipped
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER_2", "gemini")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL_2", "m2")

    # Provider 3: complete
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER_3", "tokenharbor")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL_3", "m3")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY_3", "k3")

    settings = Settings(_env_file=None)
    providers = settings.judge_providers
    assert len(providers) == 2
    assert providers[0].name == "groq"
    assert providers[1].name == "tokenharbor"


def test_provider_4_supported(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER_4", "ollama")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL_4", "llama3.1")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY_4", "ollama")
    monkeypatch.setenv("ASSAY_JUDGE_BASE_URL_4", "http://localhost:11434/v1")

    settings = Settings(_env_file=None)
    providers = settings.judge_providers
    assert len(providers) == 1
    assert providers[0].name == "ollama"


# ---------------------------------------------------------------------------
# Provider config attributes
# ---------------------------------------------------------------------------


def test_provider_config_timeout_default(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL", "m1")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY", "k1")

    settings = Settings(_env_file=None)
    assert settings.judge_providers[0].timeout == 15.0


def test_provider_config_timeout_override(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL", "m1")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY", "k1")
    monkeypatch.setenv("ASSAY_JUDGE_TIMEOUT", "45.5")

    settings = Settings(_env_file=None)
    assert settings.judge_providers[0].timeout == 45.5


def test_provider_config_repr_hides_api_key() -> None:
    cfg = JudgeProviderConfig(
        name="groq",
        model="m1",
        api_key="supersecret",
        base_url="https://api.groq.com",
    )
    text = repr(cfg)
    assert "supersecret" not in text
    assert "groq" in text


def test_provider_base_url_optional(monkeypatch) -> None:
    """base_url can be empty; provider still constructed."""
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_PROVIDER", "groq")
    monkeypatch.setenv("ASSAY_JUDGE_MODEL", "m1")
    monkeypatch.setenv("ASSAY_JUDGE_API_KEY", "k1")

    settings = Settings(_env_file=None)
    assert settings.judge_providers[0].base_url == ""


# ---------------------------------------------------------------------------
# Fallback and votes defaults
# ---------------------------------------------------------------------------


def test_fallback_default_true(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.judge_fallback is True


def test_fallback_override_false(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_FALLBACK", "false")
    settings = Settings(_env_file=None)
    assert settings.judge_fallback is False


def test_votes_default_one(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.judge_votes == 1


def test_votes_override(monkeypatch) -> None:
    _clear_judge_env(monkeypatch)
    monkeypatch.setenv("ASSAY_JUDGE_VOTES", "3")
    settings = Settings(_env_file=None)
    assert settings.judge_votes == 3
