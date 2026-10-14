"""Integration tests for the run executor (mocked target adapter)."""

import json

import pytest

from assay.adapters.http_target import HTTPTargetAdapter, TargetError, TargetResponse
from assay.core.executor import execute_run
from assay.db.models import RunStatus
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository
from assay.db.repositories.run import ResultRepository, RunRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dataset_with_questions(test_session, n: int = 2):
    """Create a dataset with n questions. Returns (dataset, questions)."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    ds = ds_repo.create(name=f"ds-{n}", description="Test")
    questions = [
        q_repo.create(
            dataset_id=ds.id,
            question=f"Q{i}?",
            expected_answer=f"Answer number {i}",
            expected_context=f"Context number {i}",
        )
        for i in range(n)
    ]
    return ds, questions


def _make_run(test_session, dataset_id: int, name: str = "run-1"):
    run_repo = RunRepository(test_session)
    return run_repo.create(
        dataset_id=dataset_id,
        name=name,
        target_url="http://mock.local/query",
    )


def _make_response(answer: str = "reset password") -> TargetResponse:
    return TargetResponse(
        answer=answer,
        retrieved_contexts=[{"text": "reset password settings", "source": "docs.md"}],
        latency_ms=1000,
        cost_usd=0.001,
        metadata={"model": "mock"},
    )


class _FakeAdapter:
    """A fake adapter that returns canned responses or raises."""

    def __init__(self, responses, raise_on: set[int] | None = None):
        self.responses = responses
        self.raise_on = raise_on or set()
        self.calls: list[dict] = []

    def query(self, question, dataset_id=None, run_id=None):
        idx = len(self.calls)
        self.calls.append(
            {"question": question, "dataset_id": dataset_id, "run_id": run_id}
        )
        if idx in self.raise_on:
            raise TargetError(f"mock failure at index {idx}")
        return self.responses[idx]


def _patch_adapter(monkeypatch, adapter):
    """Patch HTTPTargetAdapter to return the given fake adapter."""
    def fake_init(self, target_url, timeout=60.0):
        self.target_url = target_url
        self.timeout = timeout

    monkeypatch.setattr(HTTPTargetAdapter, "__init__", fake_init)
    monkeypatch.setattr(HTTPTargetAdapter, "query", lambda self, **kw: adapter.query(**kw))


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_execute_run_happy_path(test_session, monkeypatch) -> None:
    ds, questions = _make_dataset_with_questions(test_session, n=2)
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([_make_response(), _make_response()])
    _patch_adapter(monkeypatch, adapter)

    summary = execute_run(test_session, run.id, verbose=False)

    assert summary.total == 2
    assert summary.succeeded == 2
    assert summary.failed == 0
    assert summary.total_latency_ms == 2000
    assert summary.total_cost_usd == pytest.approx(0.002)

    run_repo = RunRepository(test_session)
    updated = run_repo.get(run.id)
    assert updated.status == RunStatus.COMPLETED.value

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert len(results) == 2
    for r in results:
        assert r.answer == "reset password"
        assert r.groundedness is not None
        assert r.context_recall is not None


def test_execute_run_passes_question_and_ids(test_session, monkeypatch) -> None:
    ds, _ = _make_dataset_with_questions(test_session, n=1)
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([_make_response()])
    _patch_adapter(monkeypatch, adapter)

    execute_run(test_session, run.id, verbose=False)

    assert adapter.calls[0]["question"] == "Q0?"
    assert adapter.calls[0]["dataset_id"] == str(ds.id)
    assert adapter.calls[0]["run_id"] == str(run.id)


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_execute_run_all_failed(test_session, monkeypatch) -> None:
    ds, _ = _make_dataset_with_questions(test_session, n=2)
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([_make_response(), _make_response()], raise_on={0, 1})
    _patch_adapter(monkeypatch, adapter)

    summary = execute_run(test_session, run.id, verbose=False)

    assert summary.total == 2
    assert summary.succeeded == 0
    assert summary.failed == 2

    run_repo = RunRepository(test_session)
    updated = run_repo.get(run.id)
    assert updated.status == RunStatus.FAILED.value
    assert "All 2 questions failed" in (updated.error_message or "")


def test_execute_run_partial_failure_marks_completed(test_session, monkeypatch) -> None:
    ds, _ = _make_dataset_with_questions(test_session, n=2)
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([_make_response(), _make_response()], raise_on={1})
    _patch_adapter(monkeypatch, adapter)

    summary = execute_run(test_session, run.id, verbose=False)

    assert summary.succeeded == 1
    assert summary.failed == 1

    run_repo = RunRepository(test_session)
    updated = run_repo.get(run.id)
    assert updated.status == RunStatus.COMPLETED.value

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert len(results) == 2
    # One result should have an error_message
    errors = [r for r in results if r.error_message]
    assert len(errors) == 1


# ---------------------------------------------------------------------------
# Validation paths
# ---------------------------------------------------------------------------


def test_execute_run_not_found(test_session, monkeypatch) -> None:
    adapter = _FakeAdapter([])
    _patch_adapter(monkeypatch, adapter)

    with pytest.raises(ValueError, match="not found"):
        execute_run(test_session, 99999, verbose=False)


def test_execute_run_wrong_status_raises(test_session, monkeypatch) -> None:
    ds, _ = _make_dataset_with_questions(test_session, n=1)
    run = _make_run(test_session, ds.id)

    run_repo = RunRepository(test_session)
    run_repo.mark_running(run.id)

    adapter = _FakeAdapter([])
    _patch_adapter(monkeypatch, adapter)

    with pytest.raises(ValueError, match="cannot execute"):
        execute_run(test_session, run.id, verbose=False)


def test_execute_run_empty_dataset_marks_failed(test_session, monkeypatch) -> None:
    ds_repo = DatasetRepository(test_session)
    ds = ds_repo.create(name="empty-ds")
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([])
    _patch_adapter(monkeypatch, adapter)

    with pytest.raises(ValueError, match="no questions"):
        execute_run(test_session, run.id, verbose=False)

    run_repo = RunRepository(test_session)
    updated = run_repo.get(run.id)
    assert updated.status == RunStatus.FAILED.value
    assert "no questions" in (updated.error_message or "")


def test_execute_run_failed_run_can_be_retried(test_session, monkeypatch) -> None:
    """A FAILED run can be re-executed (status not COMPLETED)."""
    ds, _ = _make_dataset_with_questions(test_session, n=1)
    run = _make_run(test_session, ds.id)

    run_repo = RunRepository(test_session)
    run_repo.mark_failed(run.id, "previous failure")

    adapter = _FakeAdapter([_make_response()])
    _patch_adapter(monkeypatch, adapter)

    summary = execute_run(test_session, run.id, verbose=False)
    assert summary.succeeded == 1

    updated = run_repo.get(run.id)
    assert updated.status == RunStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# Judge integration (judge disabled by default in tests)
# ---------------------------------------------------------------------------


def test_execute_run_without_judge_uses_simple_metrics(test_session, monkeypatch) -> None:
    """By default, use_judge=False -> simple metrics, no judge calls."""
    ds, _ = _make_dataset_with_questions(test_session, n=1)
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([_make_response()])
    _patch_adapter(monkeypatch, adapter)

    summary = execute_run(test_session, run.id, verbose=False, use_judge=False)

    assert summary.judge_used == 0
    assert summary.relevance_used == 0

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert results[0].answer_relevance is None


def test_execute_run_with_judge_requested_but_not_configured(
    test_session, monkeypatch
) -> None:
    """use_judge=True but judge not configured -> fallback to simple, no crash."""
    from assay.config import settings

    # Force judge to be disabled.
    monkeypatch.setattr(settings, "judge_provider", None)
    monkeypatch.setattr(settings, "judge_model", None)
    monkeypatch.setattr(settings, "judge_api_key", None)
    monkeypatch.setattr(settings, "judge_provider_2", None)
    monkeypatch.setattr(settings, "judge_model_2", None)
    monkeypatch.setattr(settings, "judge_api_key_2", None)
    monkeypatch.setattr(settings, "judge_provider_3", None)
    monkeypatch.setattr(settings, "judge_model_3", None)
    monkeypatch.setattr(settings, "judge_api_key_3", None)
    monkeypatch.setattr(settings, "judge_provider_4", None)
    monkeypatch.setattr(settings, "judge_model_4", None)
    monkeypatch.setattr(settings, "judge_api_key_4", None)

    ds, _ = _make_dataset_with_questions(test_session, n=1)
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([_make_response()])
    _patch_adapter(monkeypatch, adapter)

    summary = execute_run(test_session, run.id, verbose=False, use_judge=True)

    assert summary.judge_used == 0
    assert summary.relevance_used == 0
    assert summary.succeeded == 1

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    # simple groundedness was used
    assert results[0].groundedness is not None
    assert results[0].answer_relevance is None


def test_execute_run_stores_retrieved_contexts_as_json(test_session, monkeypatch) -> None:
    ds, _ = _make_dataset_with_questions(test_session, n=1)
    run = _make_run(test_session, ds.id)

    adapter = _FakeAdapter([_make_response()])
    _patch_adapter(monkeypatch, adapter)

    execute_run(test_session, run.id, verbose=False)

    res_repo = ResultRepository(test_session)
    result = res_repo.list_by_run(run.id)[0]
    parsed = json.loads(result.retrieved_contexts)
    assert isinstance(parsed, list)
    assert parsed[0]["text"] == "reset password settings"
