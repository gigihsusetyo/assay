"""Unit tests for judge.py pure functions (no API key required)."""

from assay.core.metrics.judge import (
    _extract_json,
    _normalize,
    _strip_context_prefix,
    _verify_evidence,
)


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


def test_normalize_lowercases() -> None:
    assert _normalize("HELLO World") == "hello world"


def test_normalize_collapses_whitespace() -> None:
    assert _normalize("hello    world\n\nfoo") == "hello world foo"


def test_normalize_strips_edges() -> None:
    assert _normalize("   hello   ") == "hello"


def test_normalize_empty() -> None:
    assert _normalize("") == ""


# ---------------------------------------------------------------------------
# _strip_context_prefix
# ---------------------------------------------------------------------------


def test_strip_prefix_single_digit() -> None:
    assert _strip_context_prefix("[1] hello") == "hello"


def test_strip_prefix_multi_digit() -> None:
    assert _strip_context_prefix("[12] hello") == "hello"


def test_strip_prefix_no_brackets() -> None:
    assert _strip_context_prefix("hello") == "hello"


def test_strip_prefix_only_leading() -> None:
    assert _strip_context_prefix("[1] a [2] b") == "a [2] b"


def test_strip_prefix_whitespace_variants() -> None:
    assert _strip_context_prefix("  [3]   hello") == "hello"


# ---------------------------------------------------------------------------
# _verify_evidence
# ---------------------------------------------------------------------------


def test_verify_evidence_exact_match() -> None:
    contexts = ["The rate limit is 100 requests per minute."]
    assert _verify_evidence("The rate limit is 100 requests per minute.", contexts) is True


def test_verify_evidence_normalized_match() -> None:
    contexts = ["The rate limit is 100 requests per minute."]
    assert _verify_evidence("the RATE limit is 100 REQUESTS per minute", contexts) is True


def test_verify_evidence_not_in_context() -> None:
    contexts = ["The rate limit is 100 requests per minute."]
    assert _verify_evidence("The capital of France is Paris.", contexts) is False


def test_verify_evidence_none() -> None:
    contexts = ["anything"]
    assert _verify_evidence(None, contexts) is False


def test_verify_evidence_empty_string() -> None:
    contexts = ["anything"]
    assert _verify_evidence("", contexts) is False


def test_verify_evidence_with_prefix() -> None:
    contexts = ["The rate limit is 100 requests per minute."]
    assert _verify_evidence("[1] The rate limit is 100 requests per minute.", contexts) is True


def test_verify_evidence_ellipsis_split() -> None:
    """Ellipsis splits into fragments; every fragment must appear."""
    contexts = [
        "The rate limit is 100 requests per minute. Contact support for an increase.",
    ]
    evidence = "The rate limit is 100 requests per minute... Contact support for an increase."
    assert _verify_evidence(evidence, contexts) is True


def test_verify_evidence_ellipsis_one_fragment_missing() -> None:
    """If one fragment is missing, verification fails."""
    contexts = ["The rate limit is 100 requests per minute."]
    evidence = "The rate limit is 100 requests per minute... This part is not in the context."
    assert _verify_evidence(evidence, contexts) is False


def test_verify_evidence_multi_context() -> None:
    """Evidence can come from any context."""
    contexts = ["First context.", "Second context with the fact."]
    assert _verify_evidence("Second context with the fact.", contexts) is True


def test_verify_evidence_empty_contexts() -> None:
    assert _verify_evidence("anything", []) is False


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


def test_extract_json_direct() -> None:
    assert _extract_json('{"key": "value"}') == {"key": "value"}


def test_extract_json_with_whitespace() -> None:
    assert _extract_json('  \n  {"key": "value"}  \n  ') == {"key": "value"}


def test_extract_json_markdown_fence() -> None:
    text = 'Here is the result:\n```json\n{"key": "value"}\n```'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_markdown_fence_no_lang() -> None:
    text = '```\n{"key": "value"}\n```'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_with_thought_block() -> None:
    text = '<thought>Let me think...</thought>{"key": "value"}'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_with_surrounding_text() -> None:
    text = 'Sure, here is the answer: {"key": "value"} hope that helps!'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_invalid_returns_none() -> None:
    assert _extract_json("not json at all") is None


def test_extract_json_empty_returns_none() -> None:
    assert _extract_json("") is None


def test_extract_json_none_like_returns_none() -> None:
    """Empty string is treated as no JSON."""
    assert _extract_json("") is None


def test_extract_json_json_array_returns_none() -> None:
    """Arrays are not accepted (only objects)."""
    assert _extract_json("[1, 2, 3]") is None


def test_extract_json_nested() -> None:
    text = '{"outer": {"inner": "value"}}'
    assert _extract_json(text) == {"outer": {"inner": "value"}}
