"""Simple metrics for MVP.

These are heuristic metrics, not LLM-as-judge. They are fast, deterministic,
and good enough for the MVP. LLM-as-judge will come later.
"""

import re


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str) -> set[str]:
    """Tokenize into a set of words, ignoring very short tokens."""
    normalized = _normalize(text)
    return {t for t in normalized.split() if len(t) > 2}


def groundedness(answer: str, contexts: list[str]) -> float:
    """Measure how much of the answer is supported by the contexts.

    Heuristic: fraction of answer tokens that appear in the contexts.
    Range 0.0 to 1.0.
    """
    if not answer or not contexts:
        return 0.0

    answer_tokens = _tokenize(answer)
    if not answer_tokens:
        return 0.0

    context_tokens: set[str] = set()
    for ctx in contexts:
        context_tokens |= _tokenize(ctx)

    if not context_tokens:
        return 0.0

    overlap = answer_tokens & context_tokens
    return len(overlap) / len(answer_tokens)


def context_recall(expected_context: str | None, retrieved_contexts: list[str]) -> float | None:
    """Measure how much of the expected context was retrieved.

    Heuristic: fraction of expected context tokens that appear in retrieved contexts.
    Returns None if no expected context is provided.
    """
    if not expected_context:
        return None
    if not retrieved_contexts:
        return 0.0

    expected_tokens = _tokenize(expected_context)
    if not expected_tokens:
        return None

    retrieved_tokens: set[str] = set()
    for ctx in retrieved_contexts:
        retrieved_tokens |= _tokenize(ctx)

    if not retrieved_tokens:
        return 0.0

    overlap = expected_tokens & retrieved_tokens
    return len(overlap) / len(expected_tokens)
