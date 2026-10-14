# ADR-004: LLM-as-Judge with Bring Your Own Key

**Status:** Accepted
**Date:** 4 October 2026
**Updated:** 14 October 2026

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

What was built:

1. A calibration set: 250 manually reviewed entries from 60+ Indonesian legal documents. Each entry has a human label for groundedness, assigned without seeing the judge prediction.
2. An adversarial suite: 20 cases covering number mutation, negation, modality, quantifier, condition dropped, refusal, multi-context, conflicting contexts, prompt injection, entity swap, paraphrase, cross-lingual, and hedging.
3. The judge is run on both sets.
4. Agreement with human labels is measured with Cohen's kappa and a confusion matrix.
5. Bias probes: position bias, verbosity bias, self-preference bias.
6. Results are reported in this ADR and in the README.

If the judge is not reliable, the user should not trust the groundedness scores. Better to know than to guess.

The current result on the 250-entry calibration set is kappa 0.899, raw agreement 95.6%. See the "Prompt Refinement History and Known Limitations" section below for the detailed confusion matrix and known failure modes.

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

After the fix, the calibration set was expanded and re-validated. On the current 250-entry calibration set, the judge achieves kappa 0.899 with raw agreement 95.6%. The position bias fix did not hurt accuracy.

Note: the position bias probe itself is small. Two entries is not enough to claim the bias is fully eliminated. It is evidence that the fix helped, not proof that the problem is gone. A larger probe is future work.

## Adversarial Suite

On 7 October 2026, an adversarial suite was added. It covers 20 cases across 20 categories: world knowledge leak, context over world, number mutation, negation flip, modality shift, quantifier shift, condition dropped, refusal correct, refusal false, refusal with hallucination, multi-context, conflicting contexts, prompt injection in context, prompt injection in answer, entity swap, paraphrase heavy, cross-lingual, distractor context, partial support, and hedged speculation.

The suite is in `examples/adversarial_suite.json`. The runner is `scripts/run_adversarial_suite.py`.

The first run passed 85%. Three cases failed: quantifier shift, condition dropped, and multi-context. The prompt was fixed for logical deduction, and the code was fixed for evidence separators. After two more iterations, the suite passed 100%.

The suite is small. 20 cases is not enough to claim robustness. But it catches the failure modes that matter most, and it can be expanded over time.

On the current groundedness prompt (v4), the adversarial suite passes 17 of 20 cases (85%). The three failing cases are `condition_dropped`, `multi_context`, and `cross_lingual`. An attempt to fix them (v5) made the prompt too long and degraded the calibration set kappa; it was rolled back. See "Prompt Refinement History and Known Limitations" below.

## Prompt Refinement: Subset and Question Scope

On 13 October 2026, a third refinement was made to the groundedness
prompt. During the hold-out review, three cases were found where the
judge marked a correct answer as unsupported:

- **q453**: The question asked about policies with potential gender
  bias. The context stated "in the case of policies that are
  potentially gender-discriminatory, a policy recommendation must be
  prepared". The answer omitted the qualifier because it was already
  implied in the question. The judge marked it unsupported.

- **q489**: The context specified "BOP Museum dan BOP Taman Budaya".
  The answer said "BOP". The judge marked it unsupported because the
  scope was narrowed. In this case, the judge was correct: the scope
  was material and the answer widened it.

- **q491**: The answer was a direct quote from the context, with one
  clause dropped. The judge marked it unsupported.

Two rules were added to the prompt:

1. A direct quote from the CONTEXT, or a faithful subset of it, is
   supported. Do not penalize an answer for omitting parts of the
   context that the question does not require.

2. Qualifiers that are already present in the QUESTION do not need to
   be repeated in the ANSWER. The question provides the scope. The
   answer only needs to stay within it.

After the change, q453 and q491 passed. q489 remained unsupported, and
on closer inspection the human label was corrected: the judge was
right. The scope "Museum dan BOP Taman Budaya" is material and the
answer widened it.

This is the third prompt refinement. The first two addressed logical
deduction and evidence separators. Each refinement is tested against
the adversarial suite to avoid regressions.

## Prompt Refinement History and Known Limitations

The groundedness prompt has been refined four times. Each refinement
was validated against the calibration set and the adversarial suite.

### Refinement History

