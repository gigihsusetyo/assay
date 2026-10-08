# ADR-004: LLM-as-Judge with Bring Your Own Key

**Status:** Accepted
**Date:** 4 October 2026
**Updated:** 8 October 2026

## Context

Assay measures RAG quality. The initial MVP used simple heuristic metrics: token overlap between answer and context. These are fast, deterministic, and free. But they are shallow. An answer that is semantically correct but uses different words scores low. An answer that copies tokens but is semantically wrong scores high.

To measure quality properly, LLM-as-judge is needed. An LLM reads the question, the answer, and the contexts, then decides whether the answer is grounded.

But LLM-as-judge has problems. It costs money. It is non-deterministic. And the judge itself needs validation.

The question is: who provides the LLM?

Options considered:

1. **Assay provides the LLM.** Assay picks a model, sets the API key, and pays the bill. Simple for users, but not sustainable for an open source project.

2. **User provides the LLM (BYOK).** User sets their own API key, picks their own model. Assay is a framework, not a provider.

3. **Hybrid.** Assay provides a free default, user can override. More complex, but user-friendly.

## Decision

The decision: BYOK (Bring Your Own Key).

Users set these environment variables:

```
ASSAY_JUDGE_PROVIDER=groq
ASSAY_JUDGE_MODEL=openai/gpt-oss-120b
ASSAY_JUDGE_API_KEY=gsk_...
ASSAY_JUDGE_BASE_URL=https://api.groq.com/openai/v1
```

If these are not set, the judge is disabled. Assay falls back to simple heuristic metrics. The user can still use Assay, just without LLM-based evaluation.

The OpenAI-compatible API is used. This means the same code works with OpenRouter, OpenAI, Anthropic (via proxy), Ollama, and any other provider that follows the same format.

No default LLM is provided. No free tier from Assay. No API key from Assay.

### Recommended Providers

As of October 2026, two providers are recommended for development and testing.

**Groq** offers 14,400 requests per day on the free tier. The model `openai/gpt-oss-120b` produces clean JSON and reliable judgments. The limitation is the daily token cap: 200,000 tokens per day on the free tier. For intensive testing with many entries or multiple votes, this cap can be reached quickly.

**Token Harbor** offers a value-based allowance with a rolling 7-day window. The model `deepseek-v4-flash:free` is more strict about qualifiers than Groq, which makes it a better fit for the groundedness prompt in this project. The trade-off is that the free route may retain prompt and response data, so it should not be used with sensitive documents.

OpenRouter is also supported, but the free tier is limited to 50 requests per day. This is too small for development. Adding credit ($10) unlocks 1,000 requests per day.

Ollama is supported for local, private inference. It requires a machine with enough RAM to run a model, and it does not work on older operating systems.

## Consequences

What is gained:

- Assay does not pay for LLM calls.
- Users are free to choose any model. Some teams need local models (Ollama) for data privacy. Some need GPT-4 for accuracy. Some need cheap models for volume.
- The code is provider-agnostic. The same judge module works with any OpenAI-compatible API.
- This matches industry standards. RAGAS, DeepEval, and TruLens all use BYOK.

What is sacrificed:

- Users must set up their own API key. This is friction. But our target users are engineers, and they understand this.
- Judge quality depends on the model the user picks. A weak model gives weak judgments. This is why we need judge validation (see below).
- No "out of the box" experience. Users cannot just clone and run. They need an API key.

## Judge Validation

Because judge quality varies by model, it needs to be measured. This is what makes Assay different from other tools.

The plan:

1. Build a calibration set: 50 questions with human-labeled groundedness, drawn from 21 Indonesian legal documents.
2. Build an adversarial suite: 20 cases covering number mutation, negation, modality, quantifier, condition dropped, refusal, multi-context, conflicting contexts, prompt injection, entity swap, paraphrase, cross-lingual, and hedging.
3. Run the judge on both sets.
4. Compute agreement with human labels using Cohen's kappa.
5. Probe for bias: position bias, verbosity bias, self-preference bias.
6. Report the results in the docs.

If the judge is not reliable, the user should not trust the groundedness scores. Better to know than to guess.

## Fallback Behavior

