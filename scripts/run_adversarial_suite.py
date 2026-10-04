"""Run the adversarial suite against the current judge.

Usage:
    python scripts/run_adversarial_suite.py examples/adversarial_suite.json

For each case, the script runs the judge and compares the result against
the expected outcome. It reports pass/fail per case and per category.

Exit code 0 if all pass, 1 if any fail, 2 if the suite cannot run.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from assay.core.metrics.judge import JudgeError, judge_groundedness


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", help="Adversarial suite JSON file")
    args = parser.parse_args()

    path = Path(args.suite)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        raise SystemExit("Suite has no entries")

    print("=" * 70)
    print("Adversarial Suite Runner")
    print("=" * 70)
    print()

    results_by_category: dict[str, list[tuple[str, bool, str]]] = defaultdict(list)
    total = 0
    passed = 0
    errors = 0

    for entry in entries:
        case_id = entry.get("id", "?")
        category = entry.get("category", "uncategorized")
        expected_grounded = entry.get("expected_grounded")
        expected_verdict = entry.get("expected_verdict")
        expected_abstained = entry.get("expected_abstained", False)
        why = entry.get("why", "")

        try:
            result = judge_groundedness(
                question=entry["question"],
                answer=entry["answer"],
                contexts=entry.get("contexts", []),
            )
        except JudgeError as e:
            print(f"[{case_id}] ERROR: {e}")
            results_by_category[category].append((case_id, False, "judge error"))
            errors += 1
            total += 1
            continue

        # Check grounded
        grounded_ok = (result.grounded == expected_grounded) if expected_grounded is not None else True

        # Check abstained
        abstained_ok = result.abstained == expected_abstained

        # Check verdict if expected
        verdict_ok = True
        actual_verdict = None
        if expected_verdict is not None:
            if result.claims:
                actual_verdict = result.claims[0].verdict
                verdict_ok = actual_verdict == expected_verdict
            else:
                verdict_ok = False

        ok = grounded_ok and abstained_ok and verdict_ok
        total += 1
        if ok:
            passed += 1

        status = "PASS" if ok else "FAIL"
        print(f"[{case_id}] {status} ({category})")
        print(f"  Expected: grounded={expected_grounded}, "
              f"verdict={expected_verdict}, abstained={expected_abstained}")
        print(f"  Got:      grounded={result.grounded}, "
              f"verdict={actual_verdict}, abstained={result.abstained}, "
              f"score={result.score:.2f}")
        if not ok:
            print(f"  Why this matters: {why}")
            if result.claims:
                for c in result.claims:
                    print(f"    claim: {c.text[:70]}")
                    print(f"    verdict: {c.verdict}, evidence: {(c.evidence or 'none')[:60]}")
        print()

        results_by_category[category].append((case_id, ok, status))

    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print(f"Total:  {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Errors: {errors}")
    print(f"Pass rate: {passed / total * 100:.1f}%")
    print()

    print("By category:")
    for category, results in sorted(results_by_category.items()):
        cat_passed = sum(1 for _, ok, _ in results if ok)
        cat_total = len(results)
        marker = "OK " if cat_passed == cat_total else "FAIL"
        print(f"  [{marker}] {category}: {cat_passed}/{cat_total}")
    print()

    if passed < total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
