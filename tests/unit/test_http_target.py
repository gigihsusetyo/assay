"""Unit tests for the HTTP target adapter (mocked transport)."""

import httpx
import pytest

from assay.adapters.http_target import HTTPTargetAdapter, TargetError


def _adapter_with(handler) -> HTTPTargetAdapter:
    """Build an adapter whose httpx client uses a MockTransport."""
    adapter = HTTPTargetAdapter(target_url="http://test.local/query")
    # Monkey-patch the client creation to use MockTransport.
    adapter._mock_transport = httpx.MockTransport(handler)
    return adapter


# We need to patch httpx.Client inside the adapter to use MockTransport.
# The simplest approach: patch the adapter.query method's httpx.Client call
# by injecting the transport through a context manager.


@pytest.fixture
def patch_httpx(monkeypatch):
    """Provide a helper to install a MockTransport into httpx.Client."""

    def install(handler):
        original_client = httpx.Client

        def patched_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "Client", patched_client)

    return install


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_query_success_full_response(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "answer": "Go to settings and click reset.",
                "retrieved_contexts": [
                    {"text": "You can reset your password in settings.", "source": "docs.md"}
                ],
                "latency_ms": 1240,
                "cost_usd": 0.0032,
                "metadata": {"model": "gpt-4"},
            },
        )

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    response = adapter.query(question="How do I reset my password?")

    assert response.answer == "Go to settings and click reset."
    assert len(response.retrieved_contexts) == 1
    assert response.retrieved_contexts[0]["text"] == "You can reset your password in settings."
    assert response.latency_ms == 1240
    assert response.cost_usd == 0.0032
    assert response.metadata == {"model": "gpt-4"}


def test_query_minimal_response(patch_httpx) -> None:
    """Optional fields default gracefully."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"answer": "OK"})

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    response = adapter.query(question="Hi")

    assert response.answer == "OK"
    assert response.retrieved_contexts == []
    assert response.latency_ms == 0
    assert response.cost_usd is None
    assert response.metadata == {}


def test_query_sends_correct_payload(patch_httpx) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content.decode())
        return httpx.Response(200, json={"answer": "OK"})

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    adapter.query(question="Q?", dataset_id="ds-1", run_id="run-1")

    assert captured["body"] == {
        "question": "Q?",
        "dataset_id": "ds-1",
        "run_id": "run-1",
    }


def test_query_none_ids_sent_as_null(patch_httpx) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["body"] = _json.loads(request.content.decode())
        return httpx.Response(200, json={"answer": "OK"})

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    adapter.query(question="Q?")

    assert captured["body"]["dataset_id"] is None
    assert captured["body"]["run_id"] is None


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_query_http_error_raises_target_error(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    with pytest.raises(TargetError, match="500"):
        adapter.query(question="Q?")


def test_query_404_raises_target_error(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not found")

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    with pytest.raises(TargetError, match="404"):
        adapter.query(question="Q?")


def test_query_missing_answer_field_raises(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"foo": "bar"})

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    with pytest.raises(TargetError, match="answer"):
        adapter.query(question="Q?")


def test_query_invalid_json_raises(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    with pytest.raises(TargetError, match="JSON"):
        adapter.query(question="Q?")


def test_query_connection_error_raises(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    with pytest.raises(TargetError, match="Failed to reach"):
        adapter.query(question="Q?")


def test_query_timeout_raises(patch_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out")

    patch_httpx(handler)
    adapter = HTTPTargetAdapter("http://test.local/query")
    with pytest.raises(TargetError, match="Failed to reach"):
        adapter.query(question="Q?")