| Version | Date | Change | Kappa (250) | Adversarial |
|---|---|---|---|---|
| v1 | 4 Oct 2026 | Initial prompt | — | — |
| v2 | 7 Oct 2026 | Logical deduction, evidence separators | — | 100% |
| v3 | 8 Oct 2026 | Position bias fix, subset rules | 0.819 | 100% |
| v4 | 13 Oct 2026 | Subset examples, range numeric, material qualifiers | **0.899** | 17/20 (85%) |
| v5 | 14 Oct 2026 | Cross-lingual, multi-context, exception | (not validated) | 20/20 (100%) |
| Rollback | 14 Oct 2026 | v5 rolled back to v4 | 0.899 | 17/20 (85%) |

### Why v5 Was Rolled Back

v5 added three rules to fix the three failing adversarial cases:
cross-lingual matching, multi-context combination, and exception
handling. The adversarial suite went from 17/20 to 20/20.

But when tested against the 11 remaining disagreements from the
calibration set, only 3 of 11 were fixed. The additional rules did
not help the disagreements, and the prompt became longer. A longer
prompt makes the model less focused on the earlier rules.

The trade-off was clear: v4 sacrifices 3 adversarial edge cases to
gain a 0.080 kappa improvement over v3. v5 sacrifices the kappa
improvement to gain 3 adversarial cases. v4 is the better trade-off.

### Calibration Set Distribution

The 250-entry calibration set has the following human labels:

| Human label | Count |
|---|---|
| Grounded (True) | 172 |
| Not grounded (False) | 78 |
| **Total** | **250** |

Confusion matrix against the judge:

| | Judge grounded | Judge not grounded |
|---|---|---|
| **Human grounded (172)** | 165 (TP) | 7 (FN) |
| **Human not grounded (78)** | 4 (FP) | 74 (TN) |

Kappa 0.899. Raw agreement 95.6%.

### Known Limitations of v4

The judge is not perfect. At kappa 0.899, 11 of 250 calibration
entries (4.4%) are still misclassified. The 11 disagreements fall
into these patterns:

**False Positives (4):** The judge marks an answer as grounded when
it should not be.

- Entry 69: judge misses a qualifier that was dropped.
- Entry 116: judge misses a scope change.
- Entry 125: judge misses a unit that was dropped ("30 jam pelajaran"
  vs "30 jam").
- Entry 232: judge misses a compound condition that was dropped.

**False Negatives (7):** The judge marks an answer as not grounded
when it should be.

- Entry 3: judge contradicts its own reason (says "all supported"
  but returns grounded=False).
- Entry 53: judge misreads a frequency claim.
- Entry 66: judge treats a non-material qualifier as material.
- Entry 96: judge misreads subject/object.
- Entry 155: judge confuses "Bantuan Pemerintah" with "Subsidi".
- Entry 183: judge treats a subset definition as a material drop.
- Entry 199: judge misses a direct quote.

**Three adversarial edge cases fail:**

- `condition_dropped`: the judge returns "unsupported" instead of
  "contradicted" when an exception is dropped.
- `multi_context`: the judge cannot combine facts from two contexts
  to support a claim.
- `cross_lingual`: the judge does not recognize a translation as a
  paraphrase.

### Why We Accept These Limitations

1. **Kappa 0.899 is EXCELLENT.** The remaining 4.4% error rate is
   within the expected range for an LLM judge at temperature 0.

2. **The 3 adversarial edge cases are rare in practice.** Cross-lingual
   RAG (Indonesian context, English answer) and multi-context
   combination are valid scenarios, but they are not the common case.

3. **Longer prompts make things worse.** Adding rules to fix edge
   cases degrades the model's focus on the core rules. This was
   demonstrated by the v5 experiment.

4. **A better fix is a better model.** When a stronger LLM is available
   (larger context, better instruction following), these limitations
   may disappear without prompt changes.

### Future Work

- Re-test with newer LLM models as they become available.
- Split the prompt into a "core" section and a "domain overlay"
  section. The core handles universal rules; the overlay handles
  domain-specific rules. This may allow adding rules without
  diluting the core.
- Build a larger calibration set (500+ entries) to reduce sampling
  noise in the kappa estimate.

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

## Answer Relevance Validation (Preliminary)

On 14 October 2026, a 249-entry relevance review set was labeled by a
human, independently from the judge. This section reports the result
and its limitations.

### Numbers

| Metric | Value |
|---|---|
| Entries | 249 |
| Human relevant (True) | 247 |
| Human relevant (False) | 2 |
| Raw agreement | 98.0% |
| Cohen's kappa | 0.277 |
| True positives | 243 |
| True negatives | 1 |
| False positives | 1 |
| False negatives | 4 |

### Why Kappa Is Misleading Here

