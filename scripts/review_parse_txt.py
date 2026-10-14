"""Parse reviewed .txt batches into a JSON calibration set.

Usage:
    python scripts/review_parse_txt.py
    python scripts/review_parse_txt.py --output examples/calibration_set_reviewed.json

Reads review/batch_*.txt, extracts the HUMAN field for each entry,
merges with the original calibration set, and writes a new JSON file.

Entries with HUMAN: SKIP or HUMAN: FLAG (or empty) are excluded from
the final set but reported.
"""

import argparse
import json
import re
from pathlib import Path

ENTRY_HEADER_RE = re.compile(r"^ENTRY\s+(\d+)\s*/\s*(\d+)$")
ID_RE = re.compile(r"^ID:\s*(.+)$")
HUMAN_RE = re.compile(r"^HUMAN:\s*(.*)$")
NOTE_RE = re.compile(r"^NOTE:\s*(.*)$")


def _parse_batch(path: Path) -> dict[str, dict]:
    """Return {entry_id: {human: bool|None, note: str, raw_human: str}}."""
    results: dict[str, dict] = {}
    current_id: str | None = None
    in_entry = False

    text = path.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        m = ENTRY_HEADER_RE.match(line.strip())
        if m:
            in_entry = True
            current_id = None
            continue

        if not in_entry:
            continue

        m = ID_RE.match(line.strip())
        if m:
            current_id = m.group(1).strip()
            if current_id not in results:
                results[current_id] = {
                    "human": None,
                    "note": "",
                    "raw_human": "",
                }
            continue

        m = HUMAN_RE.match(line.strip())
        if m and current_id:
            raw = m.group(1).strip()
            results[current_id]["raw_human"] = raw
            upper = raw.upper()
            if upper == "GROUNDED":
                results[current_id]["human"] = True
            elif upper == "NOT GROUNDED":
                results[current_id]["human"] = False
            elif upper in ("SKIP", "FLAG"):
                results[current_id]["human"] = None
            else:
                results[current_id]["human"] = None
            continue

        m = NOTE_RE.match(line.strip())
        if m and current_id:
            results[current_id]["note"] = m.group(1).strip()
            continue

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        default="review",
        help="Directory with batch_*.txt files (default: review)",
    )
    parser.add_argument(
        "--calibration-set",
        default="examples/calibration_set.json",
        help="Original calibration set JSON (default: examples/calibration_set.json)",
    )
    parser.add_argument(
        "--output",
        default="examples/calibration_set_reviewed.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input dir not found: {input_dir}")

    batch_files = sorted(input_dir.glob("batch_*.txt"))
    if not batch_files:
        raise SystemExit(f"No batch_*.txt found in {input_dir}")

    # Load original calibration set for reference (by id)
    with Path(args.calibration_set).open(encoding="utf-8") as f:
        original = json.load(f)
    original_by_id = {e["id"]: e for e in original.get("entries", [])}

    # Parse all batches
    decisions: dict[str, dict] = {}
    for batch_file in batch_files:
        parsed = _parse_batch(batch_file)
        print(f"{batch_file}: {len(parsed)} entries parsed")
        for eid, d in parsed.items():
            decisions[eid] = d

    print()
    print(f"Total decisions: {len(decisions)}")
    print()

    # Build final set
    final_entries: list[dict] = []
    labeled = 0
    skipped = 0
    flagged = 0
    empty = 0

    for eid, d in decisions.items():
        if eid not in original_by_id:
            print(f"WARNING: {eid} not in original calibration set, skipping")
            continue

        human = d["human"]
        if human is None:
            raw = d["raw_human"].upper()
            if raw == "SKIP":
                skipped += 1
            elif raw == "FLAG":
                flagged += 1
            else:
                empty += 1
            continue

        entry = dict(original_by_id[eid])
        entry["human_grounded"] = human
        entry["human_verdict"] = None
        entry["human_reason"] = (
            f"Manual review: {d['note']}" if d["note"] else "Manual review"
        )
        final_entries.append(entry)
        labeled += 1

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "5.0.0",
        "description": (
            f"Manually reviewed calibration set. "
            f"{labeled} labeled entries."
        ),
        "entries": final_entries,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Labeled:   {labeled}")
    print(f"Skipped:   {skipped}")
    print(f"Flagged:   {flagged}")
    print(f"Empty:     {empty}")
    print()
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
