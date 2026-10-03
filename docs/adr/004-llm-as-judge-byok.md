# ADR-004: LLM-as-Judge with Bring Your Own Key

**Status:** Accepted
**Date:** 4 October 2026

## Context

Assay measures RAG quality. The initial MVP used simple heuristic metrics: token overlap between answer and context. These are fast, deterministic, and free. But they are shallow. An answer that is semantically correct but uses different words scores low. An answer that copies tokens but is semantically wrong scores high.

To measure quality properly, we need LLM-as-judge. An LLM reads the question, the answer, and the contexts, then decides whether the answer is grounded.

But LLM-as-judge has problems. It costs money. It is non-deterministic. And the judge itself needs validation.

The question is: who provides the LLM?

Options considered:

1. **Assay provides the LLM.** Assay picks a model, sets the API key, and pays the bill. Simple for users, but not sustainable for an open source project.

2. **User provides the LLM (BYOK).** User sets their own API key, picks their own model. Assay is a framework, not a provider.

3. **Hybrid.** Assay provides a free default, user can override. More complex, but user-friendly.

## Decision

We chose BYOK (Bring Your Own Key).

Users set these environment variables:

```
ASSAY_JUDGE_PROVIDER=openrouter
ASSAY_JUDGE_MODEL=openrouter/free
ASSAY_JUDGE_API_KEY=sk-or-...
ASSAY_JUDGE_BASE_URL=https://openrouter.ai/api/v1
```

If these are not set, the judge is disabled. Assay falls back to simple heuristic metrics. The user can still use Assay, just without LLM-based evaluation.

We use the OpenAI-compatible API. This means the same code works with OpenRouter, OpenAI, Anthropic (via proxy), Ollama, and any other provider that follows the same format.

We do not provide a default LLM. No free tier from Assay. No API key from Assay.

## Consequences

What we gain:

- Assay does not pay for LLM calls.
- Users are free to choose any model. Some teams need local models (Ollama) for data privacy. Some need GPT-4 for accuracy. Some need cheap models for volume.
- The code is provider-agnostic. The same judge module works with any OpenAI-compatible API.
- This matches industry standards. RAGAS, DeepEval, and TruLens all use BYOK.

What we sacrifice:

- Users must set up their own API key. This is friction. But our target users are engineers, and they understand this.
- Judge quality depends on the model the user picks. A weak model gives weak judgments. This is why we need judge validation (see below).
- No "out of the box" experience. Users cannot just clone and run. They need an API key.

## Judge Validation

Because judge quality varies by model, we need to measure it. This is what makes Assay different from other tools.

We will:

1. Build a calibration set: 50 questions with human-labeled groundedness.
2. Run the judge on the calibration set.
3. Compute agreement with human labels using Cohen's kappa.
4. Probe for bias: position bias, verbosity bias, self-preference bias.
5. Report the results in the docs.

If the judge is not reliable, the user should not trust the groundedness scores. Better to know than to guess.

## Fallback Behavior

The judge can fail for several reasons:

- Rate limit (429).
- Server error (500).
- Invalid JSON output.

When the judge fails, Assay falls back to simple heuristic metrics. The CLI reports how many questions were judged by the LLM and how many fell back.

This means the pipeline never breaks. But the user should know that some scores came from heuristics, not from the judge.

## Retry Logic

We retry on rate limit and server errors. Up to 3 attempts, with exponential backoff (1s, 2s, 4s). This is standard practice.

## JSON Parsing

Not all models return clean JSON, even when asked. We have a tolerant parser:

1. Try direct JSON parse.
2. Try to extract JSON from markdown fences.
3. Try to find the first { ... } block.
4. Last resort: parse text for grounded/unsafe signals.

This is not perfect. But it handles most cases. If the parser fails completely, the judge falls back to simple metrics.

---

# ADR-004: LLM-as-Judge dengan Bring Your Own Key

**Status:** Diterima
**Tanggal:** 4 Oktober 2026

## Konteks

Assay mengukur kualitas RAG. MVP awal pakai metrics heuristic sederhana: token overlap antara jawaban dan konteks. Cepat, deterministic, gratis. Tapi dangkal. Jawaban yang benar secara semantic tapi pakai kata berbeda akan skor rendah. Jawaban yang copy token tapi salah secara semantic akan skor tinggi.

