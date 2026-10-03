# ADR-003: Simple Metrics for MVP

**Status:** Accepted
**Date:** 2 October 2026

## Context

Assay needs to measure RAG quality. The obvious choice is LLM-as-judge: use an LLM to evaluate whether the answer is grounded in the retrieved contexts.

But LLM-as-judge has problems. It costs money. It is slow. It is non-deterministic. And the judge itself needs validation: how do we know the judge is reliable?

For the MVP, I need something fast, deterministic, and free. Something that catches obvious regressions without requiring an LLM call.

## Decision

For the MVP, Assay uses simple heuristic metrics.

**Groundedness:** fraction of answer tokens that appear in the retrieved contexts. Range 0.0 to 1.0.

**Context recall:** fraction of expected context tokens that appear in retrieved contexts. Returns None if no expected context is provided.

These are token-overlap heuristics. They are not LLM-as-judge. They are fast, deterministic, and good enough to catch obvious regressions.

## Important: Regression Signals, Not Correctness Guarantees

These metrics are regression signals. They are not correctness guarantees.

Token overlap catches obvious drift. It does not catch semantic errors. An answer that says "rate limit is 1000" when the context says "rate limit is 100" will score high on groundedness, because most tokens overlap. That is a real limitation.

The purpose of these metrics is to detect whether a change made the system worse, not to certify that the system is good. For semantic correctness, use LLM-as-judge (see ADR-004).

## Consequences

What I gain:

- No LLM cost per evaluation.
- Deterministic results. Same input, same output.
- Fast. No network calls.
- Tests are simple.

What I sacrifice:

- The metrics are shallow. They catch token-level mismatch, not semantic mismatch.
- An answer that is semantically correct but uses different words will score low.
- An answer that copies tokens from context but is semantically wrong will score high.
- The metrics do not measure "does the answer actually answer the question".

Plan:

- Add LLM-as-judge metrics in a later phase.
- Validate the judge against human labels. Report agreement.
- Keep the simple metrics as a fast pre-check. LLM-as-judge runs only when needed.
- Make metrics pluggable so teams can add their own.

---

# ADR-003: Metrics Sederhana untuk MVP

**Status:** Diterima
**Tanggal:** 2 Oktober 2026

## Konteks

Assay perlu mengukur kualitas RAG. Pilihan yang jelas adalah LLM-as-judge: pakai LLM untuk evaluasi apakah jawaban didukung konteks yang di-retrieve.

Tapi LLM-as-judge ada masalahnya. Biaya. Lambat. Non-deterministic. Dan judge-nya sendiri butuh validasi: bagaimana kita tahu judge-nya reliable?

Untuk MVP, saya butuh sesuatu yang cepat, deterministic, dan gratis. Sesuatu yang bisa tangkap regresi jelas tanpa perlu panggil LLM.

## Keputusan

Untuk MVP, Assay pakai metrics heuristic sederhana.

**Groundedness:** fraksi token jawaban yang muncul di konteks yang di-retrieve. Range 0.0 sampai 1.0.

**Context recall:** fraksi token expected context yang muncul di retrieved contexts. Return None kalau tidak ada expected context.

Ini heuristic token-overlap. Bukan LLM-as-judge. Cepat, deterministic, dan cukup untuk tangkap regresi jelas.

## Penting: Sinyal Regresi, Bukan Jaminan Kebenaran

Metrics ini adalah sinyal regresi. Bukan jaminan kebenaran.

Token overlap menangkap drift yang jelas. Tidak menangkap kesalahan semantic. Jawaban yang bilang "rate limit 1000" padahal konteks bilang "rate limit 100" akan skor tinggi di groundedness, karena sebagian besar token overlap. Ini keterbatasan nyata.

Tujuan metrics ini adalah mendeteksi apakah perubahan membuat sistem lebih buruk, bukan mensertifikasi bahwa sistem bagus. Untuk kebenaran semantic, pakai LLM-as-judge (lihat ADR-004).

## Konsekuensi

Yang saya dapat:

- Tidak ada biaya LLM per evaluasi.
- Hasil deterministic. Input sama, output sama.
- Cepat. Tidak ada network call.
- Tests sederhana.

Yang saya korbankan:

- Metrics-nya dangkal. Tangkap mismatch token, bukan mismatch semantic.
- Jawaban yang benar secara semantic tapi pakai kata berbeda akan skor rendah.
- Jawaban yang copy token dari konteks tapi salah secara semantic akan skor tinggi.
- Metrics tidak mengukur "apakah jawaban benar-benar menjawab pertanyaan".

Rencana:

- Tambah LLM-as-judge metrics di fase berikutnya.
- Validasi judge terhadap human labels. Laporkan agreement.
- Simpan simple metrics sebagai pre-check cepat. LLM-as-judge jalan hanya saat perlu.
- Buat metrics pluggable supaya tim bisa tambah sendiri.