The judge can fail for several reasons:

- Rate limit (429).
- Server error (500).
- Invalid JSON output.

When the judge fails, Assay falls back to simple heuristic metrics. The CLI reports how many questions were judged by the LLM and how many fell back.

This means the pipeline never breaks. But the user should know that some scores came from heuristics, not from the judge.

## Multi-Provider Fallback

LLM providers are not always available. Rate limits, outages, and latency spikes are common. For a CI gate, a pipeline that stops when the provider is down is not useful.

Assay supports multiple judge providers. Users configure one or more via environment variables:

```
ASSAY_JUDGE_PROVIDER=groq
ASSAY_JUDGE_MODEL=openai/gpt-oss-120b
ASSAY_JUDGE_API_KEY=gsk_...
ASSAY_JUDGE_BASE_URL=https://api.groq.com/openai/v1

ASSAY_JUDGE_PROVIDER_2=gemini
ASSAY_JUDGE_MODEL_2=gemma-4-26b-a4b-it
ASSAY_JUDGE_API_KEY_2=AQ...
ASSAY_JUDGE_BASE_URL_2=https://generativelanguage.googleapis.com/v1beta/openai/
```

When the primary provider fails with a transient error (rate limit, timeout, connection error, server error), Assay tries the next provider in the list. If all providers fail, a JudgeError is raised.

Fallback is enabled by default. Set `ASSAY_JUDGE_FALLBACK=false` to disable it. When disabled, only the first provider is used, and any failure is surfaced immediately.

Different providers may give different judgments. This is a trade-off. Fallback keeps the pipeline running, but the user should know that the provider used may differ between runs. Assay records which provider was used in the result so the user can audit.

Provider configuration is flexible. Any OpenAI-compatible API works. Gemini uses a different authentication scheme and is handled through the google-genai SDK.

## Position Bias: Found and Fixed

On 4 October 2026, a position bias probe was run on the judge. The probe reverses the order of contexts and checks whether the judge's score changes.

The result: **50% flip rate** on a small two-entry probe. The same content, different order, different score. This is severe position bias.

The cause: the original prompt did not state that context order does not matter. The judge treated the first context as more important.

The fix: explicit rules were added to the prompt:

- Consider all contexts equally. The order of contexts does not matter.
- A claim is grounded if it is supported by ANY of the contexts.
- A claim is ungrounded only if it is supported by NONE of the contexts.

After the fix, the flip rate dropped to **0%**. No position bias detected on the same probe.

The judge validation still shows Cohen's kappa 1.000 on the 50-entry calibration set. The fix did not hurt accuracy.

Note: the position bias probe itself is small. Two entries is not enough to claim the bias is fully eliminated. It is evidence that the fix helped, not proof that the problem is gone. A larger probe is future work.

## Adversarial Suite

On 7 October 2026, an adversarial suite was added. It covers 20 cases across 20 categories: world knowledge leak, context over world, number mutation, negation flip, modality shift, quantifier shift, condition dropped, refusal correct, refusal false, refusal with hallucination, multi-context, conflicting contexts, prompt injection in context, prompt injection in answer, entity swap, paraphrase heavy, cross-lingual, distractor context, partial support, and hedged speculation.

The suite is in `examples/adversarial_suite.json`. The runner is `scripts/run_adversarial_suite.py`.

The first run passed 85%. Three cases failed: quantifier shift, condition dropped, and multi-context. The prompt was fixed for logical deduction, and the code was fixed for evidence separators. After two more iterations, the suite passed 100%.

The suite is small. 20 cases is not enough to claim robustness. But it catches the failure modes that matter most, and it can be expanded over time.

## Answer Relevance: A Separate Metric

On 7 October 2026, a second metric was added: answer relevance.

Groundedness asks: is the answer supported by the contexts? Answer relevance asks a different question: does the answer address what the question asked?

These are not the same. An answer can be grounded but irrelevant. If the question asks about password reset and the answer talks about rate limits, the answer may be perfectly grounded in the contexts and still fail to answer the question.

The metric decomposes the question into atomic aspects. For each aspect, the judge decides whether the answer addresses it. The score is the fraction of aspects addressed. The answer is relevant only if every aspect is addressed.

