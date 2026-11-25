"""Phase B nightly evaluation over collected bundles.

The evaluator is deterministic. It never calls an LLM, never places orders and
never evaluates the locked holdout unless the registry hash, unlock date and
manual confirmation all match.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from . import events as event_module
from . import outcomes as outcome_module
from . import stats
from .dataset import load_bundle, sha256_file, split_30d
from .features import absorption_proxy
from .spec_registry import (
    SpecError,
    load_registry,
    registry_hash,
    specs_for_family,
)

DAY_MS = 86_400_000
SLOT_MS = 300_000
BUNDLE_SECTIONS = {"features", "candles", "universe", "exclusions", "liquidations", "spot"}


def _num(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(int(ts_ms) / 1000.0, timezone.utc).isoformat()


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _turnover_band(value: Any) -> str:
    turnover = _num(value)
    if turnover is None:
        return "UNVERIFIED"
    if turnover < 1_000_000:
        return "under_1m_turnover"
    if turnover < 10_000_000:
        return "1m_10m_turnover"
    if turnover < 100_000_000:
        return "10m_100m_turnover"
    return "over_100m_turnover"


def _liquidation_side(feature: dict[str, Any]) -> str:
    long_usdt = _num(feature.get("liquidation_long_usdt")) or 0.0
    short_usdt = _num(feature.get("liquidation_short_usdt")) or 0.0
    if long_usdt > short_usdt:
        return "LONG"
    if short_usdt > long_usdt:
        return "SHORT"
    return "MIXED"


def _volatility_bucket(feature: dict[str, Any]) -> str:
    status = str(feature.get("volatility_status") or "").upper()
    if status == "GAP":
        return "flag_gap"
    if status == "INSUFFICIENT_CANDLES":
        return "flag_insufficient"
    flag = feature.get("flag_0_7")
    if flag is True:
        return "flag_true"
    if flag is False:
        return "flag_false"
    return "flag_unknown"


def bucket_value(feature: dict[str, Any], dimension: str) -> str:
    if dimension == "flag_0_7":
        return _volatility_bucket(feature)
    if dimension == "turnover_band":
        return str(feature.get("turnover_band") or _turnover_band(feature.get("turnover24h_usdt")))
    if dimension == "taker_quality":
        return str(feature.get("taker_quality") or "UNKNOWN")
    if dimension == "oi_regime":
        delta = _num(feature.get("oi_delta_15m_pct"))
        if delta is None:
            return "oi_unknown"
        return "oi_up" if delta > 0 else "oi_down" if delta < 0 else "oi_flat"
    if dimension == "oi_price_alignment":
        return str(feature.get("oi_price_alignment") or "UNKNOWN")
    if dimension == "liquidation_side":
        return str(feature.get("liquidation_side") or _liquidation_side(feature))
    if dimension == "spot_status":
        status = str(feature.get("spot_status") or "")
        if status == "MAPPED":
            return "spot_mapped"
        if status:
            return "spot_unmapped"
        return "spot_unknown"
    return "UNKNOWN"


def enrich_features(features: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add depth change and derived fields using only prior rows."""
    ordered = sorted(features, key=lambda row: (str(row.get("symbol", "")), int(row.get("ts_ms") or 0)))
    previous: dict[str, dict[str, Any]] = {}
    enriched: list[dict[str, Any]] = []
    for row in ordered:
        row = dict(row)
        symbol = str(row.get("symbol", ""))
        ts_ms = int(row.get("ts_ms") or 0)
        prev = previous.get(symbol)
        opposite_change = None
        if prev is not None and 0 < ts_ms - int(prev.get("ts_ms") or 0) <= 600_000:
            imbalance = _num(row.get("taker_imbalance"))
            if imbalance is not None:
                side = "ask" if imbalance > 0 else "bid"
                current_depth = _num(row.get(f"{side}_depth_0_5pct_usdt"))
                previous_depth = _num(prev.get(f"{side}_depth_0_5pct_usdt"))
                if current_depth is not None and previous_depth and previous_depth > 0:
                    opposite_change = 100.0 * (current_depth / previous_depth - 1.0)
        book_imbalance = _num(row.get("book_imbalance_0p5"))
        if book_imbalance is None:
            bid_depth = _num(row.get("bid_depth_0_5pct_usdt")) or 0.0
            ask_depth = _num(row.get("ask_depth_0_5pct_usdt")) or 0.0
            total_depth = bid_depth + ask_depth
            book_imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else None
        row["book_imbalance_0p5"] = book_imbalance
        row["opposite_depth_change_pct"] = opposite_change
        row["absorption"] = absorption_proxy(
            _num(row.get("taker_imbalance")),
            _num(row.get("return_5m_pct")),
            opposite_change,
            book_imbalance=book_imbalance,
            min_imbalance=0.5,
            max_price_move_pct=0.1,
            min_depth_change_pct=-10.0,
        )
        delta = _num(row.get("oi_delta_15m_pct"))
        ret15 = _num(row.get("return_15m_pct"))
        row["oi_direction"] = "UNKNOWN" if delta is None else "UP" if delta > 0 else "DOWN"
        row["price_direction"] = "UNKNOWN" if ret15 is None else "LONG" if ret15 > 0 else "SHORT"
        row["oi_price_alignment"] = (
            "UNKNOWN" if delta is None or ret15 is None
            else "ALIGNED" if delta * ret15 > 0 else "OPPOSED"
        )
        row["turnover_band"] = row.get("turnover_band") or _turnover_band(row.get("turnover24h_usdt"))
        row["spot_status"] = row.get("spot_status") or (
            "MAPPED" if row.get("spot_basis_bps") is not None else "SPOT_UNMAPPED"
        )
        row["liquidation_side"] = row.get("liquidation_side") or _liquidation_side(row)
        enriched.append(row)
        previous[symbol] = row
    return enriched


