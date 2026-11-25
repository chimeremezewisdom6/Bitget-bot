"""Load and validate pre-registered experiment specifications (TOML)."""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = ("id", "version", "question", "hypothesis", "event", "outcomes", "split", "decision")
REQUIRED_SPLIT = {"total_days": 30, "train_days": 15, "validation_days": 7, "test_days": 8}


class SpecError(ValueError):
    pass


def load(path: str | Path) -> dict[str, Any]:
    spec = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    validate(spec)
    return spec


def validate(spec: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_TOP_LEVEL if key not in spec]
    if missing:
        raise SpecError(f"Missing required keys: {', '.join(missing)}")
    if not isinstance(spec["event"], dict) or not str(spec["event"].get("type", "")).strip():
        raise SpecError("event.type is required")
    horizons = (spec.get("outcomes") or {}).get("horizons")
    if not horizons or not all(isinstance(value, int) and value > 0 for value in horizons):
        raise SpecError("outcomes.horizons must be positive integers")
    split = spec.get("split") or {}
    for key, expected in REQUIRED_SPLIT.items():
        if split.get(key) != expected:
            raise SpecError(f"split.{key} must be {expected} for the approved 30-day protocol")
    if split.get("train_days", 0) + split.get("validation_days", 0) + split.get("test_days", 0) != split.get("total_days"):
        raise SpecError("split days must sum to total_days")
    decision = spec.get("decision") or {}
    for key in ("min_events", "min_days", "ci", "fdr_q"):
        if key not in decision:
            raise SpecError(f"decision.{key} is required")
    if spec.get("version") and not isinstance(spec["version"], str):
        raise SpecError("version must be a string")


def load_all(directory: str | Path) -> dict[str, dict[str, Any]]:
    specs = {}
    for path in sorted(Path(directory).glob("*.toml")):
        spec = load(path)
        specs[spec["id"]] = spec
    return specs
