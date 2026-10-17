"""Test judge consistency across multiple runs.

Usage:
    python scripts/test_consistency.py examples/calibration_set_reviewed.json --runs 5
    python scripts/test_consistency.py examples/relevance_set_reviewed.json --runs 5

The script runs the judge multiple times on the same entries and computes
the Intraclass Correlation Coefficient (ICC(2,k)) to measure stability.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from assay.core.metrics.judge import (
    JudgeError,
    judge_answer_relevance,
    judge_groundedness,
)


def icc_2k(data: np.ndarray) -> float:
    """Compute ICC(2,k) for a 2D array (rows=subjects, cols=raters).

    ICC(2,k) measures the reliability of the average of k raters,
    assuming raters are a random sample. Used here to measure how
    consistent the judge is across repeated runs.
    """
    n, k = data.shape
    if n < 2 or k < 2:
        return 0.0

    grand_mean = data.mean()
    row_means = data.mean(axis=1)
    col_means = data.mean(axis=0)

    # Sum of squares
    ss_total = ((data - grand_mean) ** 2).sum()
    ss_rows = k * ((row_means - grand_mean) ** 2).sum()
    ss_cols = n * ((col_means - grand_mean) ** 2).sum()
    ss_error = ss_total - ss_rows - ss_cols

    # Mean squares
    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    # ICC(2,k) formula
    # If there is no variance at all (all values identical), ICC is 1.0
    if ss_total == 0:
        return 1.0

    denominator = ms_rows + (ms_cols - ms_error) / n
    if denominator == 0:
        return 1.0  # Perfect consistency if denominator is zero
    return (ms_rows - ms_error) / denominator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", help="Dataset JSON file (with human labels)")
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of runs (default: 5).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only evaluate the first N entries.",
    )
    parser.add_argument(
        "--metric",
        choices=["groundedness", "relevance"],
        default="groundedness",
        help="Which metric to test.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Timeout per call in seconds.",
    )
    args = parser.parse_args()

    # Override timeout
    from assay.config import settings
    if settings.judge_providers:
        for p in settings.judge_providers:
            p.timeout = args.timeout

    path = Path(args.dataset)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        raise SystemExit("Dataset has no entries")

    if args.limit is not None:
        entries = entries[: args.limit]

    n = len(entries)
    runs = args.runs

    # Matrix: rows = entries, cols = runs
    results = np.zeros((n, runs))
    skipped = 0

    print(f"Testing {args.metric} consistency across {runs} runs on {n} entries.")
    print(f"Timeout per call: {args.timeout}s")
    print()

    start_time = time.monotonic()

    for run_idx in range(runs):
        print(f"=== Run {run_idx + 1}/{runs} ===")
        for i, entry in enumerate(entries):
            eid = entry.get("id", "?")
            try:
                if args.metric == "groundedness":
                    res = judge_groundedness(
                        question=entry["question"],
                        answer=entry["answer"],
                        contexts=entry.get("contexts", []),
                    )
                    results[i, run_idx] = 1.0 if res.grounded else 0.0
                else:
                    res = judge_answer_relevance(
                        question=entry["question"],
                        answer=entry["answer"],
                    )
                    results[i, run_idx] = 1.0 if res.relevant else 0.0
            except JudgeError as e:
                print(f"  [{i+1}/{n}] {eid}: ERROR - {e}")
                results[i, run_idx] = np.nan
                skipped += 1
                continue

            elapsed = time.monotonic() - start_time
            avg = elapsed / ((run_idx * n) + i + 1)
            print(f"  [{i+1}/{n}] {eid}: {results[i, run_idx]:.0f} ({avg:.1f}s/entry)", flush=True)
        print()

    # Handle NaN (skip entries that errored in any run)
    valid_mask = ~np.isnan(results).any(axis=1)
    valid_results = results[valid_mask]
    if len(valid_results) < 2:
        raise SystemExit("Not enough valid entries to compute ICC")

    icc_value = icc_2k(valid_results)

    # Agreement: fraction of entries where all runs agree
    agreement = np.mean(
        [len(set(row)) == 1 for row in valid_results]
    )

    print("=" * 60)
    print("Consistency Report")
    print("=" * 60)
    print()
    print(f"Entries evaluated: {len(valid_results)}")
    print(f"Skipped (error):   {skipped}")
    print(f"Runs per entry:    {runs}")
    print()
    print(f"All-runs agreement: {agreement * 100:.1f}%")
    print(f"ICC(2,{runs}):          {icc_value:.3f}")
    print()

    if icc_value < 0.5:
        print("Interpretation: POOR. Judge is not consistent.")
    elif icc_value < 0.75:
        print("Interpretation: MODERATE. Judge needs improvement.")
    elif icc_value < 0.9:
        print("Interpretation: GOOD. Judge is consistent.")
    else:
        print("Interpretation: EXCELLENT. Judge is highly consistent.")
    print()


if __name__ == "__main__":
    main()