def load_bundles(root: str | Path) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    candles: dict[tuple[str, int], dict[str, Any]] = {}
    metas: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    truncated: list[str] = []
    seen_features: set[tuple[str, int]] = set()
    duplicate_features = 0
    for path in sorted(Path(root).rglob("bundle.tar.gz")):
        summary_path = path.parent / "summary.json"
        summary: dict[str, Any] = {}
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                errors.append({"path": str(summary_path), "error": "SUMMARY_UNREADABLE"})
        expected_sha = (summary.get("manifest") or {}).get("sha256")
        actual_sha = sha256_file(path)
        if expected_sha and expected_sha != actual_sha:
            errors.append({
                "path": str(path), "error": "BAD_SHA",
                "expected_sha256": expected_sha, "actual_sha256": actual_sha,
            })
            continue
        try:
            bundle = load_bundle(path, sections=BUNDLE_SECTIONS)
        except Exception as exc:
            errors.append({"path": str(path), "error": type(exc).__name__, "message": str(exc)[:300]})
            continue
        meta = bundle.get("meta") or {}
        if meta.get("trading_enabled") is not False:
            raise SpecError(f"Bundle {path} does not declare trading_enabled=false")
        metas.append({
            "path": str(path), "sha256": actual_sha,
            "outcome": summary.get("outcome") or meta.get("outcome"),
            "meta": meta,
        })
        if (summary.get("manifest") or {}).get("quality", {}).get("truncated_sections"):
            truncated.append(str(path))
        rows = bundle.get("rows") or {}
        for row in rows.get("features", []) or []:
            key = (str(row.get("symbol", "")), int(row.get("ts_ms") or 0))
            if key in seen_features:
                duplicate_features += 1
                continue
            seen_features.add(key)
            features.append(row)
        for row in rows.get("candles", []) or []:
            symbol = str(row.get("symbol", ""))
            ts = row.get("ts", row.get("candle_timestamp_ms"))
            try:
                key = (symbol, int(ts))
            except (TypeError, ValueError):
                continue
            candles[key] = {"symbol": symbol, **row, "ts": key[1]}
    for summary_path in sorted(Path(root).rglob("summary.json")):
        if not (summary_path.parent / "bundle.tar.gz").exists():
            errors.append({"path": str(summary_path), "error": "FAILED_NO_BUNDLE"})
    candles_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (symbol, _), row in sorted(candles.items()):
        candles_by_symbol[symbol].append(row)
    return {
        "features": enrich_features(features),
        "candles_by_symbol": dict(candles_by_symbol),
        "metas": metas,
        "errors": errors,
        "truncated": truncated,
        "duplicate_features": duplicate_features,
    }