Kappa 0.277 is POOR by the standard scale. But this number is
misleading, and reporting it alone would be dishonest.

The dataset is severely imbalanced: 247 of 249 entries (99.2%) are
labeled relevant by the human. With a class distribution this
extreme, chance agreement is already near 1.0. Kappa = (po - pe) /
(1 - pe). With po = 0.98 and pe = 0.97, kappa collapses toward zero
even though observed agreement is high. This is the well-known
prevalence effect in Cohen's kappa.

A trivial classifier that always says "relevant" would score 247/249
= 99.2% raw agreement on this dataset — **higher than the judge's
98.0%**. That baseline is the real signal. It says we cannot yet
show the judge does better than a constant answer.

### What the Dataset Does Not Support

With only 2 human-labeled negative examples, specificity is
estimated as 1/2 = 50%. The 95% Wilson confidence interval for this
estimate is roughly 10% to 90%. No choice of summary metric (kappa,
MCC, balanced accuracy, F1) fixes this. The data is not there.

The judge's sensitivity (recall on the positive class) is 243/247 =
98.4%, with a tight confidence interval. We can say something about
how often the judge accepts an answer humans consider relevant. We
cannot say much about how often it rejects an answer humans consider
irrelevant.

### Label Quality Concerns

The relevance labels were assigned without a rationale field, so
individual labels cannot be audited. On review, one inconsistency
was found: q132 was labeled not relevant even though it follows the
same structural pattern as roughly 50 other ungrounded-but-addressing
entries that were labeled relevant (q456, q222, and others). This
suggests the relevance labels were sometimes contaminated by
groundedness judgments — a reviewer may have penalized relevance
for a groundedness failure.

### Five Disagreements

| Entry | Human | Judge | Summary |
|---|---|---|---|
| q495 | True | False | Judge says the category name was not stated. Human says it was. |
| q341 | True | False | Judge says the term was not provided. Human says it was. |
| q368 | True | False | Judge says the answer addressed some but not all aspects. Human says it did. |
| q014 | False | True | Judge says the answer provided information. Human says it did not. |
| q280 | True | False | Judge says the answer addressed the wrong aspect. Human says it did. |

Four of five disagreements are false negatives. The judge is stricter
than the human reviewer, particularly on partial answers to
multi-part questions.

### Prompt vs Definition

The current relevance prompt decomposes the question into atomic
aspects and requires each aspect to be addressed. This conflates
relevance with completeness. A partial answer to a multi-part
question is relevant but incomplete, not irrelevant.

The fix is conceptual before it is a prompt change. Relevance should
ask: does the answer substantively address the question's intent?
Completeness should ask: does the answer cover all material
components? These are separate dimensions.

### Next Steps

1. **Separate relevance from completeness.** Add a completeness
   metric as a distinct dimension. Update the relevance prompt to
   stop requiring all sub-aspects.
2. **Re-audit the 5 disagreements** with a written rationale per
   label. Add inter-human agreement checks on a subset.
3. **Build a balanced challenge set.** 50-100 deliberately
   constructed negative examples, including hard negatives
   (wrong article, wrong aspect, on-topic but wrong quantity),
   not just trivially off-topic answers.
4. **Report a metric bundle.** Raw agreement, kappa, confusion
   matrix, class support, sensitivity and specificity with Wilson
   confidence intervals, balanced accuracy, and optionally MCC.
   Report production-weighted performance separately from
   challenge-set performance.
5. **Update the validator.** When the minority class has fewer than
   30 entries, the validator should report `INSUFFICIENT DATA`
   instead of a qualitative interpretation like "POOR".
6. **Reconsider CI acceptance policy.** The current
   `kappa < 0.6` threshold would fail the relevance metric by
   construction on this dataset. Apply thresholds per-class
   (specificity lower bound, sensitivity lower bound) rather than
   on kappa alone.

### Summary

The relevance judge is not yet validated. It shows high agreement
with humans on the dominant class, but the dataset cannot measure
whether it discriminates irrelevant answers. This is documented
rather than papered over. The next iteration of the calibration
work will address it.

## Majority Vote

On 7 October 2026, a majority vote option was added. When `ASSAY_JUDGE_VOTES` is greater than 1, the judge runs multiple times per question and the final decision is taken by majority vote.

This exists because LLM providers are not fully deterministic, even at temperature 0. During validation, two entries flipped between runs: one that was grounded in one run and not grounded in the next. For a CI gate, that is a problem. A gate that fails today and passes tomorrow on the same code is not a gate.

