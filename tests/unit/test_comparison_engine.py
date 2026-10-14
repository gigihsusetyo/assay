"""Unit tests for comparison engine pure functions (no DB required)."""

import pytest

from assay.core.comparison.engine import (
    _avg,
    _delta,
    _normalize_threshold,
    _percentile,
)

# ---------------------------------------------------------------------------
# _avg
# ---------------------------------------------------------------------------


def test_avg_empty_returns_none() -> None:
    assert _avg([]) is None


def test_avg_all_none_returns_none() -> None:
    assert _avg([None, None]) is None


def test_avg_single_value() -> None:
    assert _avg([0.5]) == 0.5


def test_avg_multiple_values() -> None:
    assert _avg([0.0, 0.5, 1.0]) == 0.5


def test_avg_ignores_none() -> None:
    assert _avg([0.5, None, 0.5]) == 0.5


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------


def test_percentile_empty_returns_none() -> None:
    assert _percentile([], 0.5) is None


def test_percentile_all_none_returns_none() -> None:
    assert _percentile([None, None], 0.5) is None


def test_percentile_single_value() -> None:
    assert _percentile([100], 0.95) == 100


def test_percentile_p50() -> None:
    # 1..10, p50 -> idx int(10*0.5)=5 -> value 6 (0-indexed)
    assert _percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.5) == 6


def test_percentile_p95_with_10_values() -> None:
    # idx int(10*0.95)=9 -> value 10
    assert _percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.95) == 10


def test_percentile_p100_clamps_to_last() -> None:
    assert _percentile([1, 2, 3], 1.0) == 3


def test_percentile_ignores_none() -> None:
    assert _percentile([100, None, 200], 0.95) == 200


# ---------------------------------------------------------------------------
# _delta — relative thresholds
# ---------------------------------------------------------------------------


