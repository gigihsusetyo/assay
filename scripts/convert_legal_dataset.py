"""Convert Indonesian Legal RAG dataset to Assay format.

Source: wahyyuht/skripsi-data on Hugging Face.
License: CC BY 4.0.
"""

import json
from pathlib import Path

HF_CACHE = Path(
    "/home/vscode/.cache/huggingface/hub/"
    "datasets--wahyyuht--skripsi-data/snapshots/"
    "b29572cbddafa0a65948ed86ad278a8b3a06a1f6"
)

OUTPUT = Path("examples/datasets/indonesian-legal-rag.json")


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
    """Load index_rincian for a doc_id. Assumes UU folder for now."""
    path = HF_CACHE / "index_rincian" / "UU" / f"{doc_id}.json"
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def main() -> None:
    test_path = HF_CACHE / "splits" / "test.jsonl"
    if not test_path.exists():
        raise SystemExit(f"Test file not found: {test_path}")

    queries = []
    with test_path.open() as f:
        for i, line in enumerate(f):
            if i >= 10:
                break
            queries.append(json.loads(line))

    index_cache: dict[str, dict] = {}
    questions = []
    skipped = 0

    for q in queries:
        doc_id = q["gold_doc_id"]
        node_id = q["gold_node_id"]

        if doc_id not in index_cache:
            index = load_index(doc_id)
            if index is None:
                print(f"  Skip {q['query_id']}: index for {doc_id} not found")
                skipped += 1
                continue
            index_cache[doc_id] = index

        index = index_cache[doc_id]
        node = find_node(index.get("structure", []), node_id)

        if node is None:
            print(f"  Skip {q['query_id']}: node {node_id} not found in {doc_id}")
            skipped += 1
            continue

        questions.append({
            "question": q["query"],
            "expected_answer": q["answer_hint"],
            "expected_context": node.get("text", ""),
            "metadata": {
                "source_query_id": q["query_id"],
                "gold_doc_id": doc_id,
                "gold_node_id": node_id,
                "navigation_path": q.get("navigation_path", ""),
                "query_type": q.get("query_type", ""),
                "query_style": q.get("query_style", ""),
            },
        })

    dataset = {
        "name": "indonesian-legal-rag",
        "version": "1.0.0",
        "description": (
            "Indonesian legal RAG benchmark. 10 queries from "
            "wahyyuht/skripsi-data (CC BY 4.0). "
            "Source: https://huggingface.co/datasets/wahyyuht/skripsi-data"
        ),
        "source": "https://huggingface.co/datasets/wahyyuht/skripsi-data",
        "license": "CC BY 4.0",
        "questions": questions,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"Written {len(questions)} questions to {OUTPUT}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
