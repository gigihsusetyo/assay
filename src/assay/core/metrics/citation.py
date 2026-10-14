"""Citation accuracy metric.

Extracts legal citations from an answer, checks whether each citation
exists in the retrieved contexts, and (optionally) checks whether the
citation supports the claim it is attached to.

Two layers:
- Deterministic extraction and existence check.
- LLM-as-judge for relevance.

The deterministic layer is fast, free, and auditable. The LLM layer
is optional and off by default.
"""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Citation:
    """A single citation extracted from an answer."""

    text: str
    kind: str  # "pasal", "ayat", "uu", "pp", "perpres", "permen", "other"
    canonical: str  # normalized form for comparison
    exists_in_context: bool = False
    supports_claim: bool | None = None  # None if LLM judge not run
    reason: str = ""


@dataclass
class CitationResult:
    """Result of citation accuracy evaluation."""

    score: float | None  # None if no citations found
    citations: list[Citation] = field(default_factory=list)
    total: int = 0
    valid: int = 0
    reason: str = ""


# ---------------------------------------------------------------------------
# Extraction patterns
# ---------------------------------------------------------------------------


# Order matters: more specific patterns first.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # "Pasal 5 ayat (2)" or "Pasal 5 Ayat 2"
    (
        "pasal_ayat",
        re.compile(
            r"Pasal\s+(\d+)\s+ayat\s+\(?(\d+)\)?",
            re.IGNORECASE,
        ),
    ),
    # "Pasal 5"
    ("pasal", re.compile(r"Pasal\s+(\d+)", re.IGNORECASE)),
    # "ayat (2)"
    ("ayat", re.compile(r"ayat\s+\(?(\d+)\)?", re.IGNORECASE)),
    # "UU Nomor 16 Tahun 2025" or "UU 16/2025" or "UU No. 16/2025"
    (
        "uu",
        re.compile(
            r"(?:UU|Undang-Undang)\s+(?:Nomor|No\.?)?\s*(\d+)\s*(?:Tahun|/)\s*(\d{4})",
            re.IGNORECASE,
        ),
    ),
    # "PP Nomor 35 Tahun 2025" or "PP 35/2025"
    (
        "pp",
        re.compile(
            r"PP\s+(?:Nomor|No\.?)?\s*(\d+)\s*(?:Tahun|/)\s*(\d{4})",
            re.IGNORECASE,
        ),
    ),
    # "Perpres Nomor 11 Tahun 2026" or "Perpres 11/2026"
    (
        "perpres",
        re.compile(
            r"Perpres\s+(?:Nomor|No\.?)?\s*(\d+)\s*(?:Tahun|/)\s*(\d{4})",
            re.IGNORECASE,
        ),
    ),
    # "Permenkes Nomor 3 Tahun 2024" or "Permenkes 3/2024"
    (
        "permen",
        re.compile(
            r"(?:Permen\w*|Peraturan\s+Menteri\s+\w+)\s+(?:Nomor|No\.?)?\s*(\d+)\s*(?:Tahun|/)\s*(\d{4})",
            re.IGNORECASE,
        ),
    ),
]


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_citations(answer: str) -> list[Citation]:
    """Extract legal citations from an answer.

    Patterns are applied from most specific to least specific. If a
    more specific pattern matches a span, less specific patterns are
    skipped for that span. This prevents "Pasal 5 ayat (2)" from also
    being extracted as "Pasal 5" and "ayat (2)".

    Returns citations in order of appearance. Duplicates are removed.
    """
    if not answer:
        return []

    # Track character spans already covered by more specific patterns.
    covered_spans: list[tuple[int, int]] = []
    found: dict[str, Citation] = {}

    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(answer):
            start, end = match.start(), match.end()

            # Skip if this span overlaps with a covered span.
            if any(not (end <= s or start >= e) for s, e in covered_spans):
                continue

            text = match.group(0)
            canonical = _normalize(text)
            key = f"{kind}:{canonical}"
            if key in found:
                continue

            found[key] = Citation(
                text=text,
                kind=kind,
                canonical=canonical,
            )
            covered_spans.append((start, end))

    # Sort by position of first appearance in answer.
    result = list(found.values())
    result.sort(key=lambda c: answer.find(c.text))
    return result


# ---------------------------------------------------------------------------
# Existence check
# ---------------------------------------------------------------------------


def _check_existence(citation: Citation, contexts: list[str]) -> bool:
    """Check whether the citation appears in any context.

    Normalizes both sides. For "pasal_ayat" citations, both the pasal
    and the ayat must appear in the same context.
    """
    if not contexts:
        return False

    normalized_contexts = [_normalize(c) for c in contexts]
    target = citation.canonical

    if citation.kind == "pasal_ayat":
        # Extract pasal and ayat numbers from canonical form.
        m = re.match(r"pasal\s+(\d+)\s+ayat\s+\(?(\d+)\)?", target)
        if not m:
            return False
        pasal_num = m.group(1)
        ayat_num = m.group(2)
        pasal_pattern = re.compile(rf"pasal\s+{pasal_num}\b")
        ayat_pattern = re.compile(rf"ayat\s+\(?{ayat_num}\)?\b")
        return any(
            pasal_pattern.search(ctx) and ayat_pattern.search(ctx)
            for ctx in normalized_contexts
        )

    if citation.kind == "pasal":
        m = re.match(r"pasal\s+(\d+)", target)
        if not m:
            return False
        pasal_num = m.group(1)
        pattern = re.compile(rf"pasal\s+{pasal_num}\b")
        return any(pattern.search(ctx) for ctx in normalized_contexts)

    if citation.kind == "ayat":
        m = re.match(r"ayat\s+\(?(\d+)\)?", target)
        if not m:
            return False
        ayat_num = m.group(1)
        pattern = re.compile(rf"ayat\s+\(?{ayat_num}\)?\b")
        return any(pattern.search(ctx) for ctx in normalized_contexts)

    # For uu/pp/perpres/permen, check the full canonical string.
    # The context may have "Nomor 16 Tahun 2025" while answer has "16/2025".
    # Normalize both to "16 2025" and check for both numbers together.
    numbers = re.findall(r"\d+", target)
    if len(numbers) >= 2:
        num1, num2 = numbers[0], numbers[1]
        pattern = re.compile(rf"\b{num1}\b[^\d]{{0,40}}\b{num2}\b")
        return any(pattern.search(ctx) for ctx in normalized_contexts)

    return any(target in ctx for ctx in normalized_contexts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def citation_accuracy(
    answer: str,
    contexts: list[str],
) -> CitationResult:
    """Compute citation accuracy for an answer.

    Deterministic only. For LLM-based relevance check, use
    judge_citation_relevance from judge.py.

    Returns CitationResult with score = valid / total.
    Score is None if no citations were found.
    """
    citations = extract_citations(answer)
    if not citations:
        return CitationResult(
            score=None,
            citations=[],
            total=0,
            valid=0,
            reason="No citations found in answer.",
        )

    for c in citations:
        c.exists_in_context = _check_existence(c, contexts)
        if c.exists_in_context:
            c.reason = "Citation found in context."
        else:
            c.reason = "Citation not found in context."

    total = len(citations)
    valid = sum(1 for c in citations if c.exists_in_context)
    score = valid / total if total > 0 else None

    return CitationResult(
        score=score,
        citations=citations,
        total=total,
        valid=valid,
        reason=f"{valid}/{total} citations found in context.",
    )