def test_delta_higher_is_better_no_regression() -> None:
    """Current is higher -> pass for higher_is_better."""
    delta_abs, delta_pct, passed = _delta(
        baseline=0.80, current=0.85, higher_is_better=True,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_abs == pytest.approx(0.05)
    assert delta_pct == pytest.approx(6.25)
    assert passed is True


def test_delta_higher_is_better_within_threshold() -> None:
    """Drop of 2% within 5% threshold -> pass."""
    delta_abs, delta_pct, passed = _delta(
        baseline=0.80, current=0.784, higher_is_better=True,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_pct == pytest.approx(-2.0)
    assert passed is True


def test_delta_higher_is_better_beyond_threshold() -> None:
    """Drop of 10% exceeds 5% threshold -> fail."""
    delta_abs, delta_pct, passed = _delta(
        baseline=0.80, current=0.72, higher_is_better=True,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_pct == pytest.approx(-10.0)
    assert passed is False


def test_delta_lower_is_better_no_regression() -> None:
    """Current is lower -> pass for lower_is_better (latency, cost)."""
    delta_abs, delta_pct, passed = _delta(
        baseline=100.0, current=90.0, higher_is_better=False,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_pct == pytest.approx(-10.0)
    assert passed is True


def test_delta_lower_is_better_beyond_threshold() -> None:
    """Latency rose 10% > 5% threshold -> fail."""
    delta_abs, delta_pct, passed = _delta(
        baseline=100.0, current=110.0, higher_is_better=False,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_pct == pytest.approx(10.0)
    assert passed is False


def test_delta_baseline_zero_current_zero() -> None:
    """0 -> 0 is not a regression, percent is 0."""
    delta_abs, delta_pct, passed = _delta(
        baseline=0.0, current=0.0, higher_is_better=True,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_abs == 0.0
    assert delta_pct == 0.0
    assert passed is True


def test_delta_baseline_zero_current_nonzero() -> None:
    """0 -> non-zero: percent undefined (None), but absolute works for absolute threshold."""
    delta_abs, delta_pct, passed = _delta(
        baseline=0.0, current=0.5, higher_is_better=True,
        threshold_value=None, threshold_type="relative",
    )
    assert delta_abs == 0.5
    assert delta_pct is None
    assert passed is None


# ---------------------------------------------------------------------------
# _delta — absolute thresholds
# ---------------------------------------------------------------------------


def test_delta_absolute_higher_is_better_within() -> None:
    delta_abs, _, passed = _delta(
        baseline=0.90, current=0.87, higher_is_better=True,
        threshold_value=0.05, threshold_type="absolute",
    )
    assert delta_abs == pytest.approx(-0.03)
    assert passed is True


def test_delta_absolute_higher_is_better_beyond() -> None:
    delta_abs, _, passed = _delta(
        baseline=0.90, current=0.80, higher_is_better=True,
        threshold_value=0.05, threshold_type="absolute",
    )
    assert passed is False


def test_delta_absolute_lower_is_better_within() -> None:
    delta_abs, _, passed = _delta(
        baseline=100.0, current=103.0, higher_is_better=False,
        threshold_value=5.0, threshold_type="absolute",
    )
    assert passed is True


def test_delta_absolute_lower_is_better_beyond() -> None:
    delta_abs, _, passed = _delta(
        baseline=100.0, current=110.0, higher_is_better=False,
        threshold_value=5.0, threshold_type="absolute",
    )
    assert passed is False


def test_delta_none_baseline_returns_none() -> None:
    delta_abs, delta_pct, passed = _delta(
        baseline=None, current=0.9, higher_is_better=True,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_abs is None
    assert delta_pct is None
    assert passed is None


def test_delta_none_current_returns_none() -> None:
    delta_abs, delta_pct, passed = _delta(
        baseline=0.9, current=None, higher_is_better=True,
        threshold_value=5.0, threshold_type="relative",
    )
    assert delta_abs is None
    assert passed is None


def test_delta_no_threshold_passed_none() -> None:
    """Without threshold, we don't judge pass/fail."""
    delta_abs, delta_pct, passed = _delta(
        baseline=0.9, current=0.8, higher_is_better=True,
        threshold_value=None, threshold_type="relative",
    )
    assert delta_abs == pytest.approx(-0.1)
    assert passed is None


# ---------------------------------------------------------------------------
# _normalize_threshold
# ---------------------------------------------------------------------------


def test_normalize_threshold_none() -> None:
    value, ttype = _normalize_threshold(None)
    assert value is None
    assert ttype == "relative"


def test_normalize_threshold_number_defaults_relative() -> None:
    value, ttype = _normalize_threshold(5.0)
    assert value == 5.0
    assert ttype == "relative"


def test_normalize_threshold_int() -> None:
    value, ttype = _normalize_threshold(10)
    assert value == 10.0
    assert ttype == "relative"


def test_normalize_threshold_dict_with_value_only() -> None:
    value, ttype = _normalize_threshold({"value": 5.0})
    assert value == 5.0
    assert ttype == "relative"


def test_normalize_threshold_dict_with_absolute_type() -> None:
    value, ttype = _normalize_threshold({"value": 0.05, "type": "absolute"})
    assert value == 0.05
    assert ttype == "absolute"


def test_normalize_threshold_dict_with_relative_type() -> None:
    value, ttype = _normalize_threshold({"value": 5.0, "type": "relative"})
    assert value == 5.0
    assert ttype == "relative"


def test_normalize_threshold_dict_missing_value_returns_none() -> None:
    value, ttype = _normalize_threshold({"type": "absolute"})
    assert value is None
    assert ttype == "relative"


def test_normalize_threshold_dict_invalid_type_raises() -> None:
    with pytest.raises(ValueError, match="Invalid threshold type"):
        _normalize_threshold({"value": 5.0, "type": "weird"})


def test_normalize_threshold_invalid_spec_raises() -> None:
    with pytest.raises(ValueError, match="Invalid threshold spec"):
        _normalize_threshold("not a number or dict")
