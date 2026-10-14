"""Refusal correctness metric.

Measures whether the RAG system refuses when it should refuse, and
answers when it should answer.

The notion of "should" comes from the dataset: a question with an
expected_answer is answerable; a question without is not.

Detection of refusal is deterministic: a small set of patterns that
commonly appear in "I don't know" style responses.

The output is a per-question status plus an aggregate score.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum


class RefusalStatus(StrEnum):
    """Per-question outcome of refusal correctness."""

    ANSWERABLE_ANSWERED = "answerable_answered"  # correct
    ANSWERABLE_REFUSED = "answerable_refused"  # incorrect
    UNANSWERABLE_REFUSED = "unanswerable_refused"  # correct
    UNANSWERABLE_ANSWERED = "unanswerable_answered"  # incorrect
    NOT_APPLICABLE = "not_applicable"  # no answer produced


@dataclass
class RefusalResult:
    """Result of refusal correctness for one question."""

    status: RefusalStatus
    correct: bool | None  # None if not applicable
    is_refusal: bool
    is_answerable: bool
    reason: str = ""


@dataclass
class RefusalSummary:
    """Aggregate summary across a run."""

    total: int = 0
    applicable: int = 0
    correct: int = 0
    answerable_answered: int = 0
    answerable_refused: int = 0
    unanswerable_refused: int = 0
    unanswerable_answered: int = 0
    not_applicable: int = 0
    score: float | None = None
    reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Refusal detection
# ---------------------------------------------------------------------------


# Patterns are matched case-insensitively against a normalized form of
# the answer. The patterns are deliberately conservative: a short
# answer that matches is treated as a refusal; a longer answer that
# contains a refusal phrase plus facts is not treated as a refusal
# (the facts matter).
_REFUSAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(saya\s+)?tidak\s+(tahu|mengetahui)\b", re.IGNORECASE),
    re.compile(r"^\s*informasi\s+(tersebut\s+)?tidak\s+(tersedia|ditemukan|ada)", re.IGNORECASE),
    re.compile(r"^\s*tidak\s+(dapat|bisa)\s+(ditemukan|ditentukan|diidentifikasi)", re.IGNORECASE),
    re.compile(r"^\s*tidak\s+ada\s+(informasi|cukup informasi|data)", re.IGNORECASE),
    re.compile(r"^\s*i\s+(do\s+not|don'?t)\s+know", re.IGNORECASE),
    re.compile(r"^\s*(not\s+enough|insufficient)\s+information", re.IGNORECASE),
    re.compile(r"^\s*cannot\s+be\s+(determined|answered)", re.IGNORECASE),
    re.compile(r"^\s*tidak\s+terdapat\s+(informasi|cukup)", re.IGNORECASE),
    re.compile(r"^\s*maaf,?\s+(saya\s+)?tidak\s+(tahu|memiliki)", re.IGNORECASE),
]


# Maximum length of an answer that still counts as a refusal. Longer
# answers that merely start with a refusal phrase are treated as
# answers with a disclaimer, not as refusals.
_REFUSAL_MAX_CHARS = 200


# Conjunctions that indicate a continuation after a disclaimer. If a
# refusal phrase is followed by one of these, the answer is not a
# refusal: it is an answer with a hedge.
_CONTRAST_CONJUNCTIONS = re.compile(
    r"\b(namun|tetapi|tapi|akan\s+tetapi|however|but)\b",
    re.IGNORECASE,
)


def is_refusal(answer: str | None) -> bool:
    """Return True if the answer is a refusal.

    A refusal is a short answer that matches one of the refusal
    patterns and does not contain a contrast conjunction. A long
    answer that merely starts with a refusal phrase is not treated
    as a refusal.
    """
    if not answer:
        return False
    text = answer.strip()
    if not text:
        return False
    if len(text) > _REFUSAL_MAX_CHARS:
        return False
    if _CONTRAST_CONJUNCTIONS.search(text):
        return False
    return any(p.match(text) for p in _REFUSAL_PATTERNS)


def is_answerable(expected_answer: str | None, expected_context: str | None = None) -> bool:
    """Determine whether a question is answerable from the dataset.

    If the dataset provides an expected_answer, the question is
    answerable. Otherwise, if it provides an expected_context, the
    question is answerable only if the context is non-empty.
    Otherwise, it is treated as unanswerable.
    """
    if expected_answer is not None and expected_answer.strip():
        return True
    return bool(expected_context is not None and expected_context.strip())


# ---------------------------------------------------------------------------
# Per-question evaluation
# ---------------------------------------------------------------------------


def evaluate_refusal(
    answer: str | None,
    expected_answer: str | None,
    expected_context: str | None = None,
    error_message: str | None = None,
) -> RefusalResult:
    """Evaluate refusal correctness for a single question.

    Returns a RefusalResult with status and correctness.
    """
    if error_message:
        return RefusalResult(
            status=RefusalStatus.NOT_APPLICABLE,
            correct=None,
            is_refusal=False,
            is_answerable=False,
            reason="Result has an error message.",
        )

    if answer is None:
        return RefusalResult(
            status=RefusalStatus.NOT_APPLICABLE,
            correct=None,
            is_refusal=False,
            is_answerable=False,
            reason="No answer produced.",
        )

    answerable = is_answerable(expected_answer, expected_context)
    refusal = is_refusal(answer)

    if answerable and not refusal:
        return RefusalResult(
            status=RefusalStatus.ANSWERABLE_ANSWERED,
            correct=True,
            is_refusal=False,
            is_answerable=True,
            reason="Answerable question was answered.",
        )
    if answerable and refusal:
        return RefusalResult(
            status=RefusalStatus.ANSWERABLE_REFUSED,
            correct=False,
            is_refusal=True,
            is_answerable=True,
            reason="Answerable question was refused.",
        )
    if not answerable and refusal:
        return RefusalResult(
            status=RefusalStatus.UNANSWERABLE_REFUSED,
            correct=True,
            is_refusal=True,
            is_answerable=False,
            reason="Unanswerable question was refused.",
        )
    # not answerable and not refusal
    return RefusalResult(
        status=RefusalStatus.UNANSWERABLE_ANSWERED,
        correct=False,
        is_refusal=False,
        is_answerable=False,
        reason="Unanswerable question was answered anyway.",
    )


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


def summarize_refusal(results: list[RefusalResult]) -> RefusalSummary:
    """Aggregate a list of RefusalResult into a summary."""
    summary = RefusalSummary(total=len(results))
    for r in results:
        if r.status == RefusalStatus.NOT_APPLICABLE:
            summary.not_applicable += 1
            continue
        summary.applicable += 1
        if r.status == RefusalStatus.ANSWERABLE_ANSWERED:
            summary.answerable_answered += 1
            summary.correct += 1
        elif r.status == RefusalStatus.ANSWERABLE_REFUSED:
            summary.answerable_refused += 1
        elif r.status == RefusalStatus.UNANSWERABLE_REFUSED:
            summary.unanswerable_refused += 1
            summary.correct += 1
        elif r.status == RefusalStatus.UNANSWERABLE_ANSWERED:
            summary.unanswerable_answered += 1

    if summary.applicable > 0:
        summary.score = summary.correct / summary.applicable
    else:
        summary.score = None

    if summary.answerable_refused > 0:
        summary.reasons.append(
            f"{summary.answerable_refused} answerable questions were refused."
        )
    if summary.unanswerable_answered > 0:
        summary.reasons.append(
            f"{summary.unanswerable_answered} unanswerable questions were answered."
        )

    return summary