Untuk mengukur kualitas dengan benar, kita butuh LLM-as-judge. LLM baca pertanyaan, jawaban, dan konteks, lalu putuskan apakah jawaban didukung konteks.

Tapi LLM-as-judge ada masalah. Biaya. Non-deterministic. Dan judge-nya sendiri butuh validasi.

Pertanyaannya: siapa yang menyediakan LLM?

Opsi yang dipertimbangkan:

1. **Assay yang sediakan LLM.** Assay pilih model, set API key, bayar tagihan. Simpel untuk user, tapi tidak sustainable untuk open source.

2. **User yang sediakan LLM (BYOK).** User set API key sendiri, pilih model sendiri. Assay cuma framework, bukan provider.

3. **Hybrid.** Assay sediakan default gratis, user bisa override. Lebih kompleks, tapi user-friendly.

## Keputusan

Kami pilih BYOK (Bring Your Own Key).

User set environment variable ini:

```
ASSAY_JUDGE_PROVIDER=openrouter
ASSAY_JUDGE_MODEL=openrouter/free
ASSAY_JUDGE_API_KEY=sk-or-...
ASSAY_JUDGE_BASE_URL=https://openrouter.ai/api/v1
```

Kalau tidak di-set, judge tidak aktif. Assay fallback ke simple heuristic metrics. User tetap bisa pakai Assay, cuma tanpa LLM-based evaluation.

Kami pakai OpenAI-compatible API. Artinya kode yang sama bekerja dengan OpenRouter, OpenAI, Anthropic (via proxy), Ollama, dan provider apa pun yang ikut format yang sama.

Kami tidak sediakan default LLM. Tidak ada free tier dari Assay. Tidak ada API key dari Assay.

## Konsekuensi

Yang kami dapat:

- Assay tidak bayar LLM call.
- User bebas pilih model. Tim compliance mungkin butuh model lokal (Ollama) untuk privasi data. Tim lain butuh GPT-4 untuk akurasi. Tim lain butuh model murah untuk volume.
- Kode provider-agnostic. Modul judge yang sama bekerja dengan API OpenAI-compatible apa pun.
- Ini sesuai standar industri. RAGAS, DeepEval, TruLens semua pakai BYOK.

Yang kami korbankan:

- User harus setup API key sendiri. Ini friksi. Tapi target user kami adalah engineer, dan mereka paham ini.
- Kualitas judge bergantung pada model yang user pilih. Model lemah kasih judgment lemah. Ini kenapa kita butuh judge validation.
- Tidak ada pengalaman "out of the box". User tidak bisa langsung clone dan jalan. Mereka butuh API key.

## Validasi Judge

Karena kualitas judge bervariasi, kami perlu mengukurnya. Ini yang membedakan Assay dari tools lain.

Kami akan:

1. Bangun calibration set: 50 pertanyaan dengan label groundedness dari manusia.
2. Jalankan judge pada calibration set.
3. Hitung agreement dengan human labels pakai Cohen's kappa.
4. Probe bias: position bias, verbosity bias, self-preference bias.
5. Laporkan hasilnya di dokumentasi.

Kalau judge tidak reliable, user tidak boleh percaya skor groundedness-nya. Lebih baik tahu daripada menebak.

## Fallback Behavior

Judge bisa gagal karena beberapa alasan:

- Rate limit (429).
- Server error (500).
- Output JSON tidak valid.

Kalau judge gagal, Assay fallback ke simple heuristic metrics. CLI melaporkan berapa pertanyaan yang di-judge LLM dan berapa yang fallback.

Artinya pipeline tidak pernah putus. Tapi user harus tahu bahwa beberapa skor berasal dari heuristic, bukan dari judge.

## Retry Logic

Kami retry pada rate limit dan server error. Sampai 3 kali, dengan exponential backoff (1s, 2s, 4s). Ini praktik standar.

## JSON Parsing

Tidak semua model return JSON bersih, meskipun diminta. Kami punya parser toleran:

1. Coba parse JSON langsung.
2. Coba ekstrak JSON dari markdown fence.
3. Coba cari blok { ... } pertama.
4. Last resort: parse text untuk signal grounded/unsafe.

Ini tidak sempurna. Tapi menangani sebagian besar kasus. Kalau parser gagal total, judge fallback ke simple metrics.