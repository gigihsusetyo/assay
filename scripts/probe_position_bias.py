"""Probe position bias in the LLM-as-judge.

Position bias is when the judge's score changes based on the order of
the contexts, even though the content is the same.

This script takes a calibration set, runs the judge twice for each entry:
once with the original context order, once with the order reversed.
Then it compares the scores.

If the scores differ significantly, the judge has position bias.

Usage:
    python scripts/probe_position_bias.py examples/calibration_set.json
"""

import argparse
import json
from pathlib import Path

from assay.core.metrics.judge import JudgeError, judge_groundedness


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
    print("Position Bias Probe")
    print("=" * 60)
    print()

    total = 0
    flips = 0
    skipped = 0

    for i, entry in enumerate(entries):
        contexts = entry.get("contexts", [])
        if len(contexts) < 2:
            # Cannot reverse single context
            skipped += 1
            continue

        question = entry["question"]
        answer = entry["answer"]

        # Original order
        try:
            original = judge_groundedness(question, answer, contexts)
        except JudgeError as e:
            print(f"Entry {i + 1}: judge failed on original ({e})")
            skipped += 1
            continue

        # Reversed order
        reversed_contexts = list(reversed(contexts))
        try:
            reversed_result = judge_groundedness(question, answer, reversed_contexts)
        except JudgeError as e:
            print(f"Entry {i + 1}: judge failed on reversed ({e})")
            skipped += 1
            continue

        total += 1
        original_label = original.grounded
        reversed_label = reversed_result.grounded

        if original_label != reversed_label:
            flips += 1
            print(f"Entry {i + 1}: FLIP")
            print(f"  Original order: score={original.score:.2f}")
            print(f"  Reversed order: score={reversed_result.score:.2f}")
            print(f"  Original reason: {original.reason[:100]}")
            print(f"  Reversed reason: {reversed_result.reason[:100]}")
            print()

    print("=" * 60)
    print(f"Entries evaluated: {total}")
    print(f"Skipped: {skipped}")
    print(f"Flips: {flips}")
    if total > 0:
        flip_rate = flips / total * 100
        print(f"Flip rate: {flip_rate:.1f}%")
        if flip_rate == 0:
            print("Interpretation: NO POSITION BIAS DETECTED")
        elif flip_rate < 10:
            print("Interpretation: MINOR POSITION BIAS")
        elif flip_rate < 25:
            print("Interpretation: MODERATE POSITION BIAS")
        else:
            print("Interpretation: SEVERE POSITION BIAS")


if __name__ == "__main__":
    main()
