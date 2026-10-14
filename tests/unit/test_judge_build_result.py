"""Unit tests for judge._build_result (no API key required)."""

import pytest

from assay.core.metrics.judge import JudgeError, _build_result


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_build_result_all_supported() -> None:
    parsed = {
        "claims": [
            {
                "claim": "The rate limit is 100 per minute.",
                "verdict": "supported",
                "evidence": "rate limit is 100 per minute",
            }
        ],
        "abstained": False,
        "reason": "All supported.",
    }
    contexts = ["The rate limit is 100 per minute for all users."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.grounded is True
    assert result.score == 1.0
    assert result.abstained is False
    assert len(result.claims) == 1
    assert result.claims[0].verdict == "supported"
    assert result.claims[0].downgraded is False


def test_build_result_multiple_supported() -> None:
    parsed = {
        "claims": [
            {
                "claim": "Claim A",
                "verdict": "supported",
                "evidence": "first fact",
            },
            {
                "claim": "Claim B",
                "verdict": "supported",
                "evidence": "second fact",
            },
        ],
        "abstained": False,
        "reason": "All supported.",
    }
    contexts = ["Here is the first fact and the second fact."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.grounded is True
    assert result.score == 1.0


# ---------------------------------------------------------------------------
# Unsupported / downgrade paths
# ---------------------------------------------------------------------------


def test_build_result_one_unsupported() -> None:
    parsed = {
        "claims": [
            {
                "claim": "Claim A",
                "verdict": "supported",
                "evidence": "fact A",
            },
            {
                "claim": "Claim B",
                "verdict": "unsupported",
                "evidence": None,
            },
        ],
        "abstained": False,
        "reason": "One unsupported.",
    }
    contexts = ["Here is fact A."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.grounded is False
    assert result.score == 0.5


def test_build_result_evidence_not_found_downgrades() -> None:
    """If evidence is not in contexts, supported is downgraded to unsupported."""
    parsed = {
        "claims": [
            {
                "claim": "Claim A",
                "verdict": "supported",
                "evidence": "this text is not in the context",
            }
        ],
        "abstained": False,
        "reason": "Looks supported.",
    }
    contexts = ["Completely different context."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.grounded is False
    assert result.score == 0.0
    assert result.claims[0].verdict == "unsupported"
    assert result.claims[0].downgraded is True
    assert "evidence not found" in result.claims[0].reason


def test_build_result_contradicted() -> None:
    parsed = {
        "claims": [
            {
                "claim": "The rate limit is 1000.",
                "verdict": "contradicted",
                "evidence": None,
            }
        ],
        "abstained": False,
        "reason": "Contradicted by context.",
    }
    contexts = ["The rate limit is 100."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.grounded is False
    assert result.score == 0.0
    assert result.claims[0].verdict == "contradicted"


def test_build_result_ambiguous() -> None:
    parsed = {
        "claims": [
            {
                "claim": "Something unclear.",
                "verdict": "ambiguous",
                "evidence": None,
            }
        ],
        "abstained": False,
        "reason": "Ambiguous.",
    }
    contexts = ["Context A.", "Context B conflicts."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.grounded is False
    assert result.score == 0.0


def test_build_result_invalid_verdict_falls_back_to_unsupported() -> None:
    parsed = {
        "claims": [
            {
                "claim": "Claim A",
                "verdict": "totally-invalid-verdict",
                "evidence": None,
            }
        ],
        "abstained": False,
        "reason": "Weird verdict.",
    }
    contexts = ["Context."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.claims[0].verdict == "unsupported"
    assert result.grounded is False


# ---------------------------------------------------------------------------
# Abstention paths
# ---------------------------------------------------------------------------


def test_build_result_abstained() -> None:
    parsed = {
        "claims": [],
        "abstained": True,
        "reason": "Bare refusal.",
    }
    contexts = ["Anything."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.abstained is True
    assert result.grounded is True  # abstained is treated as grounded
    assert result.score == 1.0
    assert result.claims == []


def test_build_result_abstained_with_claims_is_not_abstained() -> None:
    """An abstention that smuggles claims is not treated as abstained."""
    parsed = {
        "claims": [
            {
                "claim": "I cannot answer but here is a fact.",
                "verdict": "unsupported",
                "evidence": None,
            }
        ],
        "abstained": True,
        "reason": "Refusal with a claim.",
    }
    contexts = ["Context."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.abstained is False
    assert result.grounded is False
    assert len(result.claims) == 1


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_build_result_no_claims_no_abstain_raises() -> None:
    parsed = {"claims": [], "abstained": False, "reason": "Oops."}
    with pytest.raises(JudgeError, match="no claims"):
        _build_result(parsed, ["ctx"], raw="{}")


def test_build_result_claims_not_a_list_raises() -> None:
    parsed = {"claims": "not a list", "abstained": False, "reason": "Bad."}
    with pytest.raises(JudgeError, match="must be a list"):
        _build_result(parsed, ["ctx"], raw="{}")


def test_build_result_skips_non_dict_claims() -> None:
    parsed = {
        "claims": [
            "not a dict",
            {
                "claim": "Valid claim",
                "verdict": "supported",
                "evidence": "valid fact",
            },
        ],
        "abstained": False,
        "reason": "Mixed.",
    }
    contexts = ["This is a valid fact."]

    result = _build_result(parsed, contexts, raw="{}")
    assert len(result.claims) == 1
    assert result.claims[0].text == "Valid claim"


def test_build_result_score_fraction() -> None:
    parsed = {
        "claims": [
            {"claim": "A", "verdict": "supported", "evidence": "fact a"},
            {"claim": "B", "verdict": "supported", "evidence": "fact b"},
            {"claim": "C", "verdict": "unsupported", "evidence": None},
            {"claim": "D", "verdict": "unsupported", "evidence": None},
        ],
        "abstained": False,
        "reason": "Mixed.",
    }
    contexts = ["We have fact a and fact b in here."]

    result = _build_result(parsed, contexts, raw="{}")
    assert result.grounded is False
    assert result.score == 0.5
