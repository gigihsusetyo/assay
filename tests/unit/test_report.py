"""Unit tests for report formatters (to_json, to_junit)."""

import json
import xml.etree.ElementTree as ET

from assay.core.comparison.engine import (
    ComparisonReport,
    MetricDelta,
    WorstFailure,
)
from assay.core.report import to_json, to_junit


def _make_report(
    metrics: list[MetricDelta] | None = None,
    worst_failures: list[WorstFailure] | None = None,
    passed: bool = True,
    reasons: list[str] | None = None,
) -> ComparisonReport:
    """Build a ComparisonReport with sensible defaults for testing."""
    return ComparisonReport(
        baseline_name="baseline-v1",
        baseline_run_id=1,
        current_run_id=2,
        metrics=metrics or [],
        worst_failures=worst_failures or [],
        passed=passed,
        reasons=reasons or [],
    )


def _metric(
    name: str = "groundedness",
    baseline: float | None = 0.90,
    current: float | None = 0.85,
    delta_absolute: float | None = -0.05,
    delta_percent: float | None = -5.56,
    threshold_value: float | None = 5.0,
    threshold_type: str = "relative",
    passed: bool | None = False,
    higher_is_better: bool = True,
) -> MetricDelta:
    return MetricDelta(
        name=name,
        baseline_value=baseline,
        current_value=current,
        delta_absolute=delta_absolute,
        delta_percent=delta_percent,
        threshold_value=threshold_value,
        threshold_type=threshold_type,
        passed=passed,
        higher_is_better=higher_is_better,
    )


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------


def test_to_json_empty_report_is_valid_json() -> None:
    report = _make_report()
    payload = json.loads(to_json(report))
    assert payload["baseline_name"] == "baseline-v1"
    assert payload["baseline_run_id"] == 1
    assert payload["current_run_id"] == 2
    assert payload["passed"] is True
    assert payload["metrics"] == []
    assert payload["worst_failures"] == []
    assert payload["reasons"] == []


def test_to_json_includes_metric_fields() -> None:
    report = _make_report(metrics=[_metric()])
    payload = json.loads(to_json(report))
    assert len(payload["metrics"]) == 1
    m = payload["metrics"][0]
    assert m["name"] == "groundedness"
    assert m["baseline"] == 0.90
    assert m["current"] == 0.85
    assert m["delta_absolute"] == -0.05
    assert m["delta_percent"] == -5.56
    assert m["threshold_value"] == 5.0
    assert m["threshold_type"] == "relative"
    assert m["higher_is_better"] is True
    assert m["passed"] is False


def test_to_json_handles_none_values() -> None:
    report = _make_report(
        metrics=[_metric(baseline=None, current=None, delta_absolute=None, delta_percent=None, passed=None)]
    )
    payload = json.loads(to_json(report))
    m = payload["metrics"][0]
    assert m["baseline"] is None
    assert m["current"] is None
    assert m["delta_absolute"] is None
    assert m["delta_percent"] is None
    assert m["passed"] is None


def test_to_json_includes_worst_failures() -> None:
    failure = WorstFailure(
        question_id=42,
        question_text="How do I reset my password?",
        baseline_value=0.95,
        current_value=0.42,
        delta=-0.53,
        metric="groundedness",
    )
    report = _make_report(worst_failures=[failure])
    payload = json.loads(to_json(report))
    assert len(payload["worst_failures"]) == 1
    f = payload["worst_failures"][0]
    assert f["question_id"] == 42
    assert f["question"] == "How do I reset my password?"
    assert f["baseline"] == 0.95
    assert f["current"] == 0.42
    assert f["delta"] == -0.53
    assert f["metric"] == "groundedness"


def test_to_json_preserves_reasons_and_passed() -> None:
    report = _make_report(
        passed=False,
        reasons=[
            "groundedness dropped by 5.6% (threshold 5.0% relative)",
        ],
    )
    payload = json.loads(to_json(report))
    assert payload["passed"] is False
    assert payload["reasons"] == [
        "groundedness dropped by 5.6% (threshold 5.0% relative)",
    ]


