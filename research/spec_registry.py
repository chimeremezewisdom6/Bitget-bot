"""Frozen Phase B experiment registry and hash validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .events import DETECTORS

DEFAULT_PATH = Path(__file__).resolve().parent / "specs" / "phase_b_v2.json"
REQUIRED_REGISTRY = (
    "registry_version", "created_at", "frozen", "families", "defaults", "holdout", "specs",
)
REQUIRED_SPEC = (
    "spec_id", "version", "family", "event_type", "params", "direction",
    "horizons_min", "buckets", "min_n", "hypothesis", "rationale", "spec_hash",
)
REQUIRED_HOLDOUT = ("policy", "unlock_after_days", "requires", "unlock_at", "evaluated")


class SpecError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def spec_hash(spec: dict[str, Any]) -> str:
    payload = {key: value for key, value in spec.items() if key != "spec_hash"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def registry_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DEFAULT_PATH
    if not target.exists():
        raise SpecError(f"Registry not found: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    validate_registry(data)
    return data


def validate_registry(data: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_REGISTRY if key not in data]
    if missing:
        raise SpecError(f"Missing registry keys: {', '.join(missing)}")
    if data.get("frozen") is not True:
        raise SpecError("Registry must be frozen before evaluation")
    families = data.get("families")
    if not isinstance(families, dict) or not families:
        raise SpecError("families must be a non-empty object")
    for name, family in families.items():
        if not isinstance(family, dict) or "specs" not in family or "fdr_q" not in family:
            raise SpecError(f"family {name} must contain specs and fdr_q")
        if not 0.0 < float(family["fdr_q"]) <= 1.0:
            raise SpecError(f"family {name} fdr_q must be in (0, 1]")

    specs = data.get("specs")
    if not isinstance(specs, list) or not specs:
        raise SpecError("specs must be a non-empty list")
    seen: set[str] = set()
    for spec in specs:
        _validate_spec(spec, families)
        spec_id = spec["spec_id"]
        if spec_id in seen:
            raise SpecError(f"Duplicate spec_id: {spec_id}")
        seen.add(spec_id)
    for name, family in families.items():
        for spec_id in family["specs"]:
            if spec_id not in seen:
                raise SpecError(f"family {name} references unknown spec {spec_id}")

    holdout = data.get("holdout")
    if not isinstance(holdout, dict):
        raise SpecError("holdout must be an object")
    for key in REQUIRED_HOLDOUT:
        if key not in holdout:
            raise SpecError(f"holdout.{key} is required")
    if holdout.get("policy") not in ("locked_newest_day", "locked_last_20pct"):
        raise SpecError("Unsupported holdout policy")
    if int(holdout.get("unlock_after_days", 0)) < 30:
        raise SpecError("holdout.unlock_after_days must be at least 30")
    if holdout.get("evaluated") is not False:
        raise SpecError("The frozen registry must not mark the holdout evaluated")

    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        raise SpecError("defaults must be an object")
    for key in ("horizons_min", "entry_latency_bars", "dedupe_ms", "non_overlapping",
                "fee_bps_per_side", "slippage_bps", "slippage_sensitivity_bps",
                "min_n", "min_days", "fdr_q", "bootstrap"):
        if key not in defaults:
            raise SpecError(f"defaults.{key} is required")
    if "feature_lookback_min" in defaults and int(defaults["feature_lookback_min"]) < 64:
        raise SpecError("defaults.feature_lookback_min must be at least 64")

    profiles = data.get("split_profiles") or {}
    if profiles and not isinstance(profiles, dict):
        raise SpecError("split_profiles must be an object")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise SpecError(f"split_profiles.{name} must be an object")
        for key in ("train_days", "validation_days", "holdout_days", "min_days"):
            if key not in profile:
                raise SpecError(f"split_profiles.{name}.{key} is required")
        if min(int(profile["train_days"]), int(profile["validation_days"]), int(profile["holdout_days"])) < 1:
            raise SpecError(f"split_profiles.{name} day counts must be positive")
        for key in ("pipeline", "validation", "holdout"):
            if key not in profile["min_days"]:
                raise SpecError(f"split_profiles.{name}.min_days.{key} is required")
        if int(profile["min_days"]["validation"]) > int(profile["validation_days"]):
            raise SpecError(f"split_profiles.{name} validation min_days exceeds split")
        if int(profile["min_days"]["holdout"]) > int(profile["holdout_days"]):
            raise SpecError(f"split_profiles.{name} holdout min_days exceeds split")


def _validate_spec(spec: dict[str, Any], families: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_SPEC if key not in spec]
    if missing:
        raise SpecError(f"spec missing keys: {', '.join(missing)}")
    spec_id = str(spec["spec_id"])
    if spec["event_type"] not in DETECTORS:
        raise SpecError(f"{spec_id}: unknown event_type {spec['event_type']}")
    if spec["direction"] not in ("SIGNAL", "LONG", "SHORT"):
        raise SpecError(f"{spec_id}: direction must be SIGNAL, LONG or SHORT")
    horizons = spec["horizons_min"]
    if not isinstance(horizons, list) or not horizons or not all(
        isinstance(value, int) and value > 0 for value in horizons
    ):
        raise SpecError(f"{spec_id}: horizons_min must be positive integers")
    if not isinstance(spec["buckets"], list):
        raise SpecError(f"{spec_id}: buckets must be a list")
    min_n = spec["min_n"]
    if not isinstance(min_n, dict) or not all(
        key in min_n and int(min_n[key]) > 0 for key in ("pipeline", "validation", "holdout")
    ):
        raise SpecError(f"{spec_id}: min_n must define pipeline, validation and holdout")
    family = spec["family"]
    if family not in families:
        raise SpecError(f"{spec_id}: unknown family {family}")
    if spec_id not in families[family]["specs"]:
        raise SpecError(f"{spec_id}: not listed in family {family}")
    expected = str(spec["spec_hash"])
    actual = spec_hash(spec)
    if expected != actual:
        raise SpecError(
            f"{spec_id}: spec_hash mismatch (expected {expected}, computed {actual})"
        )


def specs_for_family(data: dict[str, Any], family: str) -> list[dict[str, Any]]:
    if family not in data["families"]:
        raise SpecError(f"Unknown family: {family}")
    wanted = set(data["families"][family]["specs"])
    return [spec for spec in data["specs"] if spec["spec_id"] in wanted]


def spec_by_id(data: dict[str, Any], spec_id: str) -> dict[str, Any]:
    for spec in data["specs"]:
        if spec["spec_id"] == spec_id:
            return spec
    raise SpecError(f"Unknown spec_id: {spec_id}")
