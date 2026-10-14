# ADR-006: Judge is Domain-Specific, Framework is Universal

**Status:** Accepted
**Date:** 13 October 2026
**Author:** Gigih Susetyo

## Context

Assay is a CI gate for RAG quality regressions. It measures
groundedness, answer relevance, and other metrics, and fails the build
when quality drops beyond a policy.

At the core of Assay is an LLM-as-judge. The judge reads a question,
an answer, and the retrieved contexts, and decides whether the answer
is grounded.

During the development of Assay, we calibrated the judge on a dataset
of Indonesian legal documents. The calibration set was expanded from
50 to 250 entries, manually reviewed, and validated with Cohen's kappa.

This raised a question: is the judge calibrated for legal Indonesia
also valid for other domains? Or does each domain require its own
calibration?

The answer determines how Assay is positioned, how it is documented,
and how it is sold.

## Decision

**The framework is universal. The judge is domain-specific.**

Specifically:

1. **The Assay framework** (CLI, API, database, comparison engine,
   regression policy, reports, exit codes) is universal. It does not
   depend on the domain. Any team can use it for any RAG system.

2. **The metrics** (groundedness, answer relevance, context recall,
   latency, cost) are universal by definition. "Is the answer
   supported by the context?" is the same question in every domain.

3. **The LLM-as-judge** is domain-specific. A judge calibrated for
   legal Indonesia may not be reliable for medical, financial, or
   technical content. The qualifiers that matter in one domain may
   not matter in another.

4. **Calibration is required per domain.** Before using the judge in
   a CI gate, the team must verify the judge against human-labeled
   entries from their own domain. The reported Cohen's kappa is the
   measure of trust.

5. **One Assay instance can serve many datasets in one domain.**
   Multiple domains require multiple calibrations. The framework
   supports this; the calibration set is a first-class artifact.

## Consequences

### What is gained

- **Honest positioning.** We do not claim the judge works everywhere.
  We claim the framework works everywhere, and the judge works where
  it has been calibrated.

- **Clear onboarding.** Users know what to do: bring a dataset,
  calibrate the judge, then use the gate. The documentation explains
  the three steps.

- **Extensibility.** Adding a new domain means adding a calibration
  set, not forking the framework. The framework stays stable.

- **Trust through evidence.** The kappa is not a marketing number. It
  is a measured agreement between the judge and human labels. Users
  can reproduce it.

### What is sacrificed

- **No out-of-the-box judge.** Users must calibrate. This is friction.
  But it is honest friction. A judge without calibration is a guess.

- **No single universal calibration.** There is no "one calibration
  set to rule them all." Each domain needs its own.

- **Calibration cost.** Manual review of 100-250 entries takes time.
  The toolkit (split, review, parse, validate) reduces the cost, but
  it is not zero.

## Alternatives Considered

### Alternative 1: Claim the judge is universal

Rejected. The evidence does not support it. A judge calibrated on
legal documents will be less reliable on medical content, where the
material qualifiers are different (dosage, contraindications, drug
interactions).

### Alternative 2: Ship a universal calibration set

Rejected. There is no universal domain. Even a multi-domain calibration
set would be an average that fits no domain well.

### Alternative 3: Make calibration optional

Rejected. A CI gate that fails builds based on an uncalibrated judge
is worse than no gate. It gives false confidence.

## Implications

### For documentation

The README and docs must clearly state:

- Assay ships with a legal Indonesia calibration set as a reference.
- For other domains, users bring their own calibration set.
- The toolkit (`review_split_txt.py`, `review_parse_txt.py`,
  `validate_judge.py`) is provided to build one.

### For the roadmap

- **Phase 1:** Legal Indonesia calibration set (250 entries, kappa
  measured). Done.
- **Phase 2:** Additional domains (medical, technical, financial)
  with their own calibration sets. Each domain is an independent
  contribution.
- **Phase 3:** Calibration as a service. Users upload a dataset, get
  a calibrated judge. This is a candidate for the Pro tier.

### For positioning

Assay is not a "RAG evaluation tool." It is a **CI gate framework with
a calibratable judge**. The framework is the product. The judge is the
plugin. The calibration is the trust layer.

## The Three Steps of Assay

1. **Prepare a dataset.** Questions, expected answers, expected
   contexts. From your own RAG system.

2. **Calibrate the judge.** Manually label 100-250 entries. Measure
   kappa. If kappa is below the threshold (0.6 by default), fix the
   prompt or the model. If kappa is acceptable, proceed.

3. **Gate the RAG.** Pin a baseline. On every change, run Assay.
   If quality regresses beyond policy, fail the build.

The framework handles steps 1 and 3. Step 2 is the calibration, and
it is domain-specific.

## References

- ADR-004: LLM-as-Judge with Bring Your Own Key
- `docs/calibration_set.md`
- `review/PANDUAN.txt`
- `scripts/validate_judge.py`
