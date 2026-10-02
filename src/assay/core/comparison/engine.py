"""Comparison engine: compare a run against a baseline."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from assay.db.models import Baseline, Run
from assay.db.repositories.run import ResultRepository, RunRepository


@dataclass
class MetricDelta:
    """Delta for a single metric between baseline and current run."""

    name: str
    baseline_value: float | None
    current_value: float | None
    delta_absolute: float | None
    delta_percent: float | None
    threshold_percent: float | None
    passed: bool | None
    higher_is_better: bool = True


@dataclass
class WorstFailure:
    """A question where the current run performed worse than baseline."""

    question_id: int
    question_text: str
    baseline_value: float | None
    current_value: float | None
    delta: float | None
    metric: str


@dataclass
class ComparisonReport:
    """Full comparison report between a baseline and a current run."""

    baseline_name: str
    baseline_run_id: int
    current_run_id: int
    metrics: list[MetricDelta] = field(default_factory=list)
    worst_failures: list[WorstFailure] = field(default_factory=list)
    passed: bool = True
    reasons: list[str] = field(default_factory=list)


def _avg(values: list[float]) -> float | None:
    """Average of a list, ignoring None. Returns None if empty."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _percentile(values: list[float], p: float) -> float | None:
    """Simple percentile. p in [0, 1]."""
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    idx = int(len(clean) * p)
    if idx >= len(clean):
        idx = len(clean) - 1
    return clean[idx]


def _delta(
    baseline: float | None,
    current: float | None,
    higher_is_better: bool,
    threshold_percent: float | None,
) -> tuple[float | None, float | None, bool | None]:
    """Compute absolute delta, percent delta, and pass/fail."""
    if baseline is None or current is None:
        return None, None, None

    delta_abs = current - baseline
    delta_pct = None if baseline == 0 else (delta_abs / abs(baseline)) * 100.0

    passed: bool | None = None
    if threshold_percent is not None and delta_pct is not None:
        # threshold_percent is the maximum allowed regression (positive number).
        # For higher_is_better, regression means delta_pct < -threshold.
        # For lower_is_better, regression means delta_pct > +threshold.
        passed = (
            delta_pct >= -threshold_percent
            if higher_is_better
            else delta_pct <= threshold_percent
        )

    return delta_abs, delta_pct, passed


def compare_runs(
    session: Session,
    baseline: Baseline,
    current_run: Run,
    thresholds: dict[str, Any] | None = None,
    top_failures: int = 5,
) -> ComparisonReport:
    """Compare a current run against a baseline.

    Thresholds is a dict like:
    {
        "groundedness": 5.0,
        "context_recall": 5.0,
        "p95_latency_ms": 20.0,
        "avg_cost_usd": 20.0,
    }
    Numbers are maximum allowed regression in percent.
    """
    thresholds = thresholds or {}

    baseline_run_repo = RunRepository(session)
    baseline_run = baseline_run_repo.get(baseline.run_id)
    if baseline_run is None:
        raise ValueError(f"Baseline run {baseline.run_id} not found")

    result_repo = ResultRepository(session)
    baseline_results = result_repo.list_by_run(baseline.run_id)
    current_results = result_repo.list_by_run(current_run.id)

    if not baseline_results:
        raise ValueError(f"Baseline run {baseline.run_id} has no results")
    if not current_results:
        raise ValueError(f"Current run {current_run.id} has no results")

    # Compute aggregate metrics
    baseline_groundedness = _avg([r.groundedness for r in baseline_results if r.groundedness is not None])
    current_groundedness = _avg([r.groundedness for r in current_results if r.groundedness is not None])

    baseline_recall = _avg([r.context_recall for r in baseline_results if r.context_recall is not None])
    current_recall = _avg([r.context_recall for r in current_results if r.context_recall is not None])

    baseline_p95 = _percentile([r.latency_ms for r in baseline_results if r.latency_ms is not None], 0.95)
    current_p95 = _percentile([r.latency_ms for r in current_results if r.latency_ms is not None], 0.95)

    baseline_cost = _avg([r.cost_usd for r in baseline_results if r.cost_usd is not None])
    current_cost = _avg([r.cost_usd for r in current_results if r.cost_usd is not None])

    report = ComparisonReport(
        baseline_name=baseline.name,
        baseline_run_id=baseline.run_id,
        current_run_id=current_run.id,
    )

    metrics_config = [
        ("groundedness", baseline_groundedness, current_groundedness, True, "groundedness"),
        ("context_recall", baseline_recall, current_recall, True, "context_recall"),
        ("p95_latency_ms", baseline_p95, current_p95, False, "p95_latency_ms"),
        ("avg_cost_usd", baseline_cost, current_cost, False, "avg_cost_usd"),
    ]

    for name, base_val, curr_val, higher_better, threshold_key in metrics_config:
        threshold = thresholds.get(threshold_key)
        delta_abs, delta_pct, passed = _delta(base_val, curr_val, higher_better, threshold)
        metric = MetricDelta(
            name=name,
            baseline_value=base_val,
            current_value=curr_val,
            delta_absolute=delta_abs,
            delta_percent=delta_pct,
            threshold_percent=threshold,
            passed=passed,
            higher_is_better=higher_better,
        )
        report.metrics.append(metric)

        if passed is False:
            report.passed = False
            direction = "dropped" if higher_better else "increased"
            report.reasons.append(
                f"{name} {direction} by {abs(delta_pct):.1f}% "
                f"(threshold {threshold}%)"
            )

    # Worst failures: questions where groundedness dropped the most
    baseline_by_q = {r.question_id: r for r in baseline_results}
    current_by_q = {r.question_id: r for r in current_results}

    failure_candidates: list[WorstFailure] = []
    for qid, curr_res in current_by_q.items():
        base_res = baseline_by_q.get(qid)
        if base_res is None:
            continue
        if base_res.groundedness is None or curr_res.groundedness is None:
            continue
        delta = curr_res.groundedness - base_res.groundedness
        if delta < 0:
            failure_candidates.append(
                WorstFailure(
                    question_id=qid,
                    question_text=curr_res.question.question if curr_res.question else "",
                    baseline_value=base_res.groundedness,
                    current_value=curr_res.groundedness,
                    delta=delta,
                    metric="groundedness",
                )
            )

    failure_candidates.sort(key=lambda f: f.delta if f.delta is not None else 0)
    report.worst_failures = failure_candidates[:top_failures]

    return report