def test_to_json_unicode_not_escaped() -> None:
    report = _make_report(
        worst_failures=[
            WorstFailure(
                question_id=1,
                question_text="Apa itu \"Stabilitas Sistem Keuangan\"?",
                baseline_value=0.9,
                current_value=0.5,
                delta=-0.4,
                metric="groundedness",
            )
        ]
    )
    text = to_json(report)
    # ensure_ascii=False should keep unicode characters raw
    assert "Apa itu" in text
    assert "Stabilitas Sistem Keuangan" in text


# ---------------------------------------------------------------------------
# to_junit
# ---------------------------------------------------------------------------


def test_to_junit_empty_report() -> None:
    report = _make_report()
    xml_text = to_junit(report)
    root = ET.fromstring(xml_text)
    assert root.tag == "testsuite"
    assert root.attrib["name"] == "assay-gate"
    assert root.attrib["tests"] == "0"
    assert root.attrib["failures"] == "0"
    assert len(list(root)) == 0


def test_to_junit_passing_metric() -> None:
    report = _make_report(
        metrics=[_metric(passed=True, delta_absolute=0.01, delta_percent=1.0)],
    )
    xml_text = to_junit(report)
    root = ET.fromstring(xml_text)
    assert root.attrib["tests"] == "1"
    assert root.attrib["failures"] == "0"
    cases = list(root)
    assert len(cases) == 1
    assert cases[0].tag == "testcase"
    assert cases[0].attrib["name"] == "groundedness"
    assert cases[0].attrib["classname"] == "assay"
    # no failure children
    assert len(list(cases[0])) == 0


def test_to_junit_failing_metric_has_failure() -> None:
    report = _make_report(
        metrics=[_metric(passed=False)],
    )
    xml_text = to_junit(report)
    root = ET.fromstring(xml_text)
    assert root.attrib["tests"] == "1"
    assert root.attrib["failures"] == "1"
    case = list(root)[0]
    failures = list(case)
    assert len(failures) == 1
    assert failures[0].tag == "failure"
    assert "regressed" in failures[0].attrib["message"]


def test_to_junit_mixed_metrics() -> None:
    report = _make_report(
        metrics=[
            _metric(name="groundedness", passed=True),
            _metric(name="context_recall", passed=False),
            _metric(name="answer_relevance", passed=True),
        ],
    )
    xml_text = to_junit(report)
    root = ET.fromstring(xml_text)
    assert root.attrib["tests"] == "3"
    assert root.attrib["failures"] == "1"


def test_to_junit_failure_message_contains_delta() -> None:
    report = _make_report(metrics=[_metric(passed=False)])
    xml_text = to_junit(report)
    root = ET.fromstring(xml_text)
    case = list(root)[0]
    failure = list(case)[0]
    msg = failure.attrib["message"]
    assert "Baseline=0.9" in msg
    assert "Current=0.85" in msg
    assert "Delta=-0.0500" in msg
    assert "-5.56%" in msg
    assert "Threshold=5.0 relative" in msg


def test_to_junit_escapes_special_chars_in_message() -> None:
    """Messages with &, <, >, quotes are escaped properly."""
    metric = _metric(name="metric<with>special&chars", passed=False)
    report = _make_report(metrics=[metric])
    xml_text = to_junit(report)
    # ET.fromstring should parse without error if escaping is correct
    root = ET.fromstring(xml_text)
    case = list(root)[0]
    assert case.attrib["name"] == "metric<with>special&chars"


def test_to_junit_passed_none_no_failure() -> None:
    """A metric with passed=None is not counted as failure."""
    report = _make_report(metrics=[_metric(passed=None)])
    xml_text = to_junit(report)
    root = ET.fromstring(xml_text)
    assert root.attrib["tests"] == "1"
    assert root.attrib["failures"] == "0"
    case = list(root)[0]
    assert len(list(case)) == 0
