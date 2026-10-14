"""Integration test for refusal correctness in the executor pipeline."""

from assay.adapters.http_target import HTTPTargetAdapter, TargetResponse
from assay.core.executor import execute_run
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository
from assay.db.repositories.run import ResultRepository, RunRepository


def _patch_adapter(monkeypatch, responses):
    """Patch HTTPTargetAdapter to return canned responses."""
    call_count = {"n": 0}

    def fake_query(self, question, dataset_id=None, run_id=None):
        idx = call_count["n"]
        call_count["n"] += 1
        return responses[idx]

    monkeypatch.setattr(HTTPTargetAdapter, "query", fake_query)


def test_refusal_answerable_answered(test_session, monkeypatch) -> None:
    """Answerable question, answered -> refusal_correctness=1.0."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)

    ds = ds_repo.create(name="refusal-ds-1")
    q_repo.create(
        dataset_id=ds.id,
        question="Berapa batas usia?",
        expected_answer="60 tahun",
    )
    run = run_repo.create(
        dataset_id=ds.id, name="refusal-run-1", target_url="http://mock"
    )

    responses = [
        TargetResponse(
            answer="Batas usia adalah 60 tahun.",
            retrieved_contexts=[{"text": "Batas usia: 60 tahun."}],
            latency_ms=1000,
            cost_usd=0.0,
            metadata={},
        )
    ]
    _patch_adapter(monkeypatch, responses)

    summary = execute_run(test_session, run.id, verbose=False)

    assert summary.refusal_evaluated == 1
    assert summary.refusal_correct == 1

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert results[0].refusal_correctness == 1.0
    assert results[0].refusal_status == "answerable_answered"


def test_refusal_answerable_refused(test_session, monkeypatch) -> None:
    """Answerable question, refused -> refusal_correctness=0.0."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)

    ds = ds_repo.create(name="refusal-ds-2")
    q_repo.create(
        dataset_id=ds.id,
        question="Berapa batas usia?",
        expected_answer="60 tahun",
    )
    run = run_repo.create(
        dataset_id=ds.id, name="refusal-run-2", target_url="http://mock"
    )

    responses = [
        TargetResponse(
            answer="Saya tidak tahu.",
            retrieved_contexts=[{"text": "Some context."}],
            latency_ms=1000,
            cost_usd=0.0,
            metadata={},
        )
    ]
    _patch_adapter(monkeypatch, responses)

    summary = execute_run(test_session, run.id, verbose=False)
    assert summary.refusal_evaluated == 1
    assert summary.refusal_correct == 0

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert results[0].refusal_correctness == 0.0
    assert results[0].refusal_status == "answerable_refused"


def test_refusal_unanswerable_refused(test_session, monkeypatch) -> None:
    """Unanswerable question, refused -> refusal_correctness=1.0."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)

    ds = ds_repo.create(name="refusal-ds-3")
    q_repo.create(
        dataset_id=ds.id,
        question="Pertanyaan tanpa jawaban?",
        # No expected_answer, no expected_context
    )
    run = run_repo.create(
        dataset_id=ds.id, name="refusal-run-3", target_url="http://mock"
    )

    responses = [
        TargetResponse(
            answer="Informasi tidak tersedia.",
            retrieved_contexts=[],
            latency_ms=1000,
            cost_usd=0.0,
            metadata={},
        )
    ]
    _patch_adapter(monkeypatch, responses)

    summary = execute_run(test_session, run.id, verbose=False)
    assert summary.refusal_evaluated == 1
    assert summary.refusal_correct == 1

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert results[0].refusal_correctness == 1.0
    assert results[0].refusal_status == "unanswerable_refused"


def test_refusal_unanswerable_answered(test_session, monkeypatch) -> None:
    """Unanswerable question, answered -> refusal_correctness=0.0."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)

    ds = ds_repo.create(name="refusal-ds-4")
    q_repo.create(dataset_id=ds.id, question="Pertanyaan tanpa jawaban?")
    run = run_repo.create(
        dataset_id=ds.id, name="refusal-run-4", target_url="http://mock"
    )

    responses = [
        TargetResponse(
            answer="Batas usia adalah 60 tahun.",
            retrieved_contexts=[],
            latency_ms=1000,
            cost_usd=0.0,
            metadata={},
        )
    ]
    _patch_adapter(monkeypatch, responses)

    summary = execute_run(test_session, run.id, verbose=False)
    assert summary.refusal_evaluated == 1
    assert summary.refusal_correct == 0

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert results[0].refusal_correctness == 0.0
    assert results[0].refusal_status == "unanswerable_answered"
