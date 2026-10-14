"""Split calibration set into relevance review batches (plain text).

Usage:
    python scripts/review_split_relevance.py
    python scripts/review_split_relevance.py --size 100

Creates:
    review/relevance/batch_01.txt
    ...
"""

import argparse
import json
import random
from pathlib import Path

SEPARATOR = "=" * 72
DASHED = "-" * 72


def _wrap(text: str, width: int = 68, indent: str = "  ") -> str:
    words = text.split()
    lines: list[str] = []
    current = indent
    for word in words:
        if len(current) + len(word) + 1 > width and current.strip():
            lines.append(current.rstrip())
            current = indent + word + " "
        else:
            current += word + " "
    if current.strip():
        lines.append(current.rstrip())
    return "\n".join(lines) if lines else indent


def _entry_to_text(index: int, total: int, entry: dict) -> str:
    lines: list[str] = []
    lines.append(SEPARATOR)
    lines.append(f"ENTRY {index:03d} / {total}")
    lines.append(f"ID: {entry.get('id', '?')}")
    lines.append(SEPARATOR)
    lines.append("")
    lines.append("QUESTION:")
    lines.append(_wrap(entry.get("question", "")))
    lines.append("")
    lines.append("ANSWER:")
    lines.append(_wrap(entry.get("answer", "")))
    lines.append("")
    lines.append(DASHED)
    lines.append("HUMAN:          <-- isi: RELEVANT / NOT RELEVANT / SKIP / FLAG")
    lines.append("NOTE:           <-- opsional")
    lines.append(DASHED)
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="examples/calibration_set_reviewed.json",
        help="Input calibration set (default: examples/calibration_set_reviewed.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="review/relevance",
        help="Output directory (default: review/relevance)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=100,
        help="Entries per batch (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    with input_path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        raise SystemExit("No entries found.")

    rng = random.Random(args.seed)
    rng.shuffle(entries)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(entries)
    batch_size = args.size
    num_batches = (total + batch_size - 1) // batch_size

    print(f"Total entries: {total}")
    print(f"Batch size:    {batch_size}")
    print(f"Num batches:   {num_batches}")
    print()

    for i in range(num_batches):
        start = i * batch_size
        end = min(start + batch_size, total)
        batch_entries = entries[start:end]

        batch_path = output_dir / f"batch_{i + 1:02d}.txt"
        parts: list[str] = []
        parts.append(f"RELEVANCE BATCH {i + 1:02d} — {len(batch_entries)} entries")
        parts.append("")
        parts.append("Cara mengisi: ganti 'HUMAN:' dengan salah satu dari:")
        parts.append("  HUMAN: RELEVANT")
        parts.append("  HUMAN: NOT RELEVANT")
        parts.append("  HUMAN: SKIP")
        parts.append("  HUMAN: FLAG")
        parts.append("")
        parts.append("Aturan: apakah ANSWER menjawab QUESTION?")
        parts.append("Tidak perlu lihat konteks. Fokus ke Q vs A saja.")
        parts.append("")
        parts.append("")

        for j, entry in enumerate(batch_entries):
            global_index = start + j + 1
            parts.append(_entry_to_text(global_index, total, entry))

        batch_path.write_text("\n".join(parts), encoding="utf-8")
        print(f"  {batch_path}: {len(batch_entries)} entries")

    print()
    print("Done. Review the .txt files in your editor.")


if __name__ == "__main__":
    main()