Example:

- Question: "What is the rate limit and how do I increase it?"
- Answer: "The rate limit is 100 requests per minute."
- Aspects: [the rate limit (addressed), how to increase it (not addressed)]
- Score: 0.5
- Relevant: false

This is a policy decision. The judge does not decide whether the answer is factually correct or grounded; that is groundedness. It only decides whether the answer responds to the question.

The prompt lives in `judge.py` as `ANSWER_RELEVANCE_PROMPT`. The function is `judge_answer_relevance`. The result is stored in `Result.answer_relevance`.

This is the first step toward multi-dimensional evaluation. Groundedness alone is not enough to certify a RAG system. A system that always answers "I do not know" is perfectly grounded and completely useless. Answer relevance catches that.

## Majority Vote

On 7 October 2026, a majority vote option was added. When `ASSAY_JUDGE_VOTES` is greater than 1, the judge runs multiple times per question and the final decision is taken by majority vote.

This exists because LLM providers are not fully deterministic, even at temperature 0. During validation, two entries flipped between runs: one that was grounded in one run and not grounded in the next. For a CI gate, that is a problem. A gate that fails today and passes tomorrow on the same code is not a gate.

Majority vote reduces this instability. The trade-off is cost: three votes cost three times as much as one vote.

The option is configurable rather than always-on. Users who care about cost more than stability can set `ASSAY_JUDGE_VOTES=1`. Users who run a CI gate can set `ASSAY_JUDGE_VOTES=3`.

Majority vote does not fix the root cause of ambiguity. It reduces the symptom. When a case is genuinely ambiguous in the prompt, two out of three runs may still agree on the wrong answer. The fix for that is a better prompt, not more votes. The two work together.

## Retry Logic

The judge retries on rate limit, server errors, timeouts, and connection errors. Up to 3 attempts, with exponential backoff (1s, 2s, 4s). This is standard practice.

When retries within a single provider are exhausted, and multi-provider fallback is enabled, the next provider is tried. Each provider gets its own retry budget.

## JSON Parsing

Not all models return clean JSON, even when asked. A tolerant parser is used:

1. Try direct JSON parse.
2. Try to extract JSON from markdown fences.
3. Try to find the first { ... } block.
4. Strip `<thought>` blocks that some models include before the JSON.

If no valid JSON is found, the judge fails closed. It raises `JudgeError` instead of guessing. The caller falls back to simple metrics and reports the failure.

This is deliberate. A parser that guesses can turn a broken response into a false "grounded" result, which is worse than an honest error.

---

# ADR-004: LLM-as-Judge dengan Bring Your Own Key

**Status:** Diterima
**Tanggal:** 4 Oktober 2026
**Diperbarui:** 8 Oktober 2026

## Konteks

Assay mengukur kualitas RAG. MVP awal pakai metrics heuristic sederhana: token overlap antara jawaban dan konteks. Cepat, deterministic, gratis. Tapi dangkal. Jawaban yang benar secara semantic tapi pakai kata berbeda akan skor rendah. Jawaban yang copy token tapi salah secara semantic akan skor tinggi.

Untuk mengukur kualitas dengan benar, LLM-as-judge diperlukan. LLM baca pertanyaan, jawaban, dan konteks, lalu putuskan apakah jawaban didukung konteks.

Tapi LLM-as-judge ada masalah. Biaya. Non-deterministic. Dan judge-nya sendiri butuh validasi.

Pertanyaannya: siapa yang menyediakan LLM?

Opsi yang dipertimbangkan:

1. **Assay yang sediakan LLM.** Assay pilih model, set API key, bayar tagihan. Simpel untuk user, tapi tidak sustainable untuk open source.

2. **User yang sediakan LLM (BYOK).** User set API key sendiri, pilih model sendiri. Assay cuma framework, bukan provider.

3. **Hybrid.** Assay sediakan default gratis, user bisa override. Lebih kompleks, tapi user-friendly.

## Keputusan

Keputusannya: BYOK (Bring Your Own Key).

User set environment variable ini:

