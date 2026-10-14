"""Integration test for citation accuracy in the executor pipeline."""


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


def test_executor_computes_citation_accuracy(test_session, monkeypatch) -> None:
    """Executor computes citation_accuracy when answer has citations."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)

    ds = ds_repo.create(name="citation-ds")
    q_repo.create(dataset_id=ds.id, question="Q?", expected_context="Pasal 5")
    run = run_repo.create(
        dataset_id=ds.id, name="citation-run", target_url="http://mock"
    )

    responses = [
        TargetResponse(
            answer="Berdasarkan Pasal 5, aturannya adalah X.",
            retrieved_contexts=[{"text": "Pasal 5: aturannya adalah X."}],
            latency_ms=1000,
            cost_usd=0.001,
            metadata={},
        )
    ]
    _patch_adapter(monkeypatch, responses)

    summary = execute_run(test_session, run.id, verbose=False)

    assert summary.citation_used == 1

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert len(results) == 1
    assert results[0].citation_accuracy == 1.0


def test_executor_citation_none_when_no_citations(test_session, monkeypatch) -> None:
    """Executor sets citation_accuracy to None when answer has no citations."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)

    ds = ds_repo.create(name="citation-ds-2")
    q_repo.create(dataset_id=ds.id, question="Q?", expected_context="X")
    run = run_repo.create(
        dataset_id=ds.id, name="citation-run-2", target_url="http://mock"
    )

    responses = [
        TargetResponse(
            answer="Jawaban tanpa sitasi.",
            retrieved_contexts=[{"text": "Some context."}],
            latency_ms=1000,
            cost_usd=0.001,
            metadata={},
        )
    ]
    _patch_adapter(monkeypatch, responses)

    summary = execute_run(test_session, run.id, verbose=False)
    assert summary.citation_used == 0

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert results[0].citation_accuracy is None


def test_executor_citation_partial(test_session, monkeypatch) -> None:
    """Two citations, one exists, one does not."""
    ds_repo = DatasetRepository(test_session)
    q_repo = QuestionRepository(test_session)
    run_repo = RunRepository(test_session)

    ds = ds_repo.create(name="citation-ds-3")
    q_repo.create(dataset_id=ds.id, question="Q?", expected_context="Pasal 5")
    run = run_repo.create(
        dataset_id=ds.id, name="citation-run-3", target_url="http://mock"
    )

    responses = [
        TargetResponse(
            answer="Berdasarkan Pasal 5 dan Pasal 99, ...",
            retrieved_contexts=[{"text": "Pasal 5: ..."}],
            latency_ms=1000,
            cost_usd=0.001,
            metadata={},
        )
    ]
    _patch_adapter(monkeypatch, responses)

    execute_run(test_session, run.id, verbose=False)

    res_repo = ResultRepository(test_session)
    results = res_repo.list_by_run(run.id)
    assert results[0].citation_accuracy == 0.5
