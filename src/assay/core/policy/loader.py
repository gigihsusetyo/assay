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
    "answer_relevance",
    "p95_latency_ms",
    "avg_cost_usd",
}

VALID_THRESHOLD_TYPES = {"relative", "absolute"}


def _validate_threshold(key: str, raw: Any) -> dict[str, Any]:
    """Validate a single threshold spec.

    Accepts:
      - number: 5.0 -> {"value": 5.0, "type": "relative"}
      - dict: {"value": 5.0, "type": "relative"}

    Returns a normalized dict.
    """
    if isinstance(raw, bool):
        raise PolicyError(
            f"Threshold '{key}' must be a number or a mapping, got bool"
        )
    if isinstance(raw, (int, float)):
        value = float(raw)
        threshold_type = "relative"
    elif isinstance(raw, dict):
        if "value" not in raw:
            raise PolicyError(
                f"Threshold '{key}' is a mapping but has no 'value' key"
            )
        value = raw["value"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PolicyError(
                f"Threshold '{key}.value' must be a number, "
                f"got {type(value).__name__}"
            )
        value = float(value)
        threshold_type = raw.get("type", "relative")
    else:
        raise PolicyError(
            f"Threshold '{key}' must be a number or a mapping, "
            f"got {type(raw).__name__}"
        )

    if threshold_type not in VALID_THRESHOLD_TYPES:
        raise PolicyError(
            f"Threshold '{key}.type' must be one of "
            f"{sorted(VALID_THRESHOLD_TYPES)}, got {threshold_type!r}"
        )

    if value < 0:
        raise PolicyError(
            f"Threshold '{key}' must be non-negative, got {value}"
        )

    return {"value": value, "type": threshold_type}


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load a policy from a YAML file.

    Expected structure:
        version: 1
        thresholds:
          groundedness: 5.0
          context_recall: 5.0
          p95_latency_ms: 20.0
          avg_cost_usd: 20.0

    Or with explicit types:
        version: 1
        thresholds:
          groundedness:
            value: 5.0
            type: relative
          context_recall:
            value: 0.05
            type: absolute

    Returns the thresholds dict, with each value normalized to
    {"value": float, "type": str}.
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

    normalized: dict[str, Any] = {}
    for key, raw in thresholds.items():
        if key not in VALID_THRESHOLD_KEYS:
            raise PolicyError(
                f"Unknown threshold key: {key}. "
                f"Valid keys: {sorted(VALID_THRESHOLD_KEYS)}"
            )
        normalized[key] = _validate_threshold(key, raw)

    return normalized
