# Calibration Set

A calibration set is a small collection of questions with human-labeled
ground truth. It is used to validate whether the LLM-as-judge is reliable.

## Why It Exists

Assay uses an LLM to judge whether an answer is grounded in the retrieved
contexts. But an LLM is not automatically reliable. Different models give
different judgments. The same model can drift over time.

Before we trust the judge, we need to measure it. The calibration set is
how we measure.

## What It Is Not

The calibration set is not a production evaluation dataset. It is small
on purpose. Production runs can have thousands of questions. The
calibration set has around 50.

The calibration set is not a benchmark for the RAG system. It is a
benchmark for the judge.

## Format

The calibration set is a JSON file. Each entry has:

- `question`: the question text.
- `answer`: the answer from the RAG system.
- `contexts`: the retrieved contexts.
- `human_grounded`: the human label. `true` if every claim in the answer
  is supported by the contexts. `false` otherwise.
- `human_reason`: a short note explaining the label.
- `metadata`: optional. Source, date, etc.

Example:

```json
{
  "version": "1.0.0",
  "description": "Calibration set for Assay LLM-as-judge validation",
  "entries": [
    {
      "question": "What is the capital of France?",
      "answer": "Paris is the capital of France.",
      "contexts": [
        "Paris is the capital and largest city of France."
      ],
      "human_grounded": true,
      "human_reason": "Context directly states Paris is the capital.",
      "metadata": {
        "source": "manual",
        "date": "2026-10-04"
      }
    }
  ]
}
```

## How to Label

1. Read the question.
2. Read the answer.
3. Read the contexts.
4. Ask: is every claim in the answer supported by the contexts?
   - If yes, `human_grounded: true`.
   - If no, `human_grounded: false`.
5. Write a short reason. One sentence is enough.
6. Do not use outside knowledge. Only the contexts matter.
7. If the answer says "I do not have enough information" and the
   contexts do not contain the answer, that is grounded (the system
   correctly refused).

## How to Use

Run the validation script:

```bash
python scripts/validate_judge.py examples/calibration_set.json
```

The script will:

1. Run the judge on each entry.
2. Compare judge labels with human labels.
3. Compute Cohen's kappa.
4. Report agreement, confusion matrix, and disagreements.

If Cohen's kappa is below 0.6, the judge is not reliable. Consider
changing the model or the prompt.

## Maintenance

Re-validate the judge:

- When you change the judge model.
- When the judge provider updates the model.
- Every 3 to 6 months, to detect drift.

You do not need to re-label the calibration set. It stays the same.
You only re-run the validation.
```

---

## Langkah 2: Generate 50 Pertanyaan

Script untuk ambil 50 pertanyaan dari dataset legal Indonesia:

```bash
cat > scripts/generate_calibration_set.py << 'PYEOF'
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