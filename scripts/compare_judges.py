"""Compare judge providers on the same calibration set.

For each configured provider, this script runs the judge on the
calibration set and computes agreement with human labels. It then
prints a comparison table.

Usage:
    python scripts/compare_judges.py examples/calibration_set.json

The script reads provider configuration from the environment. All
providers configured via ASSAY_JUDGE_PROVIDER, ASSAY_JUDGE_PROVIDER_2,
and so on are compared.

Each provider gets its own isolated environment. The script sets the
provider as primary, then runs the judge. It does not use fallback
during comparison.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProviderResult:
    """Result of running the judge with one provider."""

    name: str
    model: str
    entries: int
    tp: int
    tn: int
    fp: int
    fn: int
    errors: int

    @property
    def agreement(self) -> float:
        total = self.tp + self.tn + self.fp + self.fn
        if total == 0:
            return 0.0
        return (self.tp + self.tn) / total

    @property
    def kappa(self) -> float:
        total = self.tp + self.tn + self.fp + self.fn
        if total == 0:
            return 0.0
        po = (self.tp + self.tn) / total
        p_yes = (self.tp + self.fp) / total
        p_no = (self.tn + self.fn) / total
        p_human_yes = (self.tp + self.fn) / total
        p_human_no = (self.tn + self.fp) / total
        pe = (p_yes * p_human_yes) + (p_no * p_human_no)
        if pe == 1.0:
            return 1.0
        return (po - pe) / (1 - pe)


def _load_providers_from_env() -> list[dict]:
    """Read provider configs from environment variables."""
    providers = []

    # Primary
    name = os.environ.get("ASSAY_JUDGE_PROVIDER")
    model = os.environ.get("ASSAY_JUDGE_MODEL")
    api_key = os.environ.get("ASSAY_JUDGE_API_KEY")
    base_url = os.environ.get("ASSAY_JUDGE_BASE_URL", "")
    if name and model and api_key:
        providers.append({
            "name": name,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
        })

    # Numbered
    for i in range(2, 5):
        name = os.environ.get(f"ASSAY_JUDGE_PROVIDER_{i}")
        model = os.environ.get(f"ASSAY_JUDGE_MODEL_{i}")
        api_key = os.environ.get(f"ASSAY_JUDGE_API_KEY_{i}")
        base_url = os.environ.get(f"ASSAY_JUDGE_BASE_URL_{i}", "")
        if name and model and api_key:
            providers.append({
                "name": name,
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
            })

    return providers


def _run_with_provider(provider: dict, entries: list[dict]) -> ProviderResult:
    """Run the judge with a single provider and compute metrics."""
    # Clear assay modules so config reloads
    for mod in list(sys.modules.keys()):
        if mod.startswith("assay.config") or mod.startswith("assay.core.metrics.judge"):
            del sys.modules[mod]

    os.environ["ASSAY_JUDGE_PROVIDER"] = provider["name"]
    os.environ["ASSAY_JUDGE_MODEL"] = provider["model"]
    os.environ["ASSAY_JUDGE_API_KEY"] = provider["api_key"]
    os.environ["ASSAY_JUDGE_BASE_URL"] = provider["base_url"]
    os.environ["ASSAY_JUDGE_FALLBACK"] = "false"

    from assay.core.metrics.judge import JudgeError, judge_groundedness

    tp = tn = fp = fn = errors = 0
    for e in entries:
        human = e.get("human_grounded")
        if human is None:
            continue
        try:
            result = judge_groundedness(
                question=e["question"],
                answer=e["answer"],
                contexts=e["contexts"],
            )
            judge = result.grounded
        except JudgeError:
            errors += 1
            continue

        if human and judge:
            tp += 1
        elif not human and not judge:
            tn += 1
        elif not human and judge:
            fp += 1
        elif human and not judge:
            fn += 1

    return ProviderResult(
        name=provider["name"],
        model=provider["model"],
        entries=tp + tn + fp + fn,
        tp=tp,
        tn=tn,
        fp=fp,
        fn=fn,
        errors=errors,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calibration_set", help="Calibration set JSON file")
    args = parser.parse_args()

    path = Path(args.calibration_set)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        raise SystemExit("Calibration set has no entries")

    providers = _load_providers_from_env()
    if not providers:
        raise SystemExit("No providers configured in environment.")

    print(f"Calibration set: {len(entries)} entries")
    print(f"Providers: {len(providers)}")
    print()

    results: list[ProviderResult] = []
    for p in providers:
        print(f"Running: {p['name']} ({p['model']})...")
        result = _run_with_provider(p, entries)
        results.append(result)
        print(f"  Agreement: {result.agreement * 100:.1f}% | Kappa: {result.kappa:.3f} | Errors: {result.errors}")
        print()

    # Comparison table
    print("=" * 80)
    print("Comparison")
    print("=" * 80)
    print()
    header = f"{'Provider':<15} {'Model':<28} {'Entries':>7} {'Agree':>8} {'Kappa':>8} {'Errors':>7}"
    print(header)
    print("-" * len(header))

    for r in results:
        model_short = r.model[:26] + ".." if len(r.model) > 28 else r.model
        print(
            f"{r.name:<15} {model_short:<28} {r.entries:>7} "
            f"{r.agreement * 100:>7.1f}% {r.kappa:>8.3f} {r.errors:>7}"
        )

    print()
    print("Note: providers are compared without fallback. Each provider")
    print("is tested in isolation. If a provider fails, the error count")
    print("reflects that.")


if __name__ == "__main__":
    main()
