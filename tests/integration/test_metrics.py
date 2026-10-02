"""Integration tests for simple metrics."""

from assay.core.metrics.simple import context_recall, groundedness


def test_groundedness_perfect_match() -> None:
    """Groundedness is 1.0 when answer is fully in context."""
    answer = "reset password settings"
    contexts = ["reset password settings"]
    assert groundedness(answer, contexts) == 1.0


def test_groundedness_no_match() -> None:
    """Groundedness is 0.0 when answer shares no tokens with context."""
    answer = "completely different words here"
    contexts = ["reset password settings"]
    assert groundedness(answer, contexts) == 0.0


def test_groundedness_partial_match() -> None:
    """Groundedness is between 0 and 1 for partial overlap."""
    answer = "reset password settings extra words"
    contexts = ["reset password settings"]
    g = groundedness(answer, contexts)
    assert 0.0 < g < 1.0


def test_groundedness_empty_inputs() -> None:
    """Groundedness is 0.0 for empty inputs."""
    assert groundedness("", ["context"]) == 0.0
    assert groundedness("answer", []) == 0.0


def test_context_recall_none_expected() -> None:
    """Context recall returns None when no expected context."""
    assert context_recall(None, ["context"]) is None


def test_context_recall_perfect() -> None:
    """Context recall is 1.0 when expected is fully retrieved."""
    expected = "reset password"
    retrieved = ["reset password instructions"]
    assert context_recall(expected, retrieved) == 1.0
