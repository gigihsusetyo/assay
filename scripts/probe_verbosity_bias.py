"""Probe verbosity bias in the LLM-as-judge.

Verbosity bias is when the judge gives higher scores to longer answers,
even when the content is the same or padded with irrelevant text.

This script takes a calibration set. For each entry, it creates a
padded version of the answer by appending text from the context or
generic filler. Then it runs the judge on both versions and compares.

If the padded version scores significantly higher, the judge has
verbosity bias.

Usage:
    python scripts/probe_verbosity_bias.py examples/calibration_set.json
"""

import argparse
import json
from pathlib import Path

from assay.core.metrics.judge import JudgeError, judge_groundedness


def make_padded_answer(answer: str, contexts: list[str]) -> str:
    """Create a longer version of the answer that is still grounded.

    The padded version appends relevant text from the contexts. This way,
    both the original and the padded answer should be grounded. If the
    judge scores the padded version higher, it has verbosity bias.
    """
    # Take the first context and append part of it to the answer
    if not contexts:
        return answer
    context_text = contexts[0]
    # Take up to 200 characters from the context
    snippet = context_text[:200].strip()
    if snippet and snippet not in answer:
        return f"{answer} {snippet}"
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calibration_set", help="Calibration set JSON file")
    args = parser.parse_args()

    path = Path(args.calibration_set)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        raise SystemExit("Calibration set has no entries")

    print("=" * 60)
    print("Verbosity Bias Probe")
    print("=" * 60)
    print()

    total = 0
    flips = 0
    skipped = 0
    score_diffs: list[float] = []

    for i, entry in enumerate(entries):
        question = entry["question"]
        answer = entry["answer"]
        contexts = entry.get("contexts", [])

        if not answer:
            skipped += 1
            continue

        # Original answer
        try:
            original = judge_groundedness(question, answer, contexts)
        except JudgeError as e:
            print(f"Entry {i + 1}: judge failed on original ({e})")
            skipped += 1
            continue

        # Padded answer: same content + relevant text from context
        padded_answer = make_padded_answer(answer, contexts)
        try:
            padded = judge_groundedness(question, padded_answer, contexts)
        except JudgeError as e:
            print(f"Entry {i + 1}: judge failed on padded ({e})")
            skipped += 1
            continue

        total += 1
        original_label = original.score >= 0.5
        padded_label = padded.score >= 0.5
        diff = padded.score - original.score
        score_diffs.append(diff)

        if original_label != padded_label:
            flips += 1
            print(f"Entry {i + 1}: FLIP")
            print(f"  Original: score={original.score:.2f}")
            print(f"  Padded:   score={padded.score:.2f}")
            print()

    print("=" * 60)
    print(f"Entries evaluated: {total}")
    print(f"Skipped: {skipped}")
    print(f"Flips: {flips}")
    if total > 0:
        flip_rate = flips / total * 100
        avg_diff = sum(score_diffs) / len(score_diffs)
        print(f"Flip rate: {flip_rate:.1f}%")
        print(f"Average score diff (padded - original): {avg_diff:+.3f}")
        if flip_rate == 0 and abs(avg_diff) < 0.1:
            print("Interpretation: NO VERBOSITY BIAS DETECTED")
        elif flip_rate < 10:
            print("Interpretation: MINOR VERBOSITY BIAS")
        elif flip_rate < 25:
            print("Interpretation: MODERATE VERBOSITY BIAS")
        else:
            print("Interpretation: SEVERE VERBOSITY BIAS")


if __name__ == "__main__":
    main()
