"""Unit tests for the regression policy loader."""

from pathlib import Path

import pytest

from assay.core.policy.loader import PolicyError, load_policy


def _write(tmp_path: Path, content: str) -> Path:
    """Write content to a temp YAML file and return the path."""
    path = tmp_path / "policy.yaml"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# File-level errors
# ---------------------------------------------------------------------------


def test_policy_file_not_found(tmp_path: Path) -> None:
    """Nonexistent file raises PolicyError."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(PolicyError, match="not found"):
        load_policy(missing)


def test_policy_not_a_mapping(tmp_path: Path) -> None:
    """YAML that is not a mapping raises PolicyError."""
    path = _write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(PolicyError, match="mapping"):
        load_policy(path)


def test_policy_missing_thresholds_key(tmp_path: Path) -> None:
    """A policy without a 'thresholds' key raises PolicyError."""
    path = _write(tmp_path, "version: 1\n")
    with pytest.raises(PolicyError, match="thresholds"):
        load_policy(path)


def test_policy_thresholds_not_a_mapping(tmp_path: Path) -> None:
    """'thresholds' must be a mapping."""
    path = _write(tmp_path, "version: 1\nthresholds:\n  - a\n  - b\n")
    with pytest.raises(PolicyError, match="thresholds"):
        load_policy(path)


# ---------------------------------------------------------------------------
# Key-level errors
# ---------------------------------------------------------------------------


def test_policy_unknown_threshold_key(tmp_path: Path) -> None:
    """Unknown threshold key raises PolicyError."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  unknown_metric: 5.0\n",
    )
    with pytest.raises(PolicyError, match="Unknown threshold key"):
        load_policy(path)


# ---------------------------------------------------------------------------
# Value-level errors
# ---------------------------------------------------------------------------


def test_policy_bool_value_rejected(tmp_path: Path) -> None:
    """A boolean value is rejected (bool is subclass of int in Python)."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness: true\n",
    )
    with pytest.raises(PolicyError):
        load_policy(path)


def test_policy_dict_without_value_key(tmp_path: Path) -> None:
    """A dict threshold without 'value' raises PolicyError."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness:\n    type: relative\n",
    )
    with pytest.raises(PolicyError, match="value"):
        load_policy(path)


def test_policy_dict_value_not_a_number(tmp_path: Path) -> None:
    """A dict threshold with non-numeric 'value' raises PolicyError."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness:\n    value: high\n",
    )
    with pytest.raises(PolicyError, match="value"):
        load_policy(path)


def test_policy_invalid_threshold_type(tmp_path: Path) -> None:
    """Invalid 'type' raises PolicyError."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness:\n    value: 5.0\n    type: weird\n",
    )
    with pytest.raises(PolicyError, match="type"):
        load_policy(path)


def test_policy_negative_value_rejected(tmp_path: Path) -> None:
    """Negative threshold value is rejected."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness: -5.0\n",
    )
    with pytest.raises(PolicyError, match="non-negative"):
        load_policy(path)


def test_policy_invalid_type_for_number_is_ok(tmp_path: Path) -> None:
    """A plain number defaults to type 'relative' (no error)."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness: 5.0\n",
    )
    result = load_policy(path)
    assert result["groundedness"] == {"value": 5.0, "type": "relative"}


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_policy_simple_number_defaults_to_relative(tmp_path: Path) -> None:
    """A plain number is normalized to type 'relative'."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness: 5.0\n",
    )
    result = load_policy(path)
    assert result == {"groundedness": {"value": 5.0, "type": "relative"}}


def test_policy_dict_with_explicit_relative(tmp_path: Path) -> None:
    """Explicit type 'relative' is preserved."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness:\n    value: 5.0\n    type: relative\n",
    )
    result = load_policy(path)
    assert result == {"groundedness": {"value": 5.0, "type": "relative"}}


def test_policy_dict_with_explicit_absolute(tmp_path: Path) -> None:
    """Explicit type 'absolute' is preserved."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  context_recall:\n    value: 0.05\n    type: absolute\n",
    )
    result = load_policy(path)
    assert result == {"context_recall": {"value": 0.05, "type": "absolute"}}


def test_policy_all_valid_keys(tmp_path: Path) -> None:
    """All known keys are accepted."""
    path = _write(
        tmp_path,
        (
            "version: 1\n"
            "thresholds:\n"
            "  groundedness: 5.0\n"
            "  context_recall: 5.0\n"
            "  answer_relevance: 5.0\n"
            "  p95_latency_ms: 20.0\n"
            "  avg_cost_usd: 20.0\n"
        ),
    )
    result = load_policy(path)
    assert set(result.keys()) == {
        "groundedness",
        "context_recall",
        "answer_relevance",
        "p95_latency_ms",
        "avg_cost_usd",
    }
    for key, spec in result.items():
        assert spec["type"] == "relative"
        assert isinstance(spec["value"], float)


def test_policy_empty_thresholds_is_valid(tmp_path: Path) -> None:
    """An empty thresholds mapping returns an empty dict."""
    path = _write(tmp_path, "version: 1\nthresholds: {}\n")
    result = load_policy(path)
    assert result == {}


def test_policy_zero_value_is_valid(tmp_path: Path) -> None:
    """A zero threshold is valid (non-negative)."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness: 0\n",
    )
    result = load_policy(path)
    assert result == {"groundedness": {"value": 0.0, "type": "relative"}}


def test_policy_accepts_string_path(tmp_path: Path) -> None:
    """load_policy accepts a string path."""
    path = _write(
        tmp_path,
        "version: 1\nthresholds:\n  groundedness: 5.0\n",
    )
    result = load_policy(str(path))
    assert result == {"groundedness": {"value": 5.0, "type": "relative"}}