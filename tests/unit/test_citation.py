"""Unit tests for citation extraction and accuracy (deterministic only)."""

from assay.core.metrics.citation import (
    citation_accuracy,
    extract_citations,
)

# ---------------------------------------------------------------------------
# extract_citations
# ---------------------------------------------------------------------------


def test_extract_pasal_simple() -> None:
    citations = extract_citations("Berdasarkan Pasal 5, ...")
    assert len(citations) == 1
    assert citations[0].kind == "pasal"
    assert citations[0].text == "Pasal 5"


def test_extract_pasal_ayat() -> None:
    citations = extract_citations("Berdasarkan Pasal 5 ayat (2), ...")
    assert len(citations) == 1
    assert citations[0].kind == "pasal_ayat"
    assert "5" in citations[0].text
    assert "2" in citations[0].text


def test_extract_uu_long() -> None:
    citations = extract_citations("Menurut UU Nomor 16 Tahun 2025, ...")
    kinds = [c.kind for c in citations]
    assert "uu" in kinds


def test_extract_uu_short() -> None:
    citations = extract_citations("Menurut UU 16/2025, ...")
    kinds = [c.kind for c in citations]
    assert "uu" in kinds


def test_extract_pp() -> None:
    citations = extract_citations("PP Nomor 35 Tahun 2025 mengatur ...")
    kinds = [c.kind for c in citations]
    assert "pp" in kinds


def test_extract_perpres() -> None:
    citations = extract_citations("Perpres 11/2026 tentang ...")
    kinds = [c.kind for c in citations]
    assert "perpres" in kinds


def test_extract_multiple_citations() -> None:
    text = "Pasal 5 ayat (2) UU 16/2025 dan Pasal 7 PP 35/2025."
    citations = extract_citations(text)
    assert len(citations) >= 2


def test_extract_no_citations() -> None:
    citations = extract_citations("Tidak ada sitasi di sini.")
    assert citations == []


def test_extract_empty_answer() -> None:
    assert extract_citations("") == []


def test_extract_deduplicates() -> None:
    text = "Pasal 5, Pasal 5, Pasal 5."
    citations = extract_citations(text)
    pasal_5 = [c for c in citations if c.kind == "pasal" and c.text == "Pasal 5"]
    assert len(pasal_5) == 1


# ---------------------------------------------------------------------------
# citation_accuracy — existence check
# ---------------------------------------------------------------------------


def test_citation_accuracy_no_citations() -> None:
    result = citation_accuracy("Tidak ada sitasi.", ["context"])
    assert result.score is None
    assert result.total == 0


def test_citation_accuracy_pasal_exists() -> None:
    answer = "Berdasarkan Pasal 5, ..."
    contexts = ["Pasal 5 mengatur tentang ..."]
    result = citation_accuracy(answer, contexts)
    assert result.score == 1.0
    assert result.total >= 1
    assert result.valid >= 1


def test_citation_accuracy_pasal_not_exists() -> None:
    answer = "Berdasarkan Pasal 99, ..."
    contexts = ["Pasal 5 mengatur tentang ..."]
    result = citation_accuracy(answer, contexts)
    assert result.score == 0.0
    assert result.valid == 0


def test_citation_accuracy_pasal_ayat_both_exist() -> None:
    answer = "Berdasarkan Pasal 5 ayat (2), ..."
    contexts = ["Pasal 5 ayat (2): ..."]
    result = citation_accuracy(answer, contexts)
    assert result.score == 1.0


def test_citation_accuracy_pasal_ayat_one_missing() -> None:
    answer = "Berdasarkan Pasal 5 ayat (2), ..."
    contexts = ["Pasal 5 mengatur tentang ..."]
    result = citation_accuracy(answer, contexts)
    pasal_ayat = [c for c in result.citations if c.kind == "pasal_ayat"]
    assert all(not c.exists_in_context for c in pasal_ayat)


def test_citation_accuracy_uu_short_in_context_long() -> None:
    answer = "Menurut UU 16/2025, ..."
    contexts = ["Undang-Undang Nomor 16 Tahun 2025 mengatur ..."]
    result = citation_accuracy(answer, contexts)
    assert result.score == 1.0


def test_citation_accuracy_partial() -> None:
    answer = "Pasal 5 dan Pasal 99 mengatur ..."
    contexts = ["Pasal 5: ..."]
    result = citation_accuracy(answer, contexts)
    assert result.total == 2
    assert result.valid == 1
    assert result.score == 0.5


def test_citation_accuracy_empty_contexts() -> None:
    answer = "Berdasarkan Pasal 5, ..."
    result = citation_accuracy(answer, [])
    assert result.score == 0.0
