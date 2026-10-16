"""Integration tests for answer relevance.

These tests only run when the judge is configured. They are skipped
otherwise so that the test suite passes in CI without API keys.
"""

import pytest

from assay.config import settings
from assay.core.metrics.judge import (
    JudgeError,
    judge_answer_relevance,
)

requires_judge = pytest.mark.skipif(
    not settings.judge_enabled,
    reason="Judge is not configured (set ASSAY_JUDGE_* env vars).",
)


@requires_judge
def test_relevant_answer() -> None:
    """A direct answer to the question is relevant and complete."""
    result = judge_answer_relevance(
        question="What is the capital of France?",
        answer="Paris is the capital of France.",
    )
    assert result.relevant is True
    assert result.completeness_score == 1.0
    assert result.score == 1.0
    assert len(result.aspects) >= 1


@requires_judge
def test_irrelevant_answer() -> None:
    """An answer about a different topic is not relevant."""
    result = judge_answer_relevance(
        question="How do I reset my password?",
        answer="The rate limit is 100 requests per minute.",
    )
    assert result.relevant is False
    # Irrelevant -> completeness is 0.0 by definition.
    assert result.completeness_score == 0.0
    assert result.score == 0.0


@requires_judge
def test_multi_aspect_partial() -> None:
    """A multi-aspect question answered partially is relevant but incomplete.

    Relevance and completeness are separate dimensions:
    - The answer addresses the topic (rate limit) -> relevant = True.
    - The answer omits one aspect (how to increase it) -> completeness < 1.0.
    """
    result = judge_answer_relevance(
        question="What is the rate limit and how do I increase it?",
        answer="The rate limit is 100 requests per minute.",
    )
    assert result.relevant is True
    assert 0.0 < result.completeness_score < 1.0
    assert len(result.aspects) >= 2


def test_empty_question_or_answer() -> None:
    """Empty inputs return a non-relevant result without calling the judge."""
    result = judge_answer_relevance(question="", answer="Something")
    assert result.relevant is False
    assert result.completeness_score == 0.0
    assert result.score == 0.0

    result = judge_answer_relevance(question="Something?", answer="")
    assert result.relevant is False
    assert result.completeness_score == 0.0
    assert result.score == 0.0


def test_judge_not_configured_raises() -> None:
    """When the judge is not configured, a JudgeError is raised."""
    if settings.judge_enabled:
        pytest.skip("Judge is configured; cannot test the not-configured path.")
    with pytest.raises(JudgeError):
        judge_answer_relevance(
            question="What is the capital of France?",
            answer="Paris.",
        )
