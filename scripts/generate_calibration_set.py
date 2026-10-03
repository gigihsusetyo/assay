"""Generate calibration set template from a dataset.

This script takes questions from an existing dataset and creates a
calibration set template. The human_grounded and human_reason fields
are left empty for manual labeling.

Usage:
    python scripts/generate_calibration_set.py \
        examples/datasets/indonesian-legal-rag.json \
        examples/calibration_set.json \
        --limit 50
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input dataset JSON file")
    parser.add_argument("output", help="Output calibration set JSON file")
    parser.add_argument("--limit", type=int, default=50, help="Max entries")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    with input_path.open(encoding="utf-8") as f:
        dataset = json.load(f)

    questions = dataset.get("questions", [])
    if not questions:
        raise SystemExit("Dataset has no questions")

    entries = []
    for q in questions[: args.limit]:
        entries.append({
            "question": q["question"],
            "answer": q.get("expected_answer", ""),
            "contexts": [q.get("expected_context", "")],
            "human_grounded": None,
            "human_reason": "",
            "metadata": {
                "source": dataset.get("name", "unknown"),
                "date": "2026-10-04",
            },
        })

    output = {
        "version": "1.0.0",
        "description": "Calibration set for Assay LLM-as-judge validation",
        "entries": entries,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Written {len(entries)} entries to {output_path}")
    print("Next: fill in human_grounded and human_reason manually.")


if __name__ == "__main__":
    main()