```
ASSAY_JUDGE_PROVIDER=groq
ASSAY_JUDGE_MODEL=openai/gpt-oss-120b
ASSAY_JUDGE_API_KEY=gsk_...
ASSAY_JUDGE_BASE_URL=https://api.groq.com/openai/v1
```

Kalau tidak di-set, judge tidak aktif. Assay fallback ke simple heuristic metrics. User tetap bisa pakai Assay, cuma tanpa LLM-based evaluation.

OpenAI-compatible API digunakan. Artinya kode yang sama bekerja dengan OpenRouter, OpenAI, Anthropic (via proxy), Ollama, dan provider apa pun yang ikut format yang sama.

Tidak ada default LLM yang disediakan. Tidak ada free tier dari Assay. Tidak ada API key dari Assay.

### Provider yang Direkomendasikan

Per Oktober 2026, dua provider direkomendasikan untuk development dan testing.

**Groq** menawarkan 14.400 request per hari di free tier. Model `openai/gpt-oss-120b` menghasilkan JSON bersih dan judgment yang reliable. Batasannya adalah token harian: 200.000 token per hari di free tier. Untuk testing intensif dengan banyak entries atau multiple votes, batas ini bisa cepat tercapai.

**Token Harbor** menawarkan allowance berbasis nilai dengan jendela rolling 7 hari. Model `deepseek-v4-flash:free` lebih ketat soal qualifier daripada Groq, yang membuatnya lebih cocok untuk prompt groundedness di proyek ini. Trade-off-nya adalah free route mungkin menyimpan prompt dan response, jadi jangan dipakai dengan dokumen sensitif.

OpenRouter juga didukung, tapi free tier-nya terbatas 50 request per hari. Ini terlalu kecil untuk development. Menambah credit ($10) membuka 1.000 request per hari.

Ollama didukung untuk inference lokal dan privat. Butuh mesin dengan RAM cukup untuk menjalankan model, dan tidak bekerja di sistem operasi lama.

## Konsekuensi

Yang didapat:

- Assay tidak bayar LLM call.
- User bebas pilih model. Tim compliance mungkin butuh model lokal (Ollama) untuk privasi data. Tim lain butuh GPT-4 untuk akurasi. Tim lain butuh model murah untuk volume.
- Kode provider-agnostic. Modul judge yang sama bekerja dengan API OpenAI-compatible apa pun.
- Ini sesuai standar industri. RAGAS, DeepEval, TruLens semua pakai BYOK.

Yang dikorbankan:

- User harus setup API key sendiri. Ini friksi. Tapi target user adalah engineer, dan mereka paham ini.
- Kualitas judge bergantung pada model yang user pilih. Model lemah kasih judgment lemah. Ini kenapa judge validation diperlukan.
- Tidak ada pengalaman "out of the box". User tidak bisa langsung clone dan jalan. Mereka butuh API key.

## Validasi Judge

Karena kualitas judge bervariasi, perlu diukur. Ini yang membedakan Assay dari tools lain.

Rencananya:

1. Bangun calibration set: 50 pertanyaan dengan label groundedness dari manusia, diambil dari 21 dokumen hukum Indonesia.
2. Bangun adversarial suite: 20 kasus yang mencakup number mutation, negation, modality, quantifier, condition dropped, refusal, multi-context, conflicting contexts, prompt injection, entity swap, paraphrase, cross-lingual, dan hedging.
3. Jalankan judge pada kedua set.
4. Hitung agreement dengan human labels pakai Cohen's kappa.
5. Probe bias: position bias, verbosity bias, self-preference bias.
6. Laporkan hasilnya di dokumentasi.

Kalau judge tidak reliable, user tidak boleh percaya skor groundedness-nya. Lebih baik tahu daripada menebak.

## Fallback Behavior

Judge bisa gagal karena beberapa alasan:

- Rate limit (429).
- Server error (500).
- Output JSON tidak valid.

Kalau judge gagal, Assay fallback ke simple heuristic metrics. CLI melaporkan berapa pertanyaan yang di-judge LLM dan berapa yang fallback.

Artinya pipeline tidak pernah putus. Tapi user harus tahu bahwa beberapa skor berasal dari heuristic, bukan dari judge.

