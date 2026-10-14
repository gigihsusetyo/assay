"""Unit tests for simple metrics internals and edge cases.

Note: happy paths are covered in tests/integration/test_metrics.py.
This file focuses on internals (_normalize, _tokenize) and edge cases.
"""

from assay.core.metrics.simple import (
    _normalize,
    _tokenize,
    context_recall,
    groundedness,
)

# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


def test_normalize_lowercases() -> None:
    assert _normalize("HELLO World") == "hello world"


def test_normalize_removes_punctuation() -> None:
    assert _normalize("Hello, world!") == "hello world"


def test_normalize_collapses_whitespace() -> None:
    assert _normalize("hello    world\n\nfoo") == "hello world foo"


def test_normalize_strips_edges() -> None:
    assert _normalize("   hello   ") == "hello"


def test_normalize_empty() -> None:
    assert _normalize("") == ""


def test_normalize_keeps_underscore() -> None:
    # \w includes underscore
    assert _normalize("hello_world") == "hello_world"


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


def test_tokenize_filters_short_tokens() -> None:
    # "a", "is", "to" <= 2 chars, filtered out
    tokens = _tokenize("a is to be or not")
    assert "not" in tokens
    assert "a" not in tokens
    assert "is" not in tokens
    assert "to" not in tokens


def test_tokenize_returns_set() -> None:
    tokens = _tokenize("hello hello world")
    assert tokens == {"hello", "world"}


def test_tokenize_empty_returns_empty_set() -> None:
    assert _tokenize("") == set()


def test_tokenize_only_short_tokens() -> None:
    assert _tokenize("a b c d") == set()


# ---------------------------------------------------------------------------
# groundedness — edge cases
# ---------------------------------------------------------------------------


def test_groundedness_case_insensitive() -> None:
    assert groundedness("RESET PASSWORD", ["reset password"]) == 1.0


def test_groundedness_punctuation_ignored() -> None:
    assert groundedness("reset, password!", ["reset password"]) == 1.0


def test_groundedness_short_tokens_ignored() -> None:
    """Tokens <= 2 chars are ignored. 'a' and 'is' don't affect score."""
    answer = "reset is a password"
    contexts = ["reset password"]
    # answer tokens: {reset, password} (is, a filtered)
    # context tokens: {reset, password}
    assert groundedness(answer, contexts) == 1.0


def test_groundedness_answer_only_short_tokens() -> None:
    """If answer has no valid tokens after filtering, score is 0.0."""
    assert groundedness("a is to", ["reset password"]) == 0.0


def test_groundedness_context_only_short_tokens() -> None:
    """If context has no valid tokens, score is 0.0."""
    assert groundedness("reset password", ["a is to"]) == 0.0


def test_groundedness_duplicate_answer_tokens() -> None:
    """Set semantics: duplicates collapse."""
    # answer tokens after set: {reset, password}
    # context: {reset, password}
    assert groundedness("reset reset password password", ["reset password"]) == 1.0


def test_groundedness_multiple_contexts_union() -> None:
    answer = "reset password account"
    contexts = ["reset password", "account settings"]
    # answer: {reset, password, account}
    # union: {reset, password, account, settings}
    # overlap: 3/3
    assert groundedness(answer, contexts) == 1.0


def test_groundedness_partial() -> None:
    answer = "reset password missing token"
    contexts = ["reset password"]
    # answer: {reset, password, missing, token}
    # overlap: 2/4 = 0.5
    assert groundedness(answer, contexts) == 0.5


def test_groundedness_empty_answer() -> None:
    assert groundedness("", ["context"]) == 0.0


def test_groundedness_empty_contexts() -> None:
    assert groundedness("answer", []) == 0.0


# ---------------------------------------------------------------------------
# context_recall — edge cases
# ---------------------------------------------------------------------------


def test_context_recall_none_expected_returns_none() -> None:
    assert context_recall(None, ["any"]) is None


def test_context_recall_empty_expected_returns_none() -> None:
    assert context_recall("", ["any"]) is None


def test_context_recall_no_retrieved_returns_zero() -> None:
    assert context_recall("reset password", []) == 0.0


def test_context_recall_perfect_match() -> None:
    assert context_recall("reset password", ["reset password settings"]) == 1.0


def test_context_recall_partial() -> None:
    expected = "reset password settings"
    retrieved = ["reset password"]
    # expected: {reset, password, settings}
    # retrieved: {reset, password}
    # overlap: 2/3
    assert context_recall(expected, retrieved) == 2 / 3


def test_context_recall_case_insensitive() -> None:
    assert context_recall("RESET PASSWORD", ["reset password"]) == 1.0


def test_context_recall_multiple_retrieved_contexts() -> None:
    expected = "reset password settings"
    retrieved = ["reset password", "settings page"]
    assert context_recall(expected, retrieved) == 1.0


def test_context_recall_expected_only_short_tokens_returns_none() -> None:
    """If expected has no valid tokens, return None."""
    assert context_recall("a is to", ["reset password"]) is None


def test_context_recall_retrieved_only_short_tokens_returns_zero() -> None:
    assert context_recall("reset password", ["a is to"]) == 0.0
