"""Convert Indonesian Legal RAG dataset to Assay format.

Source: wahyyuht/skripsi-data on Hugging Face.
License: CC BY 4.0.

This script reads the test split, looks up the gold context for each
query from the index_rincian files, and writes a calibration set
template. The human_grounded and human_reason fields are left empty
for manual labeling.

Usage:
    python scripts/convert_legal_dataset.py \
        --output examples/calibration_set.json \
        --limit 50
"""

import argparse
import json
from pathlib import Path

from huggingface_hub import hf_hub_download

# Map from doc_id prefix to folder name in the dataset repo.
FOLDER_MAP = {
    "uu": "UU",
    "pp": "PP",
    "perpres": "PERPRES",
    "perpu": "PERPU",
    "pmk": "PMK",
    "permenkes": "PERMENKES",
    "permendag": "PERMENDAG",
    "permendagri": "PERMENDAGRI",
    "permenaker": "PERMENAKER",
    "permenkumham": "PERMENKUMHAM",
    "permenkominfo": "PERMENKOMINFO",
    "permenkomdigi": "PERMENKOMDIGI",
    "permenperin": "PERMENPERIN",
    "permen-pupr": "PERMEN_PUPR",
    "permen-esdm": "PERMEN_ESDM",
    "peraturan-ojk": "PERATURAN_OJK",
    "peraturan-bi": "PERATURAN_BI",
    "peraturan-bpom": "PERATURAN_BPOM",
    "peraturan-bssn": "PERATURAN_BSSN",
    "peraturan-kpu": "PERATURAN_KPU",
    "peraturan-menag": "PERMENAG",
    "peraturan-polri": "PERATURAN_POLRI",
    "perda": "PERDA",
    "perwali": "PERWALI",
    "pergub": "PERGUB",
    "perbup": "PERBUP",
    "perma": "PERATURAN_MA",
    "permendikbud": "PERMENDIKBUD",
    "permendikbudristek": "PERMENDIKBUDRISTEK",
    "permen-atr-kepala-bpn": "PERMEN_ATRBPN",
    "permen-bumn": "PERMENBUMN",
}


def folder_for(doc_id: str) -> str | None:
    """Guess the folder name for a doc_id."""
    # Try longest prefix match.
    for prefix in sorted(FOLDER_MAP.keys(), key=len, reverse=True):
        if doc_id.startswith(prefix):
            return FOLDER_MAP[prefix]
    return None


def find_node(nodes: list, target_id: str) -> dict | None:
    """Recursively search for a node by node_id."""
    for node in nodes:
        if node.get("node_id") == target_id:
            return node
        children = node.get("nodes", [])
        found = find_node(children, target_id)
        if found is not None:
            return found
    return None


def load_index(doc_id: str) -> dict | None:
    """Download and load the index_rincian for a doc_id."""
    folder = folder_for(doc_id)
    if folder is None:
        return None
    filename = f"index_rincian/{folder}/{doc_id}.json"
    try:
        path = hf_hub_download(
            repo_id="wahyyuht/skripsi-data",
            filename=filename,
            repo_type="dataset",
        )
    except Exception:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="examples/calibration_set.json",
        help="Output JSON file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of entries",
    )
    parser.add_argument(
        "--skip-used",
        default=None,
        help="Path to existing calibration set. Skip query IDs already used.",
    )
    args = parser.parse_args()

    test_path = hf_hub_download(
        repo_id="wahyyuht/skripsi-data",
        filename="splits/test.jsonl",
        repo_type="dataset",
    )

    with open(test_path, encoding="utf-8") as f:
        queries = [json.loads(line) for line in f]

    print(f"Total queries available: {len(queries)}")

    # Load used query IDs if requested
    used_ids: set[str] = set()
    if args.skip_used:
        skip_path = Path(args.skip_used)
        if skip_path.exists():
            with skip_path.open(encoding="utf-8") as f:
                skip_data = json.load(f)
            for e in skip_data.get("entries", []):
                if "id" in e:
                    used_ids.add(e["id"])
            print(f"Skipping {len(used_ids)} already-used query IDs")

    index_cache: dict[str, dict] = {}
    entries: list[dict] = []
    skipped = 0

    for q in queries:
        if len(entries) >= args.limit:
            break

        if q["query_id"] in used_ids:
            skipped += 1
            continue

        doc_id = q["gold_doc_id"]
        node_id = q["gold_node_id"]

        if doc_id not in index_cache:
            index = load_index(doc_id)
            if index is None:
                skipped += 1
                continue
            index_cache[doc_id] = index

        node = find_node(index_cache[doc_id].get("structure", []), node_id)
        if node is None:
            skipped += 1
            continue

        context_text = node.get("text", "").strip()
        if not context_text:
            skipped += 1
            continue

        entries.append({
            "id": q["query_id"],
            "category": "legal_indonesia",
            "question": q["query"],
            "answer": q.get("answer_hint", ""),
            "contexts": [context_text],
            "human_grounded": None,
            "human_verdict": None,
            "human_reason": "",
            "metadata": {
                "source": "indonesian-legal-rag",
                "gold_doc_id": doc_id,
                "gold_node_id": node_id,
                "navigation_path": q.get("navigation_path", ""),
                "query_type": q.get("query_type", ""),
                "query_style": q.get("query_style", ""),
            },
        })

    output = {
        "version": "1.0.0",
        "description": (
            "Calibration set for Assay LLM-as-judge validation. "
            "Entries from wahyyuht/skripsi-data (CC BY 4.0). "
            "human_grounded and human_reason must be filled manually."
        ),
        "entries": entries,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Written {len(entries)} entries to {output_path}")
    print(f"Skipped: {skipped}")
    print()
    print("Next: fill in human_grounded and human_reason manually.")


if __name__ == "__main__":
    main()
