"""Load and validate regression policy from YAML."""

from pathlib import Path
from typing import Any

import yaml


class PolicyError(Exception):
    """Raised when a policy file is invalid."""

    pass


VALID_THRESHOLD_KEYS = {
    "groundedness",
    "context_recall",
    "p95_latency_ms",
    "avg_cost_usd",
}


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load a policy from a YAML file.

    Expected structure:
        version: 1
        thresholds:
          groundedness: 5.0
          context_recall: 5.0
          p95_latency_ms: 20.0
          avg_cost_usd: 20.0

    Returns the thresholds dict.
    """
    path = Path(path)
    if not path.exists():
        raise PolicyError(f"Policy file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise PolicyError("Policy file must be a YAML mapping")

    if "thresholds" not in data:
        raise PolicyError("Policy file must contain a 'thresholds' key")

    thresholds = data["thresholds"]
    if not isinstance(thresholds, dict):
        raise PolicyError("'thresholds' must be a mapping")

    for key, value in thresholds.items():
        if key not in VALID_THRESHOLD_KEYS:
            raise PolicyError(
                f"Unknown threshold key: {key}. "
                f"Valid keys: {sorted(VALID_THRESHOLD_KEYS)}"
            )
        if not isinstance(value, (int, float)):
            raise PolicyError(f"Threshold '{key}' must be a number, got {type(value).__name__}")
        if value < 0:
            raise PolicyError(f"Threshold '{key}' must be non-negative, got {value}")

    return thresholds
