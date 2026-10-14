"""Integration tests for the `assay health` CLI command."""

import httpx
import pytest
from typer.testing import CliRunner

from assay.cli.main import app

runner = CliRunner()


@pytest.fixture
def patch_httpx(monkeypatch):
    """Install a MockTransport into httpx.Client."""

    def install(handler):
        original_client = httpx.Client

        def patched_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "Client", patched_client)

    return install


def test_health_ok(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok", "version": "0.1.0"})

    patch_httpx(handler)
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "API OK" in result.stdout
    assert "0.1.0" in result.stdout


def test_health_custom_url(patch_httpx) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "ok", "version": "0.1.0"})

    patch_httpx(handler)
    result = runner.invoke(app, ["health", "--url", "http://example.test:9999"])
    assert result.exit_code == 0
    assert captured["url"] == "http://example.test:9999/health"


def test_health_trailing_slash_stripped(patch_httpx) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "ok", "version": "0.1.0"})

    patch_httpx(handler)
    result = runner.invoke(app, ["health", "--url", "http://example.test:9999/"])
    assert result.exit_code == 0
    assert captured["url"] == "http://example.test:9999/health"


def test_health_env_var(monkeypatch, patch_httpx) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "ok", "version": "0.1.0"})

    monkeypatch.setenv("ASSAY_API_URL", "http://env.test:1234")
    patch_httpx(handler)
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert captured["url"] == "http://env.test:1234/health"


def test_health_connection_error(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    patch_httpx(handler)
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 1
    assert "Cannot reach API" in result.stdout


def test_health_500(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    patch_httpx(handler)
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 1
    assert "500" in result.stdout


def test_health_non_ok_status(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "degraded", "version": "0.1.0"})

    patch_httpx(handler)
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 1
    assert "degraded" in result.stdout


def test_health_invalid_json(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    patch_httpx(handler)
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 1
    assert "Invalid JSON" in result.stdout
