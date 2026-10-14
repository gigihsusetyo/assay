"""Parse relevance-reviewed .txt batches into a JSON file.

Usage:
    python scripts/review_parse_relevance.py
    python scripts/review_parse_relevance.py --output examples/relevance_set_reviewed.json

Reads review/relevance/batch_*.txt, extracts HUMAN field, merges with
the original calibration set, and writes a new JSON file with
human_relevant field.
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
                results[current_id] = {"human": None, "note": "", "raw_human": ""}
            continue

        m = HUMAN_RE.match(line.strip())
        if m and current_id:
            raw = m.group(1).strip()
            results[current_id]["raw_human"] = raw
            upper = raw.upper()
            if upper == "RELEVANT":
                results[current_id]["human"] = True
            elif upper == "NOT RELEVANT":
                results[current_id]["human"] = False
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
        default="review/relevance",
        help="Directory with batch_*.txt (default: review/relevance)",
    )
    parser.add_argument(
        "--calibration-set",
        default="examples/calibration_set_reviewed.json",
        help="Original calibration set (default: examples/calibration_set_reviewed.json)",
    )
    parser.add_argument(
        "--output",
        default="examples/relevance_set_reviewed.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input dir not found: {input_dir}")

    batch_files = sorted(input_dir.glob("batch_*.txt"))
    if not batch_files:
        raise SystemExit(f"No batch_*.txt in {input_dir}")

    with Path(args.calibration_set).open(encoding="utf-8") as f:
        original = json.load(f)
    original_by_id = {e["id"]: e for e in original.get("entries", [])}

    decisions: dict[str, dict] = {}
    for batch_file in batch_files:
        parsed = _parse_batch(batch_file)
        print(f"{batch_file}: {len(parsed)} entries parsed")
        decisions.update(parsed)

    print()
    print(f"Total decisions: {len(decisions)}")

    final_entries: list[dict] = []
    labeled = 0
    skipped = 0
    empty = 0

    for eid, d in decisions.items():
        if eid not in original_by_id:
            print(f"WARNING: {eid} not in calibration set, skipping")
            continue
        human = d["human"]
        if human is None:
            raw = d["raw_human"].upper()
            if raw == "SKIP" or raw == "FLAG":
                skipped += 1
            else:
                empty += 1
            continue
        entry = dict(original_by_id[eid])
        entry["human_relevant"] = human
        entry["human_relevance_reason"] = (
            f"Manual review: {d['note']}" if d["note"] else "Manual review"
        )
        final_entries.append(entry)
        labeled += 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0.0",
        "description": f"Relevance review set. {labeled} labeled entries.",
        "entries": final_entries,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Labeled: {labeled}")
    print(f"Skipped: {skipped}")
    print(f"Empty:   {empty}")
    print()
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
