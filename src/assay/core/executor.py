"""Run executor: evaluate a dataset against a RAG target."""

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from assay.adapters.http_target import HTTPTargetAdapter, TargetError
from assay.config import settings
from assay.core.metrics.judge import (
    JudgeError,
    judge_answer_relevance,
    judge_groundedness,
)
from assay.core.metrics.simple import context_recall, groundedness
from assay.db.models import RunStatus
from assay.db.repositories.dataset import QuestionRepository
from assay.db.repositories.run import ResultRepository, RunRepository


@dataclass
class ExecutionSummary:
    """Summary of a run execution."""

    run_id: int
    total: int
    succeeded: int
    failed: int
    total_latency_ms: int
    total_cost_usd: float
    judge_used: int
    relevance_used: int


def execute_run(
    session: Session,
    run_id: int,
    verbose: bool = False,
    use_judge: bool = False,
) -> ExecutionSummary:
    """Execute a run: call the target for each question, store results.

    If use_judge is True and the judge is configured, groundedness and
    answer relevance are computed with the LLM-as-judge. Otherwise, only
    simple heuristics are used for groundedness.

    Returns a summary of the execution.
    """
    run_repo = RunRepository(session)
    result_repo = ResultRepository(session)
    q_repo = QuestionRepository(session)

    run = run_repo.get(run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    if run.status not in (RunStatus.PENDING.value, RunStatus.FAILED.value):
        raise ValueError(
            f"Run {run_id} has status '{run.status}', cannot execute. "
            f"Only pending or failed runs can be executed."
        )

    run_repo.mark_running(run_id)

    questions = q_repo.list_by_dataset(run.dataset_id)
    if not questions:
        run_repo.mark_failed(run_id, "Dataset has no questions")
        raise ValueError(f"Dataset {run.dataset_id} has no questions")

    adapter = HTTPTargetAdapter(run.target_url)

    judge_active = use_judge and settings.judge_enabled
    if use_judge and not settings.judge_enabled and verbose:
        print("  Judge requested but not configured. Falling back to simple metrics.")

    succeeded = 0
    failed = 0
    total_latency = 0
    total_cost = 0.0
    judge_used = 0
    relevance_used = 0

    for q in questions:
        try:
            response = adapter.query(
                question=q.question,
                dataset_id=str(run.dataset_id),
                run_id=str(run.id),
            )
            contexts = [
                c.get("text", "")
                for c in response.retrieved_contexts
                if isinstance(c, dict)
            ]

            # Groundedness: try judge first, fallback to simple
            g: float | None = None
            if judge_active:
                try:
                    jr = judge_groundedness(q.question, response.answer, contexts)
                    g = jr.score
                    judge_used += 1
                    if verbose:
                        print(f"  Q{q.id}: judge groundedness={g:.2f}")
                except JudgeError as e:
                    if verbose:
                        print(f"  Q{q.id}: groundedness judge failed ({e}), using simple metrics")
                    g = groundedness(response.answer, contexts)
            else:
                g = groundedness(response.answer, contexts)

            # Answer relevance: only with judge
            ar: float | None = None
            if judge_active:
                try:
                    rr = judge_answer_relevance(q.question, response.answer)
                    ar = rr.score
                    relevance_used += 1
                    if verbose:
                        print(f"  Q{q.id}: answer relevance={ar:.2f}")
                except JudgeError as e:
                    if verbose:
                        print(f"  Q{q.id}: relevance judge failed ({e})")
                    ar = None

            r = context_recall(q.expected_context, contexts)
            result_repo.create(
                run_id=run.id,
                question_id=q.id,
                answer=response.answer,
                retrieved_contexts=json.dumps(response.retrieved_contexts),
                groundedness=g,
                context_recall=r,
                answer_relevance=ar,
                latency_ms=response.latency_ms,
                cost_usd=response.cost_usd,
            )
            succeeded += 1
            total_latency += response.latency_ms
            if response.cost_usd is not None:
                total_cost += response.cost_usd
            if verbose and not judge_active:
                print(f"  Q{q.id}: groundedness={g:.2f}, latency={response.latency_ms}ms")
        except TargetError as e:
            result_repo.create(
                run_id=run.id,
                question_id=q.id,
                error_message=str(e),
            )
            failed += 1
            if verbose:
                print(f"  Q{q.id}: FAILED - {e}")

    if failed == len(questions):
        run_repo.mark_failed(run_id, f"All {failed} questions failed")
    else:
        run_repo.mark_completed(run_id)

    return ExecutionSummary(
        run_id=run.id,
        total=len(questions),
        succeeded=succeeded,
        failed=failed,
        total_latency_ms=total_latency,
        total_cost_usd=total_cost,
        judge_used=judge_used,
        relevance_used=relevance_used,
    )
