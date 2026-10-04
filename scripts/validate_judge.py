"""Validate the LLM-as-judge against a human-labeled calibration set.

Usage:
    python scripts/validate_judge.py examples/calibration_set.json

The script runs the judge on each entry, compares the judge's label
with the human label, and computes agreement metrics.

Output:
    - Confusion matrix
    - Raw agreement
    - Cohen's kappa
    - List of disagreements
"""

import argparse
import json
from pathlib import Path

from assay.core.metrics.judge import JudgeError, judge_groundedness


def cohen_kappa(tp: int, tn: int, fp: int, fn: int) -> float:
    """Compute Cohen's kappa for binary classification."""
    total = tp + tn + fp + fn
    if total == 0:
        return 0.0
    po = (tp + tn) / total  # observed agreement
    p_yes = (tp + fp) / total  # predicted positive rate
    p_no = (tn + fn) / total  # predicted negative rate
    p_human_yes = (tp + fn) / total
    p_human_no = (tn + fp) / total
    pe = (p_yes * p_human_yes) + (p_no * p_human_no)  # expected agreement
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


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

    tp = tn = fp = fn = 0
    skipped = 0
    disagreements = []

    for i, entry in enumerate(entries):
        human = entry.get("human_grounded")
        if human is None:
            skipped += 1
            continue

        try:
            result = judge_groundedness(
                question=entry["question"],
                answer=entry["answer"],
                contexts=entry["contexts"],
            )
            judge = result.grounded
        except JudgeError as e:
            print(f"Entry {i + 1}: judge failed ({e})")
            skipped += 1
            continue

        if human and judge:
            tp += 1
        elif not human and not judge:
            tn += 1
        elif not human and judge:
            fp += 1
        elif human and not judge:
            fn += 1

        if human != judge:
            disagreements.append({
                "index": i + 1,
                "human": human,
                "judge": judge,
                "reason": result.reason[:100],
            })

    total = tp + tn + fp + fn
    if total == 0:
        raise SystemExit("No entries were evaluated")

    agreement = (tp + tn) / total
    kappa = cohen_kappa(tp, tn, fp, fn)

    print("=" * 60)
    print("Judge Validation Report")
    print("=" * 60)
    print()
    print(f"Entries evaluated: {total}")
    print(f"Skipped:           {skipped}")
    print()
    print("Confusion Matrix:")
    print(f"  True Positive  (human=true,  judge=true):  {tp}")
    print(f"  True Negative  (human=false, judge=false): {tn}")
    print(f"  False Positive (human=false, judge=true):  {fp}")
    print(f"  False Negative (human=true,  judge=false): {fn}")
    print()
    print(f"Raw agreement: {agreement * 100:.1f}%")
    print(f"Cohen's kappa: {kappa:.3f}")
    print()
    if kappa < 0.4:
        print("Interpretation: POOR. Judge is not reliable.")
    elif kappa < 0.6:
        print("Interpretation: MODERATE. Judge needs improvement.")
    elif kappa < 0.8:
        print("Interpretation: GOOD. Judge is reliable.")
    else:
        print("Interpretation: EXCELLENT. Judge is highly reliable.")
    print()

    if disagreements:
        print("Disagreements:")
        for d in disagreements:
            print(f"  Entry {d['index']}: human={d['human']}, judge={d['judge']}")
            print(f"    Judge reason: {d['reason']}")
        print()
    else:
        print("No disagreements. Judge matches human labels perfectly.")


if __name__ == "__main__":
    main()
