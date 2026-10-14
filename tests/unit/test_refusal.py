"""Unit tests for refusal correctness."""

from assay.core.metrics.refusal import (
    RefusalStatus,
    evaluate_refusal,
    is_answerable,
    is_refusal,
    summarize_refusal,
)

# ---------------------------------------------------------------------------
# is_refusal
# ---------------------------------------------------------------------------


def test_refusal_indonesian_basic() -> None:
    assert is_refusal("Saya tidak tahu.") is True


def test_refusal_indonesian_tanpa_saya() -> None:
    assert is_refusal("Tidak tahu.") is True


def test_refusal_informasi_tidak_tersedia() -> None:
    assert is_refusal("Informasi tidak tersedia.") is True


def test_refusal_tidak_dapat_ditemukan() -> None:
    assert is_refusal("Tidak dapat ditemukan dalam konteks.") is True


def test_refusal_english_i_dont_know() -> None:
    assert is_refusal("I don't know.") is True


def test_refusal_english_not_enough_info() -> None:
    assert is_refusal("Not enough information to answer.") is True


def test_refusal_maaf_saya_tidak_tahu() -> None:
    assert is_refusal("Maaf, saya tidak tahu.") is True


def test_refusal_long_answer_not_refusal() -> None:
    """A long answer that starts with a refusal phrase is not a refusal."""
    long_answer = (
        "Saya tidak tahu secara pasti, namun berdasarkan konteks, "
        "Pasal 5 ayat (2) menyatakan bahwa batas usia adalah 60 tahun. "
        "Selain itu, ada beberapa pengecualian yang perlu diperhatikan."
    )
    assert is_refusal(long_answer) is False


def test_refusal_empty_answer() -> None:
    assert is_refusal("") is False
    assert is_refusal(None) is False


def test_refusal_regular_answer() -> None:
    assert is_refusal("Batas usia adalah 60 tahun.") is False


# ---------------------------------------------------------------------------
# is_answerable
# ---------------------------------------------------------------------------


def test_answerable_with_expected_answer() -> None:
    assert is_answerable("60 tahun") is True


def test_answerable_with_expected_context_only() -> None:
    assert is_answerable(None, "Some context") is True


def test_not_answerable_without_both() -> None:
    assert is_answerable(None, None) is False


def test_not_answerable_with_empty_strings() -> None:
    assert is_answerable("", "") is False


# ---------------------------------------------------------------------------
# evaluate_refusal
# ---------------------------------------------------------------------------


def test_evaluate_answerable_answered() -> None:
    result = evaluate_refusal(
        answer="Batas usia adalah 60 tahun.",
        expected_answer="60 tahun",
    )
    assert result.status == RefusalStatus.ANSWERABLE_ANSWERED
    assert result.correct is True


def test_evaluate_answerable_refused() -> None:
    result = evaluate_refusal(
        answer="Saya tidak tahu.",
        expected_answer="60 tahun",
    )
    assert result.status == RefusalStatus.ANSWERABLE_REFUSED
    assert result.correct is False


def test_evaluate_unanswerable_refused() -> None:
    result = evaluate_refusal(
        answer="Informasi tidak tersedia.",
        expected_answer=None,
    )
    assert result.status == RefusalStatus.UNANSWERABLE_REFUSED
    assert result.correct is True


def test_evaluate_unanswerable_answered() -> None:
    result = evaluate_refusal(
        answer="Batas usia adalah 60 tahun.",
        expected_answer=None,
    )
    assert result.status == RefusalStatus.UNANSWERABLE_ANSWERED
    assert result.correct is False


def test_evaluate_with_error_message() -> None:
    result = evaluate_refusal(
        answer=None,
        expected_answer="60 tahun",
        error_message="Target error",
    )
    assert result.status == RefusalStatus.NOT_APPLICABLE
    assert result.correct is None


def test_evaluate_no_answer_no_error() -> None:
    result = evaluate_refusal(
        answer=None,
        expected_answer="60 tahun",
    )
    assert result.status == RefusalStatus.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# summarize_refusal
# ---------------------------------------------------------------------------


def test_summarize_empty() -> None:
    summary = summarize_refusal([])
    assert summary.total == 0
    assert summary.score is None


def test_summarize_all_correct() -> None:
    results = [
        evaluate_refusal("Jawaban.", "expected"),
        evaluate_refusal("Jawaban.", "expected"),
        evaluate_refusal("Saya tidak tahu.", None),
    ]
    summary = summarize_refusal(results)
    assert summary.total == 3
    assert summary.applicable == 3
    assert summary.correct == 3
    assert summary.score == 1.0


def test_summarize_mixed() -> None:
    results = [
        evaluate_refusal("Jawaban.", "expected"),  # correct
        evaluate_refusal("Saya tidak tahu.", "expected"),  # incorrect
        evaluate_refusal("Saya tidak tahu.", None),  # correct
        evaluate_refusal("Jawaban.", None),  # incorrect
    ]
    summary = summarize_refusal(results)
    assert summary.total == 4
    assert summary.correct == 2
    assert summary.score == 0.5
    assert summary.answerable_answered == 1
    assert summary.answerable_refused == 1
    assert summary.unanswerable_refused == 1
    assert summary.unanswerable_answered == 1
    assert len(summary.reasons) == 2


def test_summarize_with_not_applicable() -> None:
    results = [
        evaluate_refusal("Jawaban.", "expected"),
        evaluate_refusal(None, "expected", error_message="error"),
    ]
    summary = summarize_refusal(results)
    assert summary.total == 2
    assert summary.applicable == 1
    assert summary.not_applicable == 1
    assert summary.score == 1.0