## Multi-Provider Fallback

Provider LLM tidak selalu tersedia. Rate limit, outage, dan lonjakan latency umum terjadi. Untuk CI gate, pipeline yang berhenti saat provider down tidak berguna.

Assay mendukung beberapa provider judge. User konfigurasi satu atau lebih via environment variable:

```
ASSAY_JUDGE_PROVIDER=groq
ASSAY_JUDGE_MODEL=openai/gpt-oss-120b
ASSAY_JUDGE_API_KEY=gsk_...
ASSAY_JUDGE_BASE_URL=https://api.groq.com/openai/v1

ASSAY_JUDGE_PROVIDER_2=gemini
ASSAY_JUDGE_MODEL_2=gemma-4-26b-a4b-it
ASSAY_JUDGE_API_KEY_2=AQ...
ASSAY_JUDGE_BASE_URL_2=https://generativelanguage.googleapis.com/v1beta/openai/
```

Ketika provider utama gagal dengan error transient (rate limit, timeout, connection error, server error), Assay mencoba provider berikutnya di daftar. Kalau semua provider gagal, JudgeError di-raise.

Fallback aktif secara default. Set `ASSAY_JUDGE_FALLBACK=false` untuk mematikan. Ketika dimatikan, hanya provider pertama yang dipakai, dan kegagalan langsung dilaporkan.

Provider berbeda bisa memberi judgment berbeda. Ini trade-off. Fallback menjaga pipeline tetap jalan, tapi user harus tahu bahwa provider yang dipakai bisa berbeda antar run. Assay mencatat provider mana yang dipakai di result supaya user bisa audit.

Konfigurasi provider fleksibel. API OpenAI-compatible apa pun bekerja. Gemini pakai skema autentikasi berbeda dan ditangani lewat SDK google-genai.

## Bias Posisi: Ditemukan dan Diperbaiki

Pada 4 Oktober 2026, probe bias posisi dijalankan pada judge. Probe membalik urutan context dan memeriksa apakah skor judge berubah.

Hasilnya: **50% flip rate** pada probe kecil dua entries. Konten sama, urutan beda, skor beda. Ini bias posisi yang parah.

Penyebabnya: prompt awal tidak menyatakan bahwa urutan context tidak penting. Judge menganggap context pertama lebih penting.

Perbaikannya: aturan eksplisit ditambahkan ke prompt:

- Pertimbangkan semua context sama penting. Urutan context tidak penting.
- Klaim grounded jika didukung oleh SALAH SATU context.
- Klaim ungrounded hanya jika tidak didukung oleh SEMUA context.

Setelah perbaikan, flip rate turun ke **0%**. Tidak ada bias posisi terdeteksi pada probe yang sama.

Validasi judge tetap menunjukkan Cohen's kappa 1.000 pada calibration set 50 entries. Perbaikan tidak merusak akurasi.

Catatan: probe bias posisi itu sendiri kecil. Dua entries tidak cukup untuk klaim bahwa bias sepenuhnya hilang. Ini bukti bahwa perbaikan membantu, bukan bukti bahwa masalahnya selesai. Probe yang lebih besar adalah future work.

## Adversarial Suite

Pada 7 Oktober 2026, adversarial suite ditambahkan. Mencakup 20 kasus di 20 kategori: world knowledge leak, context over world, number mutation, negation flip, modality shift, quantifier shift, condition dropped, refusal correct, refusal false, refusal with hallucination, multi-context, conflicting contexts, prompt injection di context, prompt injection di answer, entity swap, paraphrase heavy, cross-lingual, distractor context, partial support, dan hedged speculation.

Suite ada di `examples/adversarial_suite.json`. Runner-nya `scripts/run_adversarial_suite.py`.

Run pertama lulus 85%. Tiga kasus gagal: quantifier shift, condition dropped, dan multi-context. Prompt diperbaiki untuk inferensi logis, dan kode diperbaiki untuk separator evidence. Setelah dua iterasi lagi, suite lulus 100%.

Suite ini kecil. 20 kasus tidak cukup untuk klaim robustness. Tapi dia menangkap failure mode yang paling penting, dan bisa diperluas seiring waktu.

