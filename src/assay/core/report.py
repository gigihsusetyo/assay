"""Report formatters for Assay comparison results."""

import json
from typing import Any

from assay.core.comparison.engine import ComparisonReport


def to_json(report: ComparisonReport) -> str:
    """Format a comparison report as JSON.

    This is the machine-readable format for CI integration.
    """
    metrics: list[dict[str, Any]] = []
    for m in report.metrics:
        metrics.append({
            "name": m.name,
            "baseline": m.baseline_value,
            "current": m.current_value,
            "delta_absolute": m.delta_absolute,
            "delta_percent": m.delta_percent,
            "threshold_value": m.threshold_value,
            "threshold_type": m.threshold_type,
            "higher_is_better": m.higher_is_better,
            "passed": m.passed,
        })

    failures: list[dict[str, Any]] = []
    for f in report.worst_failures:
        failures.append({
            "question_id": f.question_id,
            "question": f.question_text,
            "baseline": f.baseline_value,
            "current": f.current_value,
            "delta": f.delta,
            "metric": f.metric,
        })

    payload = {
        "baseline_name": report.baseline_name,
        "baseline_run_id": report.baseline_run_id,
        "current_run_id": report.current_run_id,
        "passed": report.passed,
        "reasons": report.reasons,
        "metrics": metrics,
        "worst_failures": failures,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _xml_escape(text: str) -> str:
    """Escape XML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def to_junit(report: ComparisonReport) -> str:
    """Format a comparison report as JUnit XML.

    Each metric becomes a test case. Failed metrics become failures.
    This works with CI systems that understand JUnit.
    """
    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')

    total = len(report.metrics)
    failures = sum(1 for m in report.metrics if m.passed is False)

    lines.append(
        f'<testsuite name="assay-gate" tests="{total}" failures="{failures}">'
    )

    for m in report.metrics:
        test_name = _xml_escape(m.name)
        lines.append(f'  <testcase name="{test_name}" classname="assay">')
        if m.passed is False:
            delta_pct_str = (
                f"{m.delta_percent:+.2f}%"
                if m.delta_percent is not None
                else "N/A"
            )
            delta_abs_str = (
                f"{m.delta_absolute:+.4f}"
                if m.delta_absolute is not None
                else "N/A"
            )
            msg = (
                f"{m.name} regressed. "
                f"Baseline={m.baseline_value}, Current={m.current_value}, "
                f"Delta={delta_abs_str} ({delta_pct_str}), "
                f"Threshold={m.threshold_value} {m.threshold_type}"
            )
            lines.append(
                f'    <failure message="{_xml_escape(msg)}" />'
            )
        lines.append("  </testcase>")

    lines.append("</testsuite>")
    return "\n".join(lines)
