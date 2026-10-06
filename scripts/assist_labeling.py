"""Run the judge on a calibration set and add predicted labels.

This script does not replace human labeling. It adds a `judge_predicted`
field to each entry so a human can review and accept or correct it.

Usage:
    python scripts/assist_labeling.py examples/calibration_set_v2.json
"""

import argparse
import json
from pathlib import Path

from assay.core.metrics.judge import JudgeError, judge_groundedness


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Calibration set JSON file")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        raise SystemExit("No entries")

    print(f"Running judge on {len(entries)} entries...")
    print()

    total = 0
    errors = 0

    for i, entry in enumerate(entries):
        try:
            result = judge_groundedness(
                question=entry["question"],
                answer=entry["answer"],
                contexts=entry["contexts"],
            )
            entry["judge_predicted_grounded"] = result.grounded
            entry["judge_predicted_score"] = result.score
            entry["judge_predicted_abstained"] = result.abstained
            entry["judge_predicted_reason"] = result.reason
            entry["judge_predicted_claims"] = [
                {"text": c.text, "verdict": c.verdict, "evidence": c.evidence}
                for c in result.claims
            ]
            status = "grounded" if result.grounded else "not grounded"
            print(f"[{i + 1}/{len(entries)}] {entry.get('id', i)}: {status} (score={result.score:.2f})")
            total += 1
        except JudgeError as e:
            print(f"[{i + 1}/{len(entries)}] {entry.get('id', i)}: ERROR - {e}")
            entry["judge_predicted_grounded"] = None
            entry["judge_predicted_reason"] = f"ERROR: {e}"
            errors += 1

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 60)
    print(f"Total: {total + errors}")
    print(f"Success: {total}")
    print(f"Errors: {errors}")
    print()
    print(f"Updated: {path}")
    print()
    print("Next: review judge_predicted_grounded and fill human_grounded.")


if __name__ == "__main__":
    main()