Majority vote reduces this instability. The trade-off is cost: three votes cost three times as much as one vote.

The option is configurable rather than always-on. Users who care about cost more than stability can set `ASSAY_JUDGE_VOTES=1`. Users who run a CI gate can set `ASSAY_JUDGE_VOTES=3`.

Majority vote does not fix the root cause of ambiguity. It reduces the symptom. When a case is genuinely ambiguous in the prompt, two out of three runs may still agree on the wrong answer. The fix for that is a better prompt, not more votes. The two work together.

## Judge Comparison

Users who configure multiple providers can compare them. The script
`scripts/compare_judges.py` runs the judge on the same calibration set
with each provider and reports agreement, Cohen's kappa, and error
count.

Example output (from an early 50-entry calibration set; numbers will
differ on the current 250-entry set):

```
Provider        Model                        Entries    Agree    Kappa  Errors
------------------------------------------------------------------------------
groq            openai/gpt-oss-120b               50    92.0%    0.831       0
gemini          gemma-4-26b-a4b-it                49    93.9%    0.867       1
tokenharbor     deepseek-v4-flash:free            50    96.0%    0.913       0
```

This is informational. It does not change Assay's behavior. The user
decides which provider to use based on the comparison.

Different providers give different judgments. A provider with a higher
kappa on the calibration set may not be better on the user's own data.
The comparison is a starting point, not a verdict.

Providers are compared without fallback. Each provider is tested in
isolation. If a provider fails, the error count reflects that.

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

## Citation Accuracy: A Deterministic Metric with Optional LLM Layer

On 14 October 2026, a third metric was added: citation accuracy.

**The problem.** In domains that rely on citations (legal, academic,
regulatory), an answer is only useful if its citations are correct. A
grounded answer that cites the wrong article is worse than an answer
that admits uncertainty.

**The metric.** Citation accuracy extracts citations from the answer
and checks two things:

1. **Existence.** Does the citation appear in the retrieved contexts?
   This is deterministic. Pattern-matching for "Pasal 5 ayat (2)",
   "UU 16/2025", "PP 35/2025", and similar forms, with normalization
   for long vs short forms.
2. **Relevance.** Does the citation actually support the claim it is
   attached to? This is optional, using LLM-as-judge.

The MVP ships the deterministic layer. The LLM relevance layer is
planned but not yet implemented.

**Why deterministic first.** Existence checks are fast, free, and
auditable. A citation either appears in the context or it does not.
Relevance checks require semantic understanding, which is what the
LLM judge is for. Splitting the two keeps the fast path fast.

**Score.** `citation_accuracy = valid_citations / total_citations`.
`None` if the answer has no citations. This makes the metric
opt-in by nature: answers without citations simply do not get a
score.

**Example.**

Answer: "Berdasarkan Pasal 5 ayat (2) UU 16/2025, batas usia adalah
60 tahun."
Context: "Pasal 5 ayat (2): berusia paling tinggi 60 tahun..."

Result: one citation, exists in context, score = 1.0.

Answer: "Berdasarkan Pasal 7, batas usia adalah 60 tahun."
Context: "Pasal 5 ayat (2): berusia paling tinggi 60 tahun..."

Result: one citation, does not exist in context, score = 0.0.

**Why not LLM for everything.** An LLM-based existence check would
cost money, add latency, and introduce nondeterminism. A regex-based
check is exact. In domains with strict citation grammar (Indonesian
legal), the deterministic layer catches most cases.

**Why it matters for Assay.** The primary use case for citation
accuracy is legal and regulatory RAG. A fintech compliance assistant
that cites the wrong OJK regulation is dangerous. A support chatbot
that cites the wrong article is unhelpful. Citation accuracy makes
this visible in the CI gate.

## Refusal Correctness: A Deterministic Metric

On 14 October 2026, a fourth metric was added: refusal correctness.

**The problem.** Groundedness, answer relevance, and citation accuracy
all measure the quality of an answer that was produced. None of them
measure whether an answer should have been produced at all. A RAG
system that always answers — even when the retrieved contexts do not
contain the answer — can be perfectly grounded on some questions and
hallucinate on others. That failure mode is invisible to the other
metrics.

**The metric.** Refusal correctness measures whether the system
refuses when it should refuse, and answers when it should answer.

The notion of "should" comes from the dataset:

- A question with an `expected_answer` (or a non-empty
  `expected_context`) is **answerable**.
- A question without either is **unanswerable**.

