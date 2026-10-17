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
import math
import time
from pathlib import Path

from assay.core.metrics.judge import JudgeError, judge_groundedness

# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if total == 0:
        return 0.0, 1.0
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = (
        z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def balanced_accuracy(tp: int, tn: int, fp: int, fn: int) -> float | None:
    """Average of sensitivity and specificity. None if a class is empty."""
    pos = tp + fn
    neg = tn + fp
    if pos == 0 or neg == 0:
        return None
    return ((tp / pos) + (tn / neg)) / 2


def mcc(tp: int, tn: int, fp: int, fn: int) -> float:
    """Matthews correlation coefficient."""
    numerator = (tp * tn) - (fp * fn)
    denom_sq = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    if denom_sq == 0:
        return 0.0
    return numerator / math.sqrt(denom_sq)


def majority_baseline(tp: int, tn: int, fp: int, fn: int) -> float:
    """Raw agreement of a classifier that always predicts the majority class."""
    total = tp + tn + fp + fn
    if total == 0:
        return 0.0
    return max(tp + fn, tn + fp) / total


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
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only evaluate the first N entries (for quick testing).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable per-entry progress output.",
    )
    parser.add_argument(
        "--min-minority",
        type=int,
        default=30,
        help="Minimum size for the minority class before reporting per-class "
        "metrics. Below this, the class is reported as INSUFFICIENT DATA.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Timeout per entry in seconds (default: 15.0).",
    )
    args = parser.parse_args()

    # Override settings timeout if provided
    from assay.config import settings
    if settings.judge_providers:
        for p in settings.judge_providers:
            p.timeout = args.timeout

    path = Path(args.calibration_set)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        raise SystemExit("Calibration set has no entries")

    if args.limit is not None:
        entries = entries[: args.limit]

    tp = tn = fp = fn = 0
    skipped = 0
    disagreements = []

    total = len(entries)
    start_time = time.monotonic()

    for i, entry in enumerate(entries):
        human = entry.get("human_grounded")
        if human is None:
            skipped += 1
            continue

        try:
            entry_start = time.monotonic()
            result = judge_groundedness(
                question=entry["question"],
                answer=entry["answer"],
                contexts=entry["contexts"],
            )
            judge = result.grounded
            entry_elapsed = time.monotonic() - entry_start
        except JudgeError as e:
            print(f"Entry {i + 1}: judge failed ({e})", flush=True)
            skipped += 1
            continue

        if not args.no_progress:
            elapsed = time.monotonic() - start_time
            avg = elapsed / (i + 1)
            remaining = avg * (total - i - 1)
            eta_str = f"{int(remaining // 60)}m {int(remaining % 60)}s" if remaining > 60 else f"{int(remaining)}s"
            print(
                f"[{i + 1}/{total}] {entry.get('id', '?')}: "
                f"human={human} judge={judge} "
                f"({entry_elapsed:.1f}s, avg {avg:.1f}s, ETA {eta_str})",
                flush=True,
            )

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
                "id": entry.get("id", "?"),
                "human": human,
                "judge": judge,
                "reason": result.reason[:100],
            })

    total = tp + tn + fp + fn
    if total == 0:
        raise SystemExit("No entries were evaluated")

    agreement = (tp + tn) / total
    kappa = cohen_kappa(tp, tn, fp, fn)
    baseline = majority_baseline(tp, tn, fp, fn)

    pos = tp + fn
    neg = tn + fp

    sensitivity = tp / pos if pos > 0 else None
    specificity = tn / neg if neg > 0 else None

    sens_ci = wilson_ci(tp, pos) if pos > 0 else None
    spec_ci = wilson_ci(tn, neg) if neg > 0 else None

    bal_acc = balanced_accuracy(tp, tn, fp, fn)
    mcc_value = mcc(tp, tn, fp, fn)

    insufficient_pos = pos < args.min_minority
    insufficient_neg = neg < args.min_minority

    print("=" * 60)
    print("Groundedness Judge Validation Report")
    print("=" * 60)
    print()
    print(f"Entries evaluated: {total}")
    print(f"Skipped:           {skipped}")
    print()
    print("Class distribution (human labels):")
    print(f"  Positive (grounded):     {pos}")
    print(f"  Negative (not grounded): {neg}")
    if insufficient_pos:
        print(
            f"  NOTE: positive class has fewer than {args.min_minority} "
            "entries. Metrics that depend on this class are unreliable."
        )
    if insufficient_neg:
        print(
            f"  NOTE: negative class has fewer than {args.min_minority} "
            "entries. Metrics that depend on this class are unreliable."
        )
    print()
    print("Confusion Matrix:")
    print(f"  True Positive  (human=true,  judge=true):  {tp}")
    print(f"  True Negative  (human=false, judge=false): {tn}")
    print(f"  False Positive (human=false, judge=true):  {fp}")
    print(f"  False Negative (human=true,  judge=false): {fn}")
    print()
    print("Metric bundle:")
    print(f"  Raw agreement:              {agreement * 100:.1f}%")
    print(f"  Majority-class baseline:    {baseline * 100:.1f}%")
    print(f"  Cohen's kappa:              {kappa:.3f}")
    if bal_acc is not None:
        print(f"  Balanced accuracy:          {bal_acc * 100:.1f}%")
    else:
        print("  Balanced accuracy:          N/A (one class is empty)")
    print(f"  MCC:                        {mcc_value:.3f}")
    print()

    print("Per-class recall:")
    if sensitivity is not None and sens_ci is not None:
        lo, hi = sens_ci
        label = "INSUFFICIENT DATA" if insufficient_pos else "ok"
        print(
            f"  Sensitivity (recall on grounded):     "
            f"{sensitivity * 100:.1f}%  (95% Wilson CI: {lo * 100:.1f}% - {hi * 100:.1f}%)  [{label}]"
        )
    else:
        print("  Sensitivity: N/A")
    if specificity is not None and spec_ci is not None:
        lo, hi = spec_ci
        label = "INSUFFICIENT DATA" if insufficient_neg else "ok"
        print(
            f"  Specificity (recall on not grounded): "
            f"{specificity * 100:.1f}%  (95% Wilson CI: {lo * 100:.1f}% - {hi * 100:.1f}%)  [{label}]"
        )
    else:
        print("  Specificity: N/A")
    print()

    print("Interpretation:")
    if insufficient_pos or insufficient_neg:
        print(
            "  INSUFFICIENT DATA. One class has fewer than "
            f"{args.min_minority} entries. The per-class metrics above "
            "cannot be used to claim reliable discrimination."
        )
    else:
        if kappa < 0.4:
            print("  Kappa: POOR. Judge is not reliable.")
        elif kappa < 0.6:
            print("  Kappa: MODERATE. Judge needs improvement.")
        elif kappa < 0.8:
            print("  Kappa: GOOD. Judge is reliable.")
        else:
            print("  Kappa: EXCELLENT. Judge is highly reliable.")
    print()

    if disagreements:
        print(f"Disagreements ({len(disagreements)}):")
        for d in disagreements:
            print(f"  Entry {d['index']} ({d['id']}): human={d['human']}, judge={d['judge']}")
            if d["reason"]:
                print(f"    reason: {d['reason']}")
        print()
    else:
        print("No disagreements. Judge matches human labels perfectly.")


if __name__ == "__main__":
    main()
