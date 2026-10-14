"""Integration tests for database repositories (in-memory SQLite)."""

from assay.db.models import RunStatus
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository
from assay.db.repositories.run import (
    BaselineRepository,
    ResultRepository,
    RunRepository,
)


# ---------------------------------------------------------------------------
# DatasetRepository
# ---------------------------------------------------------------------------


def test_dataset_create(test_session) -> None:
    repo = DatasetRepository(test_session)
    ds = repo.create(name="ds-1", description="First")
    assert ds.id is not None
    assert ds.name == "ds-1"
    assert ds.description == "First"
    assert ds.version == "1.0.0"


def test_dataset_get(test_session) -> None:
    repo = DatasetRepository(test_session)
    ds = repo.create(name="ds-1")
    fetched = repo.get(ds.id)
    assert fetched is not None
    assert fetched.id == ds.id


def test_dataset_get_missing_returns_none(test_session) -> None:
    repo = DatasetRepository(test_session)
    assert repo.get(99999) is None


def test_dataset_get_by_name(test_session) -> None:
    repo = DatasetRepository(test_session)
    repo.create(name="ds-1")
    fetched = repo.get_by_name("ds-1")
    assert fetched is not None
    assert fetched.name == "ds-1"


def test_dataset_get_by_name_missing_returns_none(test_session) -> None:
    repo = DatasetRepository(test_session)
    assert repo.get_by_name("nope") is None


def test_dataset_list_empty(test_session) -> None:
    repo = DatasetRepository(test_session)
    assert repo.list() == []


def test_dataset_list_multiple(test_session) -> None:
    repo = DatasetRepository(test_session)
    repo.create(name="a")
    repo.create(name="b")
    repo.create(name="c")
    assert len(repo.list()) == 3


def test_dataset_delete(test_session) -> None:
    repo = DatasetRepository(test_session)
    ds = repo.create(name="ds-1")
    assert repo.delete(ds.id) is True
    assert repo.get(ds.id) is None


def test_dataset_delete_missing_returns_false(test_session) -> None:
    repo = DatasetRepository(test_session)
    assert repo.delete(99999) is False


# ---------------------------------------------------------------------------
# QuestionRepository
# ---------------------------------------------------------------------------


def test_question_create(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    q = q_repo.create(
        dataset_id=ds.id,
        question="What?",
        expected_answer="Answer",
        expected_context="Context",
    )
    assert q.id is not None
    assert q.dataset_id == ds.id
    assert q.question == "What?"


def test_question_list_by_dataset(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    ds1 = ds_repo.create(name="ds-1")
    ds2 = ds_repo.create(name="ds-2")
    q_repo.create(dataset_id=ds1.id, question="A?")
    q_repo.create(dataset_id=ds1.id, question="B?")
    q_repo.create(dataset_id=ds2.id, question="C?")

    assert len(q_repo.list_by_dataset(ds1.id)) == 2
    assert len(q_repo.list_by_dataset(ds2.id)) == 1


def test_question_count_by_dataset(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    assert q_repo.count_by_dataset(ds.id) == 0
    q_repo.create(dataset_id=ds.id, question="A?")
    q_repo.create(dataset_id=ds.id, question="B?")
    assert q_repo.count_by_dataset(ds.id) == 2


def test_question_cascade_delete(test_session) -> None:
    """Deleting a dataset removes its questions (cascade)."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    q_repo.create(dataset_id=ds.id, question="A?")
    q_repo.create(dataset_id=ds.id, question="B?")

    ds_repo.delete(ds.id)
    assert q_repo.list_by_dataset(ds.id) == []


# ---------------------------------------------------------------------------
# RunRepository
# ---------------------------------------------------------------------------


def test_run_create_pending(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="run-1", target_url="http://test")
    assert run.id is not None
    assert run.status == RunStatus.PENDING.value
    assert run.started_at is None
    assert run.completed_at is None


def test_run_get_by_name(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    run_repo.create(dataset_id=ds.id, name="run-1", target_url="http://test")
    fetched = run_repo.get_by_name("run-1")
    assert fetched is not None
    assert fetched.name == "run-1"


def test_run_list_by_dataset(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    ds1 = ds_repo.create(name="ds-1")
    ds2 = ds_repo.create(name="ds-2")
    run_repo.create(dataset_id=ds1.id, name="r1", target_url="http://x")
    run_repo.create(dataset_id=ds1.id, name="r2", target_url="http://x")
    run_repo.create(dataset_id=ds2.id, name="r3", target_url="http://x")

    assert len(run_repo.list(dataset_id=ds1.id)) == 2
    assert len(run_repo.list(dataset_id=ds2.id)) == 1
    assert len(run_repo.list()) == 3


def test_run_mark_running(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    updated = run_repo.mark_running(run.id)
    assert updated is not None
    assert updated.status == RunStatus.RUNNING.value
    assert updated.started_at is not None


def test_run_mark_completed(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    updated = run_repo.mark_completed(run.id)
    assert updated is not None
    assert updated.status == RunStatus.COMPLETED.value
    assert updated.completed_at is not None


def test_run_mark_failed(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    updated = run_repo.mark_failed(run.id, "boom")
    assert updated is not None
    assert updated.status == RunStatus.FAILED.value
    assert updated.error_message == "boom"
    assert updated.completed_at is not None


def test_run_mark_missing_returns_none(test_session) -> None:
    run_repo = RunRepository(test_session)
    assert run_repo.mark_running(99999) is None
    assert run_repo.mark_completed(99999) is None
    assert run_repo.mark_failed(99999, "x") is None


def test_run_delete(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    assert run_repo.delete(run.id) is True
    assert run_repo.get(run.id) is None


def test_run_delete_missing_returns_false(test_session) -> None:
    run_repo = RunRepository(test_session)
    assert run_repo.delete(99999) is False


# ---------------------------------------------------------------------------
# ResultRepository
# ---------------------------------------------------------------------------


def test_result_create_minimal(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)
    res_repo = ResultRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    q = q_repo.create(dataset_id=ds.id, question="Q?")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    result = res_repo.create(run_id=run.id, question_id=q.id)
    assert result.id is not None
    assert result.answer is None
    assert result.groundedness is None


def test_result_create_full(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)
    res_repo = ResultRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    q = q_repo.create(dataset_id=ds.id, question="Q?")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    result = res_repo.create(
        run_id=run.id,
        question_id=q.id,
        answer="Answer",
        retrieved_contexts="[]",
        groundedness=0.9,
        context_recall=0.8,
        answer_relevance=0.7,
        latency_ms=1200,
        cost_usd=0.001,
    )
    assert result.answer == "Answer"
    assert result.groundedness == 0.9
    assert result.latency_ms == 1200


def test_result_list_by_run(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)
    res_repo = ResultRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    q1 = q_repo.create(dataset_id=ds.id, question="A?")
    q2 = q_repo.create(dataset_id=ds.id, question="B?")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    res_repo.create(run_id=run.id, question_id=q1.id, groundedness=0.9)
    res_repo.create(run_id=run.id, question_id=q2.id, groundedness=0.8)

    results = res_repo.list_by_run(run.id)
    assert len(results) == 2


def test_result_count_by_run(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)
    res_repo = ResultRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    q = q_repo.create(dataset_id=ds.id, question="A?")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    assert res_repo.count_by_run(run.id) == 0
    res_repo.create(run_id=run.id, question_id=q.id)
    assert res_repo.count_by_run(run.id) == 1


# ---------------------------------------------------------------------------
# BaselineRepository
# ---------------------------------------------------------------------------


def test_baseline_create(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    base_repo = BaselineRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")

    baseline = base_repo.create(name="bl-1", run_id=run.id, description="First")
    assert baseline.id is not None
    assert baseline.name == "bl-1"
    assert baseline.run_id == run.id


def test_baseline_get_by_name(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    base_repo = BaselineRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")
    base_repo.create(name="bl-1", run_id=run.id)

    fetched = base_repo.get_by_name("bl-1")
    assert fetched is not None
    assert fetched.name == "bl-1"


def test_baseline_get_by_name_missing_returns_none(test_session) -> None:
    base_repo = BaselineRepository(test_session)
    assert base_repo.get_by_name("nope") is None


def test_baseline_list(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    base_repo = BaselineRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")
    base_repo.create(name="bl-1", run_id=run.id)
    base_repo.create(name="bl-2", run_id=run.id)

    assert len(base_repo.list()) == 2


def test_baseline_delete(test_session) -> None:
    ds_repo = DatasetRepository(test_session)
    run_repo = RunRepository(test_session)
    base_repo = BaselineRepository(test_session)

    ds = ds_repo.create(name="ds-1")
    run = run_repo.create(dataset_id=ds.id, name="r1", target_url="http://x")
    baseline = base_repo.create(name="bl-1", run_id=run.id)

    assert base_repo.delete(baseline.id) is True
    assert base_repo.get_by_name("bl-1") is None


def test_baseline_delete_missing_returns_false(test_session) -> None:
    base_repo = BaselineRepository(test_session)
    assert base_repo.delete(99999) is False