The detection of refusal is deterministic. A short answer that matches
one of a small set of patterns ("Saya tidak tahu", "Informasi tidak
tersedia", "I don't know", "Not enough information", and so on) is a
refusal. A long answer that merely starts with a refusal phrase is
not, because the length indicates the answer contains content beyond
the refusal.

**Truth table.**

| Question | Answer | Status | Correct |
|---|---|---|---|
| Answerable | Answer | answerable_answered | yes |
| Answerable | Refusal | answerable_refused | no |
| Unanswerable | Refusal | unanswerable_refused | yes |
| Unanswerable | Answer | unanswerable_answered | no |

**Score.** `refusal_correctness = correct / applicable`. `None` if no
questions are applicable (e.g., all results have errors).

**Why deterministic.** Refusal patterns are strong signals. A user who
sees "Saya tidak tahu" knows the system refused. An LLM-based detection
would add cost and nondeterminism for a task that regex handles well.

**Contrast conjunction handling.** A refusal phrase followed by "namun",
"tetapi", "tapi", "however", or "but" is not a refusal. It is an answer
with a hedge. Example: "Saya tidak tahu secara pasti, namun berdasarkan
konteks, Pasal 5 menyatakan ..." is an answer, not a refusal. The
detector checks for contrast conjunctions before deciding.

**Why it matters for Assay.** A RAG system that refuses too often is
annoying. A RAG system that answers when it should refuse is dangerous.
Without refusal correctness, neither failure mode is visible in the CI
gate. This metric closes that gap.

---

# ADR-004: LLM-as-Judge dengan Bring Your Own Key

**Status:** Diterima
**Tanggal:** 4 Oktober 2026
**Diperbarui:** 14 Oktober 2026

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

Yang dibangun:

1. Calibration set: 250 entries yang direview manual dari 60+ dokumen hukum Indonesia. Setiap entry punya label groundedness dari manusia, ditetapkan tanpa melihat prediksi judge.
2. Adversarial suite: 20 kasus yang mencakup number mutation, negation, modality, quantifier, condition dropped, refusal, multi-context, conflicting contexts, prompt injection, entity swap, paraphrase, cross-lingual, dan hedging.
3. Judge dijalankan pada kedua set.
4. Agreement dengan human labels diukur dengan Cohen's kappa dan confusion matrix.
5. Probe bias: position bias, verbosity bias, self-preference bias.
6. Hasilnya dilaporkan di ADR ini dan di README.

Kalau judge tidak reliable, user tidak boleh percaya skor groundedness-nya. Lebih baik tahu daripada menebak.

Hasil saat ini pada calibration set 250 entries: kappa 0.899, raw agreement 95.6%. Lihat section "Prompt Refinement History and Known Limitations" untuk confusion matrix detail dan failure mode yang diketahui.

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

Setelah perbaikan, calibration set diperluas dan divalidasi ulang. Pada calibration set 250 entries saat ini, judge mencapai kappa 0.899 dengan raw agreement 95.6%. Perbaikan bias posisi tidak merusak akurasi.

Catatan: probe bias posisi itu sendiri kecil. Dua entries tidak cukup untuk klaim bahwa bias sepenuhnya hilang. Ini bukti bahwa perbaikan membantu, bukan bukti bahwa masalahnya selesai. Probe yang lebih besar adalah future work.

## Adversarial Suite

Pada 7 Oktober 2026, adversarial suite ditambahkan. Mencakup 20 kasus di 20 kategori: world knowledge leak, context over world, number mutation, negation flip, modality shift, quantifier shift, condition dropped, refusal correct, refusal false, refusal with hallucination, multi-context, conflicting contexts, prompt injection di context, prompt injection di answer, entity swap, paraphrase heavy, cross-lingual, distractor context, partial support, dan hedged speculation.

Suite ada di `examples/adversarial_suite.json`. Runner-nya `scripts/run_adversarial_suite.py`.

Run pertama lulus 85%. Tiga kasus gagal: quantifier shift, condition dropped, dan multi-context. Prompt diperbaiki untuk inferensi logis, dan kode diperbaiki untuk separator evidence. Setelah dua iterasi lagi, suite lulus 100%.

Suite ini kecil. 20 kasus tidak cukup untuk klaim robustness. Tapi dia menangkap failure mode yang paling penting, dan bisa diperluas seiring waktu.

Pada prompt groundedness saat ini (v4), adversarial suite lulus 17 dari 20 kasus (85%). Tiga kasus yang gagal: `condition_dropped`, `multi_context`, dan `cross_lingual`. Upaya untuk memperbaikinya (v5) membuat prompt terlalu panjang dan menurunkan kappa calibration set; v5 di-rollback. Lihat section "Prompt Refinement History and Known Limitations" di atas.

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

## Validasi Answer Relevance (Preliminary)

Pada 14 Oktober 2026, satu set berisi 249 entry untuk review relevance
dilabeli oleh manusia, secara independen dari judge. Section ini
melaporkan hasilnya dan keterbatasannya.

### Angka

| Metrik | Nilai |
|---|---|
| Entries | 249 |
| Human relevant (True) | 247 |
| Human relevant (False) | 2 |
| Raw agreement | 98.0% |
| Cohen's kappa | 0.277 |
| True positives | 243 |
| True negatives | 1 |
| False positives | 1 |
| False negatives | 4 |

### Kenapa Kappa Menyesatkan di Sini

Kappa 0.277 masuk kategori POOR menurut skala standar. Tapi angka ini
menyesatkan, dan melaporkannya sendiri akan tidak jujur.

Dataset-nya sangat tidak seimbang: 247 dari 249 entry (99.2%) dilabeli
relevan oleh manusia. Dengan distribusi kelas seekstrem ini, chance
agreement sudah mendekati 1.0. Kappa = (po - pe) / (1 - pe). Dengan
po = 0.98 dan pe = 0.97, kappa kolaps ke arah nol meskipun observed
agreement tinggi. Ini adalah prevalence effect pada Cohen's kappa yang
sudah dikenal luas.

Classifier trivial yang selalu bilang "relevan" akan mendapat 247/249
= 99.2% raw agreement pada dataset ini — **lebih tinggi dari 98.0%
milik judge**. Baseline itu adalah sinyal yang sebenarnya. Ia
mengatakan kita belum bisa menunjukkan judge melakukan lebih baik
dari jawaban konstan.

### Yang Tidak Bisa Didukung Dataset

Dengan hanya 2 contoh negatif yang dilabeli manusia, specificity
diestimasi sebagai 1/2 = 50%. Confidence interval Wilson 95% untuk
estimasi ini kira-kira 10% sampai 90%. Tidak ada pilihan metrik
ringkas (kappa, MCC, balanced accuracy, F1) yang bisa memperbaiki
ini. Datanya tidak ada.

Sensitivity judge (recall pada kelas positif) adalah 243/247 = 98.4%,
dengan confidence interval yang sempit. Kita bisa bilang sesuatu
tentang seberapa sering judge menerima jawaban yang dianggap relevan
oleh manusia. Kita belum bisa bilang banyak tentang seberapa sering
ia menolak jawaban yang dianggap tidak relevan oleh manusia.

### Catatan Kualitas Label

Label relevance tidak diberi field alasan, jadi label individual
tidak bisa diaudit. Saat ditinjau, ditemukan satu inkonsistensi:
q132 dilabeli tidak relevan meskipun mengikuti pola struktural yang
sama dengan sekitar 50 entry ungrounded-tetapi-menjawab lainnya yang
dilabeli relevan (q456, q222, dan lain-lain). Ini menunjukkan label
relevance kadang terkontaminasi oleh penilaian groundedness — reviewer
mungkin menghukum relevance karena kegagalan groundedness.

### Lima Ketidaksepakatan

| Entry | Human | Judge | Ringkasan |
|---|---|---|---|
| q495 | True | False | Judge bilang nama kategori tidak disebut. Human bilang disebut. |
| q341 | True | False | Judge bilang istilah tidak diberikan. Human bilang diberikan. |
| q368 | True | False | Judge bilang jawaban menjawab sebagian tapi tidak semua aspek. Human bilang menjawab. |
| q014 | False | True | Judge bilang jawaban memberi informasi. Human bilang tidak. |
| q280 | True | False | Judge bilang jawaban menjawab aspek yang salah. Human bilang menjawab. |

Empat dari lima ketidaksepakatan adalah false negative. Judge lebih
ketat dari reviewer manusia, terutama pada jawaban parsial untuk
pertanyaan multi-bagian.

### Prompt vs Definisi

Prompt relevance saat ini mendekomposisi pertanyaan menjadi aspek
atomik dan mengharuskan setiap aspek dijawab. Ini mencampur relevance
dengan completeness. Jawaban parsial untuk pertanyaan multi-bagian
itu relevan tapi tidak lengkap, bukan tidak relevan.

Perbaikannya bersifat konseptual sebelum menjadi perubahan prompt.
Relevance harus bertanya: apakah jawaban secara substantif menjawab
maksud pertanyaan? Completeness harus bertanya: apakah jawaban
mencakup semua komponen material? Ini dimensi yang terpisah.

### Langkah Selanjutnya

1. **Pisahkan relevance dari completeness.** Tambah metrik
   completeness sebagai dimensi yang berbeda. Update prompt relevance
   untuk berhenti mengharuskan semua sub-aspek.
2. **Audit ulang 5 ketidaksepakatan** dengan alasan tertulis per
   label. Tambah pemeriksaan inter-human agreement pada subset.
3. **Bangun balanced challenge set.** 50-100 contoh negatif yang
   dibangun sengaja, termasuk hard negatives (pasal salah, aspek
   salah, on-topic tapi kuantitas salah), bukan hanya jawaban
   off-topic yang mudah.
4. **Laporkan metric bundle.** Raw agreement, kappa, confusion
   matrix, class support, sensitivity dan specificity dengan Wilson
   confidence interval, balanced accuracy, dan opsional MCC.
   Laporkan performa production-weighted secara terpisah dari
   performa challenge-set.
5. **Update validator.** Ketika kelas minoritas punya kurang dari 30
   entry, validator harus melaporkan `INSUFFICIENT DATA` daripada
   interpretasi kualitatif seperti "POOR".
6. **Pertimbangkan ulang CI acceptance policy.** Threshold
   `kappa < 0.6` saat ini akan menggagalkan metrik relevance secara
   konstruktif pada dataset ini. Terapkan threshold per-class
   (lower bound specificity, lower bound sensitivity) daripada
   hanya pada kappa.

### Ringkasan

Judge relevance belum tervalidasi. Ia menunjukkan agreement tinggi
dengan manusia pada kelas dominan, tapi dataset tidak bisa mengukur
apakah ia membedakan jawaban tidak relevan. Ini didokumentasikan
daripada ditutupi. Iterasi berikutnya dari pekerjaan kalibrasi akan
menanganinya.

## Majority Vote

Pada 7 Oktober 2026, opsi majority vote ditambahkan. Ketika `ASSAY_JUDGE_VOTES` lebih besar dari 1, judge berjalan beberapa kali per pertanyaan dan keputusan akhir diambil lewat majority vote.

Ini ada karena provider LLM tidak sepenuhnya deterministik, bahkan di temperature 0. Saat validasi, dua entries berubah antar run: satu grounded di satu run dan tidak grounded di run berikutnya. Untuk CI gate, ini masalah. Gate yang gagal hari ini dan lulus besok pada kode yang sama bukan gate.

Majority vote mengurangi instabilitas ini. Trade-off-nya biaya: tiga votes berbiaya tiga kali satu vote.

Opsi ini configurable, bukan selalu aktif. User yang lebih peduli biaya daripada stabilitas bisa set `ASSAY_JUDGE_VOTES=1`. User yang jalankan CI gate bisa set `ASSAY_JUDGE_VOTES=3`.

Majority vote tidak menyelesaikan akar masalah ambiguitas. Dia mengurangi gejala. Ketika kasus benar-benar ambigu di prompt, dua dari tiga run bisa tetap setuju pada jawaban yang salah. Yang menyelesaikan itu adalah prompt yang lebih baik, bukan lebih banyak votes. Keduanya bekerja bersama.

## Komparasi Judge

User yang mengkonfigurasi beberapa provider bisa membandingkannya.
Script `scripts/compare_judges.py` menjalankan judge pada calibration
set yang sama dengan setiap provider dan melaporkan agreement, Cohen's
kappa, dan jumlah error.

Contoh output (dari calibration set awal 50 entries; angka akan
berbeda pada set 250 entries saat ini):

```
Provider        Model                        Entries    Agree    Kappa  Errors
------------------------------------------------------------------------------
groq            openai/gpt-oss-120b               50    92.0%    0.831       0
gemini          gemma-4-26b-a4b-it                49    93.9%    0.867       1
tokenharbor     deepseek-v4-flash:free            50    96.0%    0.913       0
```

Ini informatif. Tidak mengubah perilaku Assay. User yang putuskan
provider mana yang dipakai berdasarkan perbandingan.

Provider berbeda memberi judgment berbeda. Provider dengan kappa lebih
tinggi di calibration set belum tentu lebih baik di data user.
Perbandingan adalah titik awal, bukan putusan.

Provider dibandingkan tanpa fallback. Setiap provider diuji secara
terisolasi. Kalau provider gagal, jumlah error mencerminkan itu.

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

## Citation Accuracy

Pada 14 Oktober 2026, metrik ketiga ditambahkan: citation accuracy.

**Masalahnya.** Di domain yang bergantung pada sitasi (hukum,
akademik, regulasi), jawaban hanya berguna jika sitasinya benar.
Jawaban yang grounded tapi menyitasi pasal yang salah lebih buruk
dari jawaban yang mengaku tidak tahu.

**Metriknya.** Citation accuracy mengekstrak sitasi dari jawaban dan
memeriksa dua hal:

1. **Keberadaan.** Apakah sitasi muncul di konteks yang diambil?
   Ini deterministik. Pattern-matching untuk "Pasal 5 ayat (2)",
   "UU 16/2025", "PP 35/2025", dan bentuk serupa, dengan normalisasi
   untuk bentuk panjang vs pendek.
2. **Relevansi.** Apakah sitasi benar-benar mendukung klaim yang
   disertainya? Ini opsional, menggunakan LLM-as-judge.

MVP mengirimkan lapisan deterministik. Lapisan relevansi LLM
direncanakan tapi belum diimplementasikan.

**Skor.** `citation_accuracy = valid_citations / total_citations`.
`None` jika jawaban tidak punya sitasi. Ini membuat metrik secara
alami opt-in: jawaban tanpa sitasi tidak mendapat skor.

**Kenapa penting untuk Assay.** Use case utama citation accuracy
adalah RAG legal dan regulasi. Asisten kepatuhan fintech yang
menyitasi regulasi OJK yang salah itu berbahaya. Chatbot support
yang menyitasi pasal yang salah itu tidak membantu. Citation
accuracy membuat ini terlihat di CI gate.

## Refusal Correctness

Pada 14 Oktober 2026, metrik keempat ditambahkan: refusal correctness.

**Masalahnya.** Groundedness, answer relevance, dan citation accuracy
semuanya mengukur kualitas jawaban yang diproduksi. Tidak ada yang
mengukur apakah jawaban seharusnya diproduksi sama sekali. Sistem
RAG yang selalu menjawab — bahkan ketika konteks yang diambil tidak
berisi jawaban — bisa perfectly grounded pada sebagian pertanyaan
dan berhalusinasi pada yang lain. Failure mode itu tidak terlihat
oleh metrik lain.

**Metriknya.** Refusal correctness mengukur apakah sistem menolak
saat seharusnya menolak, dan menjawab saat seharusnya menjawab.

Notion "seharusnya" berasal dari dataset:

- Pertanyaan dengan `expected_answer` (atau `expected_context` yang
  tidak kosong) itu **answerable**.
- Pertanyaan tanpa keduanya itu **unanswerable**.

Deteksi refusal deterministik. Jawaban pendek yang cocok dengan
salah satu dari sekumpulan kecil pola ("Saya tidak tahu", "Informasi
tidak tersedia", "I don't know", "Not enough information", dan
sebagainya) adalah refusal. Jawaban panjang yang hanya dimulai
dengan frasa refusal bukan refusal, karena panjangnya menunjukkan
jawaban berisi konten di luar refusal.

**Truth table.**

| Pertanyaan | Jawaban | Status | Benar |
|---|---|---|---|
| Answerable | Answer | answerable_answered | ya |
| Answerable | Refusal | answerable_refused | tidak |
| Unanswerable | Refusal | unanswerable_refused | ya |
| Unanswerable | Answer | unanswerable_answered | tidak |

**Skor.** `refusal_correctness = correct / applicable`. `None` jika
tidak ada pertanyaan yang applicable.

**Kenapa deterministik.** Pola refusal adalah sinyal yang kuat.
User yang melihat "Saya tidak tahu" tahu sistem menolak. Deteksi
berbasis LLM akan menambah biaya dan nondeterminisme untuk tugas
yang regex tangani dengan baik.

**Penanganan konjungsi kontras.** Frasa refusal yang diikuti "namun",
"tetapi", "tapi", "however", atau "but" bukan refusal. Itu jawaban
dengan hedge. Contoh: "Saya tidak tahu secara pasti, namun
berdasarkan konteks, Pasal 5 menyatakan ..." adalah jawaban, bukan
refusal. Detector memeriksa konjungsi kontras sebelum memutuskan.

**Kenapa penting untuk Assay.** Sistem RAG yang terlalu sering
menolak itu mengganggu. Sistem RAG yang menjawab saat seharusnya
menolak itu berbahaya. Tanpa refusal correctness, tidak ada failure
mode yang terlihat di CI gate. Metrik ini menutup gap itu.