def window_bounds(now_ms: int, days: int) -> tuple[int, int]:
    end_ms = (int(now_ms) // DAY_MS) * DAY_MS
    return end_ms - int(days) * DAY_MS, end_ms


def data_quality(
    features: Sequence[dict[str, Any]],
    candles_by_symbol: dict[str, Sequence[dict[str, Any]]],
    loaded: dict[str, Any],
    *,
    start_ms: int,
    end_ms: int,
    days: int,
    bundles_dir: str | Path = "bundles",
) -> dict[str, Any]:
    observed = sorted({int(row.get("ts_ms") or 0) for row in features if start_ms <= int(row.get("ts_ms") or 0) < end_ms})
    expected = list(range(start_ms, end_ms, SLOT_MS))
    observed_set = set(observed)
    missing = [slot for slot in expected if slot not in observed_set]
    per_symbol = Counter(str(row.get("symbol", "")) for row in features)
    counts = sorted(per_symbol.values()) if per_symbol else [0]
    slots_per_day = DAY_MS // SLOT_MS
    slots_by_day = Counter(int(slot) // DAY_MS for slot in observed)
    complete_days = sum(1 for count in slots_by_day.values() if count >= slots_per_day)
    artifact_manifest_path = Path(bundles_dir) / "artifacts_manifest.json"
    artifact_errors = []
    if artifact_manifest_path.exists():
        try:
            artifact_errors = json.loads(artifact_manifest_path.read_text(encoding="utf-8")).get("errors", [])
        except (OSError, json.JSONDecodeError):
            artifact_errors = [{"error": "artifacts_manifest unreadable"}]
    status = "OK"
    if not features:
        status = "NO_DATA"
    elif missing or loaded["errors"] or loaded["truncated"] or artifact_errors:
        status = "PARTIAL"
    return {
        "status": status,
        "window_start_utc": _iso(start_ms),
        "window_end_utc": _iso(end_ms),
        "days": int(days),
        "complete_days": complete_days,
        "expected_slots": len(expected),
        "observed_slots": len(observed),
        "missing_slots_count": len(missing),
        "missing_slots_sample": [_iso(slot) for slot in missing[:200]],
        "coverage_pct": round(100.0 * len(observed) / len(expected), 4) if expected else 0.0,
        "feature_rows": len(features),
        "candle_rows": sum(len(rows) for rows in candles_by_symbol.values()),
        "symbols": len(per_symbol),
        "symbol_rows_min": counts[0] if counts else 0,
        "symbol_rows_median": statistics.median(counts) if counts else 0,
        "symbol_rows_max": counts[-1] if counts else 0,
        "duplicate_features": loaded["duplicate_features"],
        "bundle_count": len(loaded["metas"]),
        "bundle_errors": loaded["errors"],
        "truncated_bundles": loaded["truncated"],
        "artifact_errors": artifact_errors,
    }


def _split_config(days: int) -> tuple[int, int, int]:
    if days <= 3:
        return 1, 1, max(1, days - 2)
    holdout = max(1, round(days * 0.2))
    validation = max(1, round(days * 0.2))
    train = max(1, days - validation - holdout)
    return train, validation, holdout


def _split_profile(days: int, registry: dict[str, Any]) -> dict[str, Any]:
    if days <= 3:
        key = "pilot_3d"
    elif days == 30:
        key = "standard_30d"
    else:
        key = ""
    profile = (registry.get("split_profiles") or {}).get(key) if key else None
    if profile is not None:
        return profile
    train_days, validation_days, holdout_days = _split_config(days)
    configured = (registry.get("defaults") or {}).get("min_days") or {}
    return {
        "train_days": train_days,
        "validation_days": validation_days,
        "holdout_days": holdout_days,
        "min_days": {
            "pipeline": int(configured.get("pipeline", 1)),
            "validation": int(configured.get("validation", max(1, min(6, validation_days)))),
            "holdout": int(configured.get("holdout", max(1, min(6, holdout_days)))),
        },
    }


def _negative_oi_rows(features: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Record negative OI moves descriptively; they are not a tested event."""
    rows = []
    for feature in features:
        delta = _num(feature.get("oi_delta_15m_pct"))
        ret = _num(feature.get("return_15m_pct"))
        if delta is None or ret is None or delta > -2.0 or abs(ret) < 0.2:
            continue
        rows.append({
            "symbol": feature.get("symbol"),
            "ts_ms": int(feature.get("ts_ms") or 0),
            "oi_delta_15m_pct": delta,
            "return_15m_pct": ret,
            "oi_direction": "DOWN",
            "price_direction": "LONG" if ret > 0 else "SHORT",
            "oi_price_alignment": "ALIGNED" if delta * ret > 0 else "OPPOSED",
        })
    return rows


def _funding_bps(feature: dict[str, Any], direction: str, horizon_min: int) -> tuple[float | None, str]:
    rate = _num(feature.get("funding_rate"))
    if rate is None:
        return None, "MISSING"
    sign = 1.0 if direction == "LONG" else -1.0
    return sign * rate * (horizon_min / 480.0) * 10_000.0, "PROVIDED"


def _summary_for(
    items: Sequence[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    values = [
        item["net_bps"] if item.get("net_bps") is not None else item.get("net_ex_funding_bps")
        for item in items
    ]
    values = [float(value) for value in values if value is not None]
    blocks = [int(item.get("entry_ts_ms") or 0) // DAY_MS for item in items if item.get("net_bps") is not None or item.get("net_ex_funding_bps") is not None]
    summary = stats.summarise(values, blocks=blocks if len(blocks) == len(values) else None, seed=seed)
    pvalue = stats.bootstrap_pvalue(
        values, seed=seed, blocks=blocks if len(blocks) == len(values) else None
    )
    costs = {
        key: statistics.fmean([
            float(item["costs_bps"][key])
            for item in items
            if item.get("costs_bps", {}).get(key) is not None
        ]) if any(item.get("costs_bps", {}).get(key) is not None for item in items) else None
        for key in ("fee", "spread", "slippage", "funding", "total", "total_ex_funding")
    }
    mfe = [float(item["mfe_bps"]) for item in items if item.get("mfe_bps") is not None]
    mae = [float(item["mae_bps"]) for item in items if item.get("mae_bps") is not None]
    t_mfe = [float(item["time_to_mfe_min"]) for item in items if item.get("time_to_mfe_min") is not None]
    t_mae = [float(item["time_to_mae_min"]) for item in items if item.get("time_to_mae_min") is not None]
    return {
        **summary,
        "p_value": pvalue.get("p_value"),
        "raw_win_rate": (
            round(sum(1 for item in items if (item.get("gross_bps") or 0) > 0) / len(items), 6)
            if items else None
        ),
        "net_win_rate": summary.get("positive_rate"),
        "mean_gross_bps": (
            round(statistics.fmean([float(item["gross_bps"]) for item in items if item.get("gross_bps") is not None]), 6)
            if any(item.get("gross_bps") is not None for item in items) else None
        ),
        "mean_mfe_bps": round(statistics.fmean(mfe), 6) if mfe else None,
        "mean_mae_bps": round(statistics.fmean(mae), 6) if mae else None,
        "median_time_to_mfe_min": statistics.median(t_mfe) if t_mfe else None,
        "median_time_to_mae_min": statistics.median(t_mae) if t_mae else None,
        "mean_costs_bps": {key: (round(value, 6) if value is not None else None) for key, value in costs.items()},
        "funding_missing": sum(1 for item in items if item.get("funding_status") == "MISSING"),
        "fee_estimated": sum(
            1 for item in items
            if item.get("fee_status") in ("ESTIMATED", "FEE_ESTIMATED")
        ),
        "long_n": sum(1 for item in items if item.get("direction") == "LONG"),
        "short_n": sum(1 for item in items if item.get("direction") == "SHORT"),
    }


def _test_row(
    spec: dict[str, Any],
    *,
    split: str,
    horizon: int,
    bucket_dimension: str,
    bucket: str,
    items: Sequence[dict[str, Any]],
    detected: int,
    skipped_overlap: int,
    skipped_no_forward: int,
    skipped_missing_cost: int,
    seed: int,
    min_n: int,
    min_days: int,
) -> dict[str, Any]:
    summary = _summary_for(items, seed=seed)
    days = len({int(item.get("entry_ts_ms") or 0) // DAY_MS for item in items}) if items else 0
    sample_status = "OK" if summary["n"] >= min_n and days >= min_days else "INSUFFICIENT_SAMPLE"
    return {
        "spec_id": spec["spec_id"],
        "family": spec["family"],
        "split": split,
        "horizon_min": int(horizon),
        "bucket_dimension": bucket_dimension,
        "bucket": bucket,
        "detected": int(detected),
        "skipped_overlap": int(skipped_overlap),
        "skipped_no_forward": int(skipped_no_forward),
        "skipped_missing_cost": int(skipped_missing_cost),
        "days": days,
        "min_n": int(min_n),
        "min_days": int(min_days),
        "sample_status": sample_status,
        "verdict": "INSUFFICIENT_SAMPLE" if sample_status != "OK" else None,
        "q_value": None,
        **summary,
    }


def evaluate_spec(
    spec: dict[str, Any],
    events: Sequence[dict[str, Any]],
    candles_by_symbol: dict[str, Sequence[dict[str, Any]]],
    *,
    split: str,
    defaults: dict[str, Any],
    min_days: dict[str, int],
    seed: int,
    now_ms: int,
    min_n_override: int | None = None,
) -> list[dict[str, Any]]:
    split_key = "pipeline" if split == "train" else split
    min_n = max(int(spec["min_n"][split_key]), int(min_n_override or 0))
    min_days = int(min_days[split_key])
    horizons = [int(value) for value in spec["horizons_min"]]
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        scored: list[dict[str, Any]] = []
        skipped_no_forward = 0
        skipped_missing_cost = 0
        for event in events:
            feature = event.get("features") or {}
            spread = _num(feature.get("spread_bps"))
            if spread is None:
                skipped_missing_cost += 1
                continue
            fee = _num(feature.get("taker_fee_bps"))
            fee_status = "PROVIDED"
            if fee is None:
                fee = float(defaults["fee_bps_per_side"])
                fee_status = "FEE_ESTIMATED"
            funding, funding_status = _funding_bps(feature, str(event.get("direction")), horizon)
            result = outcome_module.score_event(
                event,
                candles_by_symbol.get(str(event.get("symbol")), []),
                horizon_min=horizon,
                fee_bps=fee,
                spread_bps=spread,
                slippage_bps=float(defaults["slippage_bps"]),
                funding_bps=funding,
                funding_status=funding_status,
                entry_latency_bars=int(defaults["entry_latency_bars"]),
                now_ms=now_ms,
            )
            if result is None:
                skipped_no_forward += 1
                continue
            result["event_features"] = feature
            result["event_ts_ms"] = event.get("ts_ms")
            result["fee_status"] = fee_status
            scored.append(result)
        accepted, skipped_overlap = outcome_module.select_non_overlapping(scored)
        rows.append(_test_row(
            spec, split=split, horizon=horizon, bucket_dimension="overall", bucket="all",
            items=accepted, detected=len(events), skipped_overlap=skipped_overlap,
            skipped_no_forward=skipped_no_forward, skipped_missing_cost=skipped_missing_cost,
            seed=seed, min_n=min_n, min_days=min_days,
        ))
        for dimension in spec.get("buckets", []):
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in accepted:
                groups[bucket_value(item.get("event_features") or {}, dimension)].append(item)
            for bucket, bucket_items in sorted(groups.items()):
                rows.append(_test_row(
                    spec, split=split, horizon=horizon, bucket_dimension=dimension, bucket=bucket,
                    items=bucket_items, detected=len(events), skipped_overlap=skipped_overlap,
                    skipped_no_forward=skipped_no_forward, skipped_missing_cost=skipped_missing_cost,
                    seed=seed, min_n=min_n, min_days=min_days,
                ))
    return rows


def apply_fdr(rows: Sequence[dict[str, Any]], families: dict[str, Any]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("p_value") is not None:
            grouped[(row["family"], row["split"])].append(row)
    for (family, _split), group in grouped.items():
        qvalues = stats.bh_fdr([float(row["p_value"]) for row in group])
        fdr_q = float(families[family]["fdr_q"])
        for row, qvalue in zip(group, qvalues):
            row["q_value"] = qvalue
            ci = row.get("ci") or {}
            if row["sample_status"] != "OK":
                row["verdict"] = "INSUFFICIENT_SAMPLE"
            elif qvalue <= fdr_q and ci.get("lo") is not None and ci["lo"] > 0:
                row["verdict"] = "VALIDATED"
            elif ci.get("hi") is not None and ci["hi"] < 0:
                row["verdict"] = "REJECTED"
            else:
                row["verdict"] = "INCONCLUSIVE"


LEDGER_SCHEMA_VERSION = 2
AUDIT_EVENTS = ("attempted", "completed", "results_inspected")


class LedgerError(ValueError):
    """The holdout ledger is malformed or uses an unsupported schema."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_holdout_ledger(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "evaluated_hashes": [],
            "audit": [],
        }
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"ledger is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise LedgerError("ledger must be a JSON object")
    version = data.get("schema_version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise LedgerError("ledger schema_version must be a positive integer")
    if version > LEDGER_SCHEMA_VERSION:
        raise LedgerError(f"unsupported ledger schema_version: {version}")
    hashes = data.get("evaluated_hashes", [])
    if not isinstance(hashes, list):
        raise LedgerError("ledger evaluated_hashes must be a list")
    audit = data.get("audit", [])
    if not isinstance(audit, list):
        raise LedgerError("ledger audit must be a list")
    data["schema_version"] = version
    data["audit"] = audit
    return data


def _write_holdout_ledger(path: Path, ledger: dict[str, Any]) -> None:
    payload = json.dumps(ledger, indent=2, sort_keys=True) + "\n"
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)


def _audit_entry(
    event: str,
    expected_hash: str,
    *,
    run_id: str = "",
    actor: str = "",
    detail: str = "",
    attempted_at: str = "",
) -> dict[str, Any]:
    if event not in AUDIT_EVENTS:
        raise LedgerError(f"unsupported audit event: {event}")
    entry: dict[str, Any] = {
        "event": event,
        "hash": expected_hash,
        "run_id": run_id or os.environ.get("GITHUB_RUN_ID", ""),
        "actor": actor or os.environ.get("GITHUB_ACTOR", ""),
        "recorded_at": _now_iso(),
    }
    if detail:
        entry["detail"] = detail
    if attempted_at:
        entry["attempted_at"] = attempted_at
    return entry


def preflight_holdout(
    *,
    registry: dict[str, Any],
    requested_hash: str,
    days: int,
) -> str:
    expected_hash = registry_hash(registry)
    if not requested_hash:
        raise LedgerError("registry_hash is required for holdout confirmation")
    if requested_hash != expected_hash:
        raise LedgerError(
            f"registry hash mismatch: computed {expected_hash}, requested {requested_hash}"
        )
    minimum = int(registry["holdout"]["unlock_after_days"])
    if int(days) < minimum:
        raise LedgerError(f"holdout requires at least {minimum} complete days")
    return expected_hash


def should_open_ledger_pr(
    mode: str | None,
    *,
    token_ok: bool,
    push_ok: bool,
) -> bool:
    return (mode or "").strip().lower() != "app" or not token_ok or not push_ok


def _holdout_status(
    *,
    days: int,
    observed_days: int,
    complete_days: int | None = None,
    registry: dict[str, Any],
    confirm_holdout: bool,
    spec_hash: str,
    unlock_at: str,
    ledger_path: str,
) -> tuple[str, str | None]:
    policy = registry["holdout"]
    expected_hash = registry_hash(registry)
    usable_days = observed_days if complete_days is None else complete_days
    if usable_days < int(policy["unlock_after_days"]):
        return "LOCKED_INSUFFICIENT_DAYS", expected_hash
    if not confirm_holdout:
        return "LOCKED_AWAITING_AUTHORIZATION", expected_hash
    if not spec_hash or spec_hash != expected_hash:
        return "LOCKED_HASH_MISMATCH", expected_hash
    unlock_date = _parse_date(unlock_at)
    if unlock_date is None or _utc_today() < unlock_date:
        return "LOCKED_AWAITING_UNLOCK_DATE", expected_hash
    if not ledger_path:
        return "LOCKED_LEDGER_REQUIRED", expected_hash
    if Path(ledger_path).exists():
        try:
            ledger = _read_holdout_ledger(ledger_path)
            if expected_hash in (ledger.get("evaluated_hashes") or []):
                return "LOCKED_ALREADY_EVALUATED", expected_hash
        except (OSError, LedgerError):
            return "LOCKED_LEDGER_UNREADABLE", expected_hash
    return "UNLOCKED", expected_hash


def ensure_linux_ci() -> None:
    """Production holdout execution is authorized only on Linux CI."""
    if os.environ.get("CI") != "true" or os.environ.get("RUNNER_OS") != "Linux":
        raise LedgerError(
            "production holdout execution is restricted to Linux CI; "
            "local Windows execution is not authorized"
        )


def validate_holdout_environment(payload: dict[str, Any]) -> None:
    """Reject a missing or weakly protected phase-b-holdout environment."""
    if not isinstance(payload, dict):
        raise LedgerError("environment response must be a JSON object")
    if payload.get("name") != "phase-b-holdout":
        raise LedgerError("phase-b-holdout environment is missing or misnamed")
    rules = payload.get("protection_rules") or []
    if not isinstance(rules, list):
        raise LedgerError("environment protection_rules must be a list")
    reviewer_rules = [
        rule for rule in rules
        if isinstance(rule, dict) and rule.get("type") == "required_reviewers"
    ]
    if not reviewer_rules:
        raise LedgerError("phase-b-holdout has no required reviewers")
    reviewers = reviewer_rules[0].get("reviewers") or []
    if not isinstance(reviewers, list) or not reviewers:
        raise LedgerError("phase-b-holdout required reviewers list is empty")
    if not all(rule.get("prevent_self_review") is True for rule in reviewer_rules):
        raise LedgerError("phase-b-holdout must prevent self-review")
    if payload.get("can_admins_bypass") is not False:
        raise LedgerError("phase-b-holdout must disallow administrator bypass")


def _pr_hashes(pr: dict[str, Any]) -> set[str]:
    text = f"{pr.get('title') or ''} {pr.get('body') or ''}"
    return set(re.findall(r"\b[0-9a-f]{64}\b", text.lower()))


def holdout_pr_gate(
    *,
    open_prs: Sequence[dict[str, Any]],
    closed_prs: Sequence[dict[str, Any]],
    requested_hash: str,
    retry_authorization: str = "",
    ledger_hashes: Sequence[str] = (),
    max_prs: int = 1000,
) -> str:
    """Fail closed unless PR history and ledger state permit this evaluation."""
    if not requested_hash:
        raise LedgerError("registry_hash is required for holdout PR checks")
    if not isinstance(open_prs, list) or not isinstance(closed_prs, list):
        raise LedgerError("holdout PR data must be JSON lists")
    if len(open_prs) >= max_prs or len(closed_prs) >= max_prs:
        raise LedgerError("holdout PR history is truncated; manual review is required")
    if open_prs:
        labels = ", ".join(
            f"#{pr.get('number')} {pr.get('headRefName', '')}" for pr in open_prs
        )
        raise LedgerError(f"pending holdout ledger PR(s): {labels}")
    if requested_hash in {str(value) for value in ledger_hashes}:
        raise LedgerError("holdout hash is already recorded in the ledger")

    merged = [pr for pr in closed_prs if pr.get("mergedAt")]
    abandoned = [pr for pr in closed_prs if not pr.get("mergedAt")]
    known = {str(value) for value in ledger_hashes}
    unhashed = [pr for pr in merged if not _pr_hashes(pr)]
    if unhashed:
        labels = ", ".join(f"#{pr.get('number')}" for pr in unhashed)
        raise LedgerError(
            f"merged legacy ledger PR(s) {labels} have no experiment hash; "
            "manual ledger audit is required before another evaluation"
        )
    unrecorded = [
        pr for pr in merged
        if not (_pr_hashes(pr) & known)
    ]
    if unrecorded:
        labels = ", ".join(f"#{pr.get('number')}" for pr in unrecorded)
        raise LedgerError(
            f"merged ledger PR(s) {labels} reference a hash absent from the ledger; "
            "manual ledger repair is required before another evaluation"
        )
    if abandoned:
        if retry_authorization != requested_hash:
            labels = ", ".join(f"#{pr.get('number')}" for pr in abandoned)
            raise LedgerError(
                f"closed unmerged ledger PR(s) {labels} exist, including legacy "
                "PRs without a hash; retry_authorization must equal the exact "
                "frozen registry hash and the phase-b-holdout reviewers must approve"
            )
        return "RETRY_AUTHORIZED"
    return "CLEAR"


def verify_holdout_state(
    *,
    registry: dict[str, Any],
    spec_hash: str,
    unlock_at: str,
    ledger_path: str,
    days: int,
) -> str:
    """Recheck the frozen hash and ledger immediately before evaluation."""
    expected = preflight_holdout(
        registry=registry, requested_hash=spec_hash, days=days
    )
    if not ledger_path or not Path(ledger_path).exists():
        raise LedgerError("holdout ledger is missing")
    status, _ = _holdout_status(
        days=days,
        observed_days=days,
        registry=registry,
        confirm_holdout=True,
        spec_hash=expected,
        unlock_at=unlock_at,
        ledger_path=ledger_path,
    )
    if status != "UNLOCKED":
        raise LedgerError(f"holdout state is {status}")
    return status


def verify_holdout_result(
    *,
    registry: dict[str, Any],
    spec_hash: str,
    ledger_path: str,
    result_dir: str | Path,
    days: int,
) -> dict[str, Any]:
    """Recheck the hash, ledger, and result immediately before recording."""
    expected = preflight_holdout(
        registry=registry, requested_hash=spec_hash, days=days
    )
    if not ledger_path or not Path(ledger_path).exists():
        raise LedgerError("holdout ledger is missing")
    ledger = _read_holdout_ledger(ledger_path)
    if expected in (ledger.get("evaluated_hashes") or []):
        raise LedgerError("holdout hash is already recorded")
    result_path = Path(result_dir)
    status_path = result_path / "holdout_status.json"
    quality_path = result_path / "data_quality.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"holdout result is unreadable: {exc}") from exc
    errors = []
    if status.get("status") != "UNLOCKED":
        errors.append(f"holdout status is {status.get('status')}")
    if status.get("complete") is not True:
        errors.append("holdout result is not complete")
    if status.get("quality_status") != "OK" or quality.get("status") != "OK":
        errors.append("data quality is not OK")
    if int(status.get("holdout_rows") or 0) <= 0:
        errors.append("no holdout rows")
    if int(status.get("insufficient_overall_holdout_rows") or 0) != 0:
        errors.append("holdout has insufficient overall rows")
    if status.get("registry_hash") != expected:
        errors.append("registry hash does not match the approved hash")
    if errors:
        raise LedgerError("; ".join(errors))
    return status


def _append_holdout_ledger(
    path: str | Path,
    expected_hash: str,
    *,
    attempted_at: str = "",
    run_id: str = "",
) -> bool:
    """Append a completed hash and its audit entries atomically."""
    if not expected_hash:
        raise LedgerError("holdout hash is required")
    ledger_path = Path(path)
    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            ledger = _read_holdout_ledger(ledger_path)
            hashes = [str(value) for value in (ledger.get("evaluated_hashes") or [])]
            if expected_hash in hashes:
                return False
            ledger["schema_version"] = LEDGER_SCHEMA_VERSION
            ledger["evaluated_hashes"] = sorted({*hashes, expected_hash})
            ledger["audit"].append(_audit_entry(
                "attempted", expected_hash, run_id=run_id, attempted_at=attempted_at
            ))
            ledger["audit"].append(_audit_entry(
                "completed", expected_hash, run_id=run_id, attempted_at=attempted_at
            ))
            _write_holdout_ledger(ledger_path, ledger)
            return True
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _append_holdout_audit(
    path: str | Path,
    event: str,
    expected_hash: str,
    *,
    run_id: str = "",
    actor: str = "",
    detail: str = "",
    attempted_at: str = "",
) -> dict[str, Any]:
    """Append an audit event without changing the completed-hash set."""
    if not expected_hash:
        raise LedgerError("holdout hash is required")
    if event not in AUDIT_EVENTS:
        raise LedgerError(f"unsupported audit event: {event}")
    ledger_path = Path(path)
    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            ledger = _read_holdout_ledger(ledger_path)
            hashes = [str(value) for value in (ledger.get("evaluated_hashes") or [])]
            if event in ("completed", "results_inspected") and expected_hash not in hashes:
                raise LedgerError(f"{event} requires a recorded holdout hash")
            entry = _audit_entry(
                event, expected_hash, run_id=run_id, actor=actor,
                detail=detail, attempted_at=attempted_at,
            )
            ledger["schema_version"] = LEDGER_SCHEMA_VERSION
            ledger["audit"].append(entry)
            _write_holdout_ledger(ledger_path, ledger)
            return entry
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _holdout_complete(
    status: str,
    quality_status: str,
    holdout_rows: Sequence[dict[str, Any]],
) -> bool:
    """A hash is consumed only when every overall holdout test is powered.

    Bucket rows remain diagnostic. Requiring every rare bucket to be powered
    would let one sparse slice block a valid overall holdout indefinitely.
    """
    overall = [
        row for row in holdout_rows
        if row.get("bucket_dimension") == "overall"
    ]
    return bool(
        status == "UNLOCKED"
        and quality_status == "OK"
        and overall
        and all(row.get("sample_status") == "OK" for row in overall)
    )


def _render_report(
    *,
    quality: dict[str, Any],
    holdout: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    registry: dict[str, Any],
) -> str:
    lines = [
        "# Phase B nightly research evaluation",
        "",
        f"- Data status: **{quality['status']}**",
        f"- Window: {quality['window_start_utc']} to {quality['window_end_utc']}",
        f"- Bundles: {quality['bundle_count']}; feature rows: {quality['feature_rows']}; symbols: {quality['symbols']}",
        f"- Slots observed/expected: {quality['observed_slots']}/{quality['expected_slots']} ({quality['coverage_pct']}%)",
        f"- Missing slots: {quality['missing_slots_count']}",
        f"- Complete UTC days: {holdout.get('complete_days')}",
        f"- Holdout: **{holdout['status']}**",
        "",
        "## Data quality",
        "",
        f"- Bundle errors: {len(quality['bundle_errors'])}",
        f"- Truncated bundles: {len(quality['truncated_bundles'])}",
        f"- Artifact errors: {len(quality['artifact_errors'])}",
        f"- Duplicate features: {quality['duplicate_features']}",
        "",
        "## Results",
        "",
        "All pre-registered tests are shown, including insufficient and negative results.",
        "",
        "| Spec | Split | H | Bucket | n | Days | Win% | Mean net bps | Median | 95% CI | p | q | Status | Verdict |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|",
    ]
    for row in sorted(rows, key=lambda item: (item["family"], item["split"], item["spec_id"], item["horizon_min"], item["bucket_dimension"], item["bucket"])):
        ci = row.get("ci") or {}
        lines.append(
            f"| {row['spec_id']} | {row['split']} | {row['horizon_min']} | "
            f"{row['bucket_dimension']}={row['bucket']} | {row.get('n')} | {row['days']} | "
            f"{row.get('net_win_rate')} | {row.get('mean')} | {row.get('median')} | "
            f"[{ci.get('lo')}, {ci.get('hi')}] | {row.get('p_value')} | {row.get('q_value')} | "
            f"{row['sample_status']} | {row['verdict']} |"
        )
    lines += [
        "",
        "## Risk and cost detail",
        "",
        "| Spec | Split | H | n | MFE bps | MAE bps | T-MFE min | T-MAE min | Fee | Spread | Slip | Funding | Funding missing |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: (item["split"], item["spec_id"], item["horizon_min"], item["bucket_dimension"], item["bucket"])):
        costs = row.get("mean_costs_bps") or {}
        lines.append(
            f"| {row['spec_id']} | {row['split']} | {row['horizon_min']} | {row.get('n')} | "
            f"{row.get('mean_mfe_bps')} | {row.get('mean_mae_bps')} | {row.get('median_time_to_mfe_min')} | "
            f"{row.get('median_time_to_mae_min')} | {costs.get('fee')} | {costs.get('spread')} | "
            f"{costs.get('slippage')} | {costs.get('funding')} | {row.get('funding_missing')} |"
        )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "- These are conditional associations on historical data, not proof of profitability.",
        "- Net results subtract fees, entry spread, slippage and funding where available.",
        "- Directional accuracy alone is not a profitability claim; sample size, effect size and costs matter.",
        "- The holdout is not evaluated while locked. Do not tune against it.",
        "",
        "## Frozen specifications",
        "",
    ]
    for spec in registry["specs"]:
        lines.append(f"- **{spec['spec_id']}**: {spec['hypothesis']} Params: `{json.dumps(spec['params'], sort_keys=True)}`")
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    *,
    out_dir: str | Path,
    quality: dict[str, Any],
    holdout: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    registry: dict[str, Any],
    loaded: dict[str, Any],
    negative_oi: Sequence[dict[str, Any]] = (),
) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": quality["status"],
        "window_start_utc": quality["window_start_utc"],
        "window_end_utc": quality["window_end_utc"],
        "days": quality["days"],
        "complete_days": quality.get("complete_days"),
        "bundles": quality["bundle_count"],
        "feature_rows": quality["feature_rows"],
        "candle_rows": quality["candle_rows"],
        "symbols": quality["symbols"],
        "expected_slots": quality["expected_slots"],
        "observed_slots": quality["observed_slots"],
        "missing_slots": quality["missing_slots_count"],
        "holdout": holdout,
        "tests": len(rows),
        "validated": sum(1 for row in rows if row["verdict"] == "VALIDATED"),
        "rejected": sum(1 for row in rows if row["verdict"] == "REJECTED"),
        "insufficient": sum(1 for row in rows if row["verdict"] == "INSUFFICIENT_SAMPLE"),
        "inconclusive": sum(1 for row in rows if row["verdict"] == "INCONCLUSIVE"),
        "negative_oi_diagnostics": len(negative_oi),
        "registry_hash": registry_hash(registry),
        "registry_version": registry["registry_version"],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "data_quality.json").write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "holdout_status.json").write_text(json.dumps(holdout, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out / "oi_negative.jsonl").open("w", encoding="utf-8") as handle:
        for row in negative_oi:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (out / "oi_negative_summary.json").write_text(
        json.dumps({"rows": len(negative_oi)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "report.md").write_text(
        _render_report(quality=quality, holdout=holdout, rows=rows, registry=registry),
        encoding="utf-8",
    )
    fields = [
        "family", "spec_id", "split", "horizon_min", "bucket_dimension", "bucket",
        "n", "days", "detected", "skipped_overlap", "skipped_no_forward", "skipped_missing_cost",
        "net_win_rate", "raw_win_rate", "mean", "median", "p10", "p90",
        "mean_gross_bps", "mean_mfe_bps", "mean_mae_bps",
        "median_time_to_mfe_min", "median_time_to_mae_min",
        "p_value", "q_value", "sample_status", "verdict", "min_n", "min_days",
        "long_n", "short_n", "funding_missing", "fee_estimated",
    ]
    with (out / "spec_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (item["family"], item["split"], item["spec_id"], item["horizon_min"], item["bucket_dimension"], item["bucket"])):
            writer.writerow(row)
    manifest = {
        "registry_hash": registry_hash(registry),
        "registry_version": registry["registry_version"],
        "code_sha": os.getenv("GITHUB_SHA", ""),
        "window_start_utc": quality["window_start_utc"],
        "window_end_utc": quality["window_end_utc"],
        "bundles": loaded["metas"],
        "artifact_errors": quality["artifact_errors"],
        "truncated_bundles": quality["truncated_bundles"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"summary": str(out / "summary.json"), "report": str(out / "report.md")}


def evaluate_window(
    *,
    bundles_dir: str | Path,
    days: int = 3,
    out_dir: str | Path,
    registry: dict[str, Any],
    now_ms: int | None = None,
    seed: int = 0,
    min_n_override: int | None = None,
    confirm_holdout: bool = False,
    spec_hash: str = "",
    holdout_unlock_at: str = "",
    holdout_ledger: str = "",
) -> dict[str, Any]:
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    start_ms, end_ms = window_bounds(now, days)
    loaded = load_bundles(bundles_dir)
    features = [row for row in loaded["features"] if start_ms <= int(row.get("ts_ms") or 0) < end_ms]
    candles_by_symbol = loaded["candles_by_symbol"]
    quality = data_quality(
        features, candles_by_symbol, loaded, start_ms=start_ms, end_ms=end_ms, days=days,
        bundles_dir=bundles_dir,
    )
    observed_days = len({int(row.get("ts_ms") or 0) // DAY_MS for row in features})
    holdout_status, expected_hash = _holdout_status(
        days=days,
        observed_days=observed_days,
        complete_days=int(quality.get("complete_days") or 0),
        registry=registry,
        confirm_holdout=confirm_holdout,
        spec_hash=spec_hash,
        unlock_at=holdout_unlock_at,
        ledger_path=holdout_ledger,
    )
    holdout = {
        "status": holdout_status,
        "complete_days": int(quality.get("complete_days") or 0),
        "unlock_after_days": registry["holdout"]["unlock_after_days"],
        "unlock_at": registry["holdout"]["unlock_at"],
        "requires": registry["holdout"]["requires"],
        "evaluated": False,
        "complete": False,
        "quality_status": quality["status"],
        "holdout_rows": 0,
        "insufficient_holdout_rows": 0,
        "insufficient_overall_holdout_rows": 0,
        "insufficient_bucket_holdout_rows": 0,
        "registry_hash": expected_hash,
        "audit_event": "attempted",
        "attempted_at": _now_iso(),
        "attempted_by": os.environ.get("GITHUB_ACTOR", ""),
        "attempted_run_id": os.environ.get("GITHUB_RUN_ID", ""),
    }
    negative_oi = _negative_oi_rows(features)
    rows: list[dict[str, Any]] = []
    holdout_rows: list[dict[str, Any]] = []
    if features:
        profile = _split_profile(days, registry)
        defaults = registry["defaults"]
        for family in registry["families"]:
            for spec in specs_for_family(registry, family):
                detected = event_module.dedupe(
                    event_module.detect_all(features, spec["event_type"], spec["params"]),
                    min_gap_ms=int(defaults["dedupe_ms"]),
                )
                split = split_30d(
                    [event.as_dict() for event in detected],
                    start_ms,
                    train_days=int(profile["train_days"]),
                    validation_days=int(profile["validation_days"]),
                    test_days=int(profile["holdout_days"]),
                    embargo_minutes=60,
                    max_horizon_min=max(int(value) for value in spec["horizons_min"]),
                    feature_lookback_min=int(defaults.get("feature_lookback_min", 64)),
                )
                for split_name in ("train", "validation"):
                    rows.extend(evaluate_spec(
                        spec, split[split_name], candles_by_symbol,
                        split=split_name, defaults=defaults,
                        min_days=profile["min_days"], seed=seed,
                        now_ms=end_ms, min_n_override=min_n_override,
                    ))
                if holdout_status == "UNLOCKED":
                    holdout_rows.extend(evaluate_spec(
                        spec, split["test"], candles_by_symbol,
                        split="holdout", defaults=defaults,
                        min_days=profile["min_days"], seed=seed,
                        now_ms=end_ms, min_n_override=min_n_override,
                    ))
        rows.extend(holdout_rows)
        apply_fdr(rows, registry["families"])
    insufficient_holdout = sum(
        1 for row in holdout_rows if row.get("sample_status") != "OK"
    )
    insufficient_overall = sum(
        1 for row in holdout_rows
        if row.get("bucket_dimension") == "overall"
        and row.get("sample_status") != "OK"
    )
    insufficient_bucket = sum(
        1 for row in holdout_rows
        if row.get("bucket_dimension") != "overall"
        and row.get("sample_status") != "OK"
    )
    holdout_complete = _holdout_complete(
        holdout_status, str(quality["status"]), holdout_rows
    )
    holdout.update({
        "evaluated": holdout_complete,
        "complete": holdout_complete,
        "quality_status": quality["status"],
        "holdout_rows": len(holdout_rows),
        "insufficient_holdout_rows": insufficient_holdout,
        "insufficient_overall_holdout_rows": insufficient_overall,
        "insufficient_bucket_holdout_rows": insufficient_bucket,
    })
    write_outputs(
        out_dir=out_dir, quality=quality, holdout=holdout, rows=rows,
        registry=registry, loaded=loaded, negative_oi=negative_oi,
    )
    return {"quality": quality, "holdout": holdout, "rows": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate frozen Phase B specs")
    parser.add_argument("--bundles", default="bundles")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--out", default=None)
    parser.add_argument("--registry", default=None)
    parser.add_argument("--fdr-q", type=float, default=None)
    parser.add_argument("--min-n", type=int, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--confirm-holdout", action="store_true")
    parser.add_argument("--spec-hash", default="")
    parser.add_argument("--holdout-unlock-at", default="")
    parser.add_argument("--holdout-ledger", default="")
    parser.add_argument("--open-prs", default="")
    parser.add_argument("--closed-prs", default="")
    parser.add_argument("--retry-authorization", default="")
    parser.add_argument("--check-holdout-prs", action="store_true")
    parser.add_argument("--environment-json", default="")
    parser.add_argument("--verify-holdout-environment", action="store_true")
    parser.add_argument("--preflight-holdout", action="store_true")
    parser.add_argument("--verify-holdout-state", action="store_true")
    parser.add_argument("--verify-holdout-result", action="store_true")
    parser.add_argument("--holdout-result", default="")
    parser.add_argument("--record-holdout", default="")
    parser.add_argument("--record-audit", default="")
    parser.add_argument("--audit-event", choices=AUDIT_EVENTS, default="")
    parser.add_argument("--audit-actor", default="")
    parser.add_argument("--audit-detail", default="")
    parser.add_argument("--attempted-at", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--holdout-hash", default="")
    parser.add_argument("--require-linux-ci", action="store_true")
    parser.add_argument("--now-ms", type=int, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    if args.require_linux_ci:
        try:
            ensure_linux_ci()
        except LedgerError as exc:
            parser.error(str(exc))
    if args.check_holdout_prs:
        if not args.open_prs or not args.closed_prs:
            parser.error("--open-prs and --closed-prs are required with --check-holdout-prs")
        try:
            open_prs = json.loads(Path(args.open_prs).read_text(encoding="utf-8"))
            closed_prs = json.loads(Path(args.closed_prs).read_text(encoding="utf-8"))
            ledger_hashes: list[str] = []
            if args.holdout_ledger:
                ledger_path = Path(args.holdout_ledger)
                if not ledger_path.exists():
                    raise LedgerError("holdout ledger is missing")
                ledger_hashes = [
                    str(value) for value in
                    (_read_holdout_ledger(ledger_path).get("evaluated_hashes") or [])
                ]
            result = holdout_pr_gate(
                open_prs=open_prs,
                closed_prs=closed_prs,
                requested_hash=args.spec_hash,
                retry_authorization=args.retry_authorization,
                ledger_hashes=ledger_hashes,
            )
        except (OSError, json.JSONDecodeError, LedgerError) as exc:
            parser.error(str(exc))
        print(result)
        return 0
    if args.verify_holdout_environment:
        if not args.environment_json:
            parser.error("--environment-json is required with --verify-holdout-environment")
        try:
            payload = json.loads(Path(args.environment_json).read_text(encoding="utf-8"))
            validate_holdout_environment(payload)
        except (OSError, json.JSONDecodeError, LedgerError) as exc:
            parser.error(str(exc))
        print("phase-b-holdout protection verified")
        return 0
    if args.preflight_holdout:
        registry = load_registry(args.registry)
        try:
            expected = preflight_holdout(
                registry=registry,
                requested_hash=args.spec_hash,
                days=args.days,
            )
        except LedgerError as exc:
            parser.error(str(exc))
        print(expected)
        return 0
    if args.verify_holdout_state:
        registry = load_registry(args.registry)
        try:
            status = verify_holdout_state(
                registry=registry,
                spec_hash=args.spec_hash,
                unlock_at=args.holdout_unlock_at,
                ledger_path=args.holdout_ledger,
                days=args.days,
            )
        except LedgerError as exc:
            parser.error(str(exc))
        print(status)
        return 0
    if args.verify_holdout_result:
        if not args.holdout_result:
            parser.error("--holdout-result is required with --verify-holdout-result")
        registry = load_registry(args.registry)
        try:
            status = verify_holdout_result(
                registry=registry,
                spec_hash=args.spec_hash,
                ledger_path=args.holdout_ledger,
                result_dir=args.holdout_result,
                days=args.days,
            )
        except LedgerError as exc:
            parser.error(str(exc))
        print(json.dumps({
            "complete": status.get("complete"),
            "hash": status.get("registry_hash"),
            "insufficient_bucket_holdout_rows": status.get("insufficient_bucket_holdout_rows", 0),
            "status": status.get("status"),
        }, sort_keys=True))
        return 0
    if args.record_audit:
        if not args.audit_event:
            parser.error("--audit-event is required with --record-audit")
        if not args.holdout_hash:
            parser.error("--holdout-hash is required with --record-audit")
        entry = _append_holdout_audit(
            args.record_audit,
            args.audit_event,
            args.holdout_hash,
            run_id=args.run_id,
            actor=args.audit_actor,
            detail=args.audit_detail,
            attempted_at=args.attempted_at,
        )
        print(json.dumps(entry, sort_keys=True))
        return 0
    if args.record_holdout:
        if not args.holdout_hash:
            parser.error("--holdout-hash is required with --record-holdout")
        added = _append_holdout_ledger(
            args.record_holdout,
            args.holdout_hash,
            attempted_at=args.attempted_at,
            run_id=args.run_id,
        )
        print(json.dumps({"added": added, "hash": args.holdout_hash}, sort_keys=True))
        return 0
    if not args.out:
        parser.error("--out is required unless a holdout maintenance mode is used")
    registry = load_registry(args.registry)
    if args.fdr_q is not None:
        for family in registry["families"].values():
            family["fdr_q"] = float(args.fdr_q)
    result = evaluate_window(
        bundles_dir=args.bundles,
        days=args.days,
        out_dir=args.out,
        registry=registry,
        now_ms=args.now_ms,
        seed=args.seed,
        min_n_override=args.min_n,
        confirm_holdout=args.confirm_holdout,
        spec_hash=args.spec_hash,
        holdout_unlock_at=args.holdout_unlock_at,
        holdout_ledger=args.holdout_ledger,
    )
    if not args.quiet:
        print(json.dumps({
            "status": result["quality"]["status"],
            "holdout": result["holdout"]["status"],
            "tests": len(result["rows"]),
            "insufficient": sum(1 for row in result["rows"] if row["verdict"] == "INSUFFICIENT_SAMPLE"),
        }, sort_keys=True))
    if result["quality"]["status"] == "NO_DATA":
        print("::warning::Phase B evaluation found no usable bundles")
    elif result["quality"]["status"] == "PARTIAL":
        print("::warning::Phase B evaluation is partial; see data_quality.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