## Answer Relevance: Metrik Terpisah

Pada 7 Oktober 2026, metrik kedua ditambahkan: answer relevance.

Groundedness bertanya: apakah jawaban didukung konteks? Answer relevance bertanya hal berbeda: apakah jawaban menjawab apa yang ditanyakan?

Ini bukan hal yang sama. Jawaban bisa grounded tapi tidak relevan. Kalau pertanyaan tentang reset password dan jawaban tentang rate limit, jawaban itu mungkin grounded sempurna di konteks tapi gagal menjawab pertanyaan.

Metrik ini mendekomposisi pertanyaan menjadi aspek atomik. Untuk setiap aspek, judge memutuskan apakah jawaban menjawabnya. Skor adalah fraksi aspek yang dijawab. Jawaban relevan hanya jika semua aspek dijawab.

Contoh:

- Pertanyaan: "Berapa rate limit dan bagaimana cara menaikkannya?"
- Jawaban: "Rate limit adalah 100 request per menit."
- Aspek: [rate limit (dijawab), cara menaikkan (tidak dijawab)]
- Skor: 0.5
- Relevan: false

Ini keputusan kebijakan. Judge tidak memutuskan apakah jawaban benar secara faktual atau grounded; itu groundedness. Judge hanya memutuskan apakah jawaban merespons pertanyaan.

Prompt ada di `judge.py` sebagai `ANSWER_RELEVANCE_PROMPT`. Fungsinya `judge_answer_relevance`. Hasilnya disimpan di `Result.answer_relevance`.

Ini langkah pertama menuju evaluasi multi-dimensi. Groundedness saja tidak cukup untuk mensertifikasi sistem RAG. Sistem yang selalu menjawab "Saya tidak tahu" grounded sempurna dan sama sekali tidak berguna. Answer relevance menangkap itu.

## Majority Vote

Pada 7 Oktober 2026, opsi majority vote ditambahkan. Ketika `ASSAY_JUDGE_VOTES` lebih besar dari 1, judge berjalan beberapa kali per pertanyaan dan keputusan akhir diambil lewat majority vote.

Ini ada karena provider LLM tidak sepenuhnya deterministik, bahkan di temperature 0. Saat validasi, dua entries berubah antar run: satu grounded di satu run dan tidak grounded di run berikutnya. Untuk CI gate, ini masalah. Gate yang gagal hari ini dan lulus besok pada kode yang sama bukan gate.

Majority vote mengurangi instabilitas ini. Trade-off-nya biaya: tiga votes berbiaya tiga kali satu vote.

Opsi ini configurable, bukan selalu aktif. User yang lebih peduli biaya daripada stabilitas bisa set `ASSAY_JUDGE_VOTES=1`. User yang jalankan CI gate bisa set `ASSAY_JUDGE_VOTES=3`.

Majority vote tidak menyelesaikan akar masalah ambiguitas. Dia mengurangi gejala. Ketika kasus benar-benar ambigu di prompt, dua dari tiga run bisa tetap setuju pada jawaban yang salah. Yang menyelesaikan itu adalah prompt yang lebih baik, bukan lebih banyak votes. Keduanya bekerja bersama.

## Retry Logic

Judge retry pada rate limit, server error, timeout, dan connection error. Sampai 3 kali, dengan exponential backoff (1s, 2s, 4s). Ini praktik standar.

Ketika retry dalam satu provider habis, dan multi-provider fallback aktif, provider berikutnya dicoba. Setiap provider punya budget retry sendiri.

## JSON Parsing

Tidak semua model return JSON bersih, meskipun diminta. Parser toleran digunakan:

1. Coba parse JSON langsung.
2. Coba ekstrak JSON dari markdown fence.
3. Coba cari blok { ... } pertama.
4. Strip blok `<thought>` yang disertakan sebagian model sebelum JSON.

Kalau tidak ada JSON valid, judge gagal tertutup. Dia raise `JudgeError`, bukan menebak. Caller fallback ke simple metrics dan laporkan kegagalan.

Ini disengaja. Parser yang menebak bisa mengubah respons rusak menjadi hasil "grounded" palsu, yang lebih buruk dari error jujur.
```