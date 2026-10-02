"""Integration tests for the comparison engine."""

from assay.core.comparison.engine import compare_runs
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository
from assay.db.repositories.run import BaselineRepository, ResultRepository, RunRepository


def test_compare_runs_detects_regression(test_session) -> None:
    """Comparison detects groundedness regression."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)
    res_repo = ResultRepository(test_session)
    base_repo = BaselineRepository(test_session)

    ds = ds_repo.create(name="test-ds", description="Test")
    q1 = q_repo.create(dataset_id=ds.id, question="Q1?", expected_answer="A1")
    q2 = q_repo.create(dataset_id=ds.id, question="Q2?", expected_answer="A2")

    # Baseline: good scores
    baseline_run = run_repo.create(dataset_id=ds.id, name="baseline", target_url="http://mock")
    res_repo.create(run_id=baseline_run.id, question_id=q1.id, groundedness=0.95, latency_ms=1000)
    res_repo.create(run_id=baseline_run.id, question_id=q2.id, groundedness=0.90, latency_ms=1200)

    baseline = base_repo.create(name="test-baseline", run_id=baseline_run.id)

    # Current: worse groundedness
    current_run = run_repo.create(dataset_id=ds.id, name="current", target_url="http://mock")
    res_repo.create(run_id=current_run.id, question_id=q1.id, groundedness=0.80, latency_ms=1000)
    res_repo.create(run_id=current_run.id, question_id=q2.id, groundedness=0.75, latency_ms=1200)

    report = compare_runs(
        test_session,
        baseline=baseline,
        current_run=current_run,
        thresholds={"groundedness": 5.0, "context_recall": 5.0, "p95_latency_ms": 20.0, "avg_cost_usd": 20.0},
    )

    assert report.passed is False
    assert len(report.reasons) > 0
    assert "groundedness" in report.reasons[0]
    assert len(report.worst_failures) == 2


def test_compare_runs_passes_within_threshold(test_session) -> None:
    """Comparison passes when all metrics are within threshold."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)
    res_repo = ResultRepository(test_session)
    base_repo = BaselineRepository(test_session)

    ds = ds_repo.create(name="test-ds-2", description="Test")
    q1 = q_repo.create(dataset_id=ds.id, question="Q1?", expected_answer="A1")

    baseline_run = run_repo.create(dataset_id=ds.id, name="baseline-2", target_url="http://mock")
    res_repo.create(run_id=baseline_run.id, question_id=q1.id, groundedness=0.90, latency_ms=1000)

    baseline = base_repo.create(name="test-baseline-2", run_id=baseline_run.id)

    current_run = run_repo.create(dataset_id=ds.id, name="current-2", target_url="http://mock")
    res_repo.create(run_id=current_run.id, question_id=q1.id, groundedness=0.88, latency_ms=950)

    report = compare_runs(
        test_session,
        baseline=baseline,
        current_run=current_run,
        thresholds={"groundedness": 5.0, "context_recall": 5.0, "p95_latency_ms": 20.0, "avg_cost_usd": 20.0},
    )

    assert report.passed is True
    assert len(report.reasons) == 0
