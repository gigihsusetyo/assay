"""Unit tests for judge._build_relevance_result (no API key required)."""

import pytest

from assay.core.metrics.judge import JudgeError, _build_relevance_result

# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_relevance_all_addressed() -> None:
    parsed = {
        "aspects": [
            {"aspect": "the capital", "addressed": True, "reason": "Stated."},
        ],
        "reason": "All addressed.",
    }
    result = _build_relevance_result(parsed, raw="{}")
    assert result.relevant is True
    assert result.score == 1.0
    assert len(result.aspects) == 1
    assert result.aspects[0].addressed is True


def test_relevance_two_aspects_both_addressed() -> None:
    parsed = {
        "aspects": [
            {"aspect": "rate limit", "addressed": True, "reason": "Stated."},
            {"aspect": "how to increase it", "addressed": True, "reason": "Explained."},
        ],
        "reason": "All addressed.",
    }
    result = _build_relevance_result(parsed, raw="{}")
    assert result.relevant is True
    assert result.score == 1.0


# ---------------------------------------------------------------------------
# Partial / not-addressed paths
# ---------------------------------------------------------------------------


def test_relevance_partial() -> None:
    parsed = {
        "aspects": [
            {"aspect": "rate limit", "addressed": True, "reason": "Stated."},
            {"aspect": "how to increase it", "addressed": False, "reason": "Ignored."},
        ],
        "reason": "Partial.",
    }
    result = _build_relevance_result(parsed, raw="{}")
    assert result.relevant is False
    assert result.score == 0.5


def test_relevance_none_addressed() -> None:
    parsed = {
        "aspects": [
            {"aspect": "rate limit", "addressed": False, "reason": "Ignored."},
        ],
        "reason": "Not addressed.",
    }
    result = _build_relevance_result(parsed, raw="{}")
    assert result.relevant is False
    assert result.score == 0.0


def test_relevance_missing_addressed_field_defaults_false() -> None:
    parsed = {
        "aspects": [{"aspect": "something", "reason": "no field"}],
        "reason": "Missing field.",
    }
    result = _build_relevance_result(parsed, raw="{}")
    assert result.aspects[0].addressed is False
    assert result.relevant is False


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_relevance_no_aspects_raises() -> None:
    parsed = {"aspects": [], "reason": "Empty."}
    with pytest.raises(JudgeError, match="no aspects"):
        _build_relevance_result(parsed, raw="{}")


def test_relevance_aspects_not_a_list_raises() -> None:
    parsed = {"aspects": "not a list", "reason": "Bad."}
    with pytest.raises(JudgeError, match="must be a list"):
        _build_relevance_result(parsed, raw="{}")


def test_relevance_skips_non_dict_aspects() -> None:
    parsed = {
        "aspects": [
            "not a dict",
            {"aspect": "valid", "addressed": True, "reason": "ok"},
        ],
        "reason": "Mixed.",
    }
    result = _build_relevance_result(parsed, raw="{}")
    assert len(result.aspects) == 1
    assert result.aspects[0].text == "valid"


def test_relevance_missing_aspects_key_raises() -> None:
    parsed = {"reason": "No aspects key."}
    with pytest.raises(JudgeError, match="no aspects"):
        _build_relevance_result(parsed, raw="{}")


def test_relevance_raw_response_preserved() -> None:
    parsed = {
        "aspects": [{"aspect": "x", "addressed": True, "reason": "ok"}],
        "reason": "ok",
    }
    result = _build_relevance_result(parsed, raw="raw response text")
    assert result.raw_response == "raw response text"


def test_relevance_score_fraction() -> None:
    parsed = {
        "aspects": [
            {"aspect": "a", "addressed": True, "reason": ""},
            {"aspect": "b", "addressed": True, "reason": ""},
            {"aspect": "c", "addressed": True, "reason": ""},
            {"aspect": "d", "addressed": False, "reason": ""},
        ],
        "reason": "3 of 4.",
    }
    result = _build_relevance_result(parsed, raw="{}")
    assert result.relevant is False
    assert result.score == 0.75
