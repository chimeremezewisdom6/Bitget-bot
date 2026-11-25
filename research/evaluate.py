"""Evaluate one pre-registered experiment on a leakage-safe 30-day split."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from . import events as event_module
from . import outcomes as outcome_module
from . import stats
from .dataset import split_30d


def _bucket(row: dict[str, Any]) -> str:
    flag = row.get("flag_0_7")
    if flag is True:
        return "volatility_flagged"
    if flag is False:
        return "volatility_normal"
    return "volatility_unknown"


def _aggregate(rows: Sequence[dict[str, Any]], event_type: str, params: dict[str, Any] | None,
               candles_by_symbol: dict[str, Sequence[Any]], horizons: Sequence[int],
               fee_bps: float, now_ms: int, seed: int = 0) -> dict[str, Any]:
    detected = event_module.dedupe(
        event_module.detect_all(rows, event_type, params),
        min_gap_ms=3_600_000,
    )
    scored = outcome_module.score_events(
        detected, candles_by_symbol, horizons=horizons, fee_bps=fee_bps, now_ms=now_ms
    )
    result: dict[str, Any] = {
        "events": len(detected),
        "outcomes": len(scored),
        "by_horizon": {},
        "by_bucket": {},
    }
    days = {row.get("ts_ms", 0) // 86_400_000 for row in rows}
    result["days"] = len(days)
    for horizon in horizons:
        values = [item["net_bps"] for item in scored if item["horizon_min"] == horizon]
        summary = stats.summarise(values, seed=seed)
        result["by_horizon"][str(horizon)] = summary
    for bucket in ("volatility_flagged", "volatility_normal", "volatility_unknown"):
        bucket_rows = [row for row in rows if _bucket(row) == bucket]
        bucket_events = event_module.dedupe(
            event_module.detect_all(bucket_rows, event_type, params),
            min_gap_ms=3_600_000,
        )
        bucket_scored = outcome_module.score_events(
            bucket_events, candles_by_symbol, horizons=horizons, fee_bps=fee_bps, now_ms=now_ms
        )
        result["by_bucket"][bucket] = {
            "events": len(bucket_events),
            "by_horizon": {
                str(horizon): stats.summarise(
                    [item["net_bps"] for item in bucket_scored if item["horizon_min"] == horizon],
                    seed=seed,
                )
                for horizon in horizons
            },
        }
    return result


def evaluate(
    spec: dict[str, Any],
    features: Sequence[dict[str, Any]],
    candles_by_symbol: dict[str, Sequence[Any]],
    *,
    start_ms: int,
    fee_bps: float = 6.0,
    seed: int = 0,
) -> dict[str, Any]:
    split_cfg = spec.get("split") or {}
    split = split_30d(
        features,
        start_ms,
        train_days=int(split_cfg.get("train_days", 15)),
        validation_days=int(split_cfg.get("validation_days", 7)),
        test_days=int(split_cfg.get("test_days", 8)),
        embargo_minutes=int(split_cfg.get("embargo_minutes", 60)),
        max_horizon_min=max((spec.get("outcomes") or {}).get("horizons", [60])),
    )
    event_cfg = spec.get("event") or {}
    horizons = (spec.get("outcomes") or {}).get("horizons", [5, 15, 30, 60])
    decision = spec.get("decision") or {}
    total_days = (
        int(split_cfg.get("train_days", 15))
        + int(split_cfg.get("validation_days", 7))
        + int(split_cfg.get("test_days", 8))
    )
    end_ms = start_ms + total_days * 86_400_000
    metrics: dict[str, Any] = {
        "experiment_id": spec.get("id"),
        "version": spec.get("version"),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "fee_bps": fee_bps,
        "event_type": event_cfg.get("type"),
        "split_sizes": {name: len(rows) for name, rows in split.items()},
        "splits": {},
    }
    for name, rows in split.items():
        aggregate = _aggregate(
            rows, event_cfg.get("type"), event_cfg.get("params"),
            candles_by_symbol, horizons, fee_bps, end_ms, seed,
        )
        for horizon, summary in aggregate["by_horizon"].items():
            summary["verdict"] = stats.verdict(
                n=summary.get("n") or 0,
                days=aggregate["days"],
                ci=summary.get("ci") or {},
                lift_bps=None,
                q_value=None,
                min_events=int(decision.get("min_events", 200)),
                min_days=int(decision.get("min_days", 10)),
                fdr_q=float(decision.get("fdr_q", 0.10)),
            )
        metrics["splits"][name] = aggregate
    return metrics


def render_report(metrics: dict[str, Any]) -> str:
    lines = [
        f"# Experiment {metrics.get('experiment_id')} v{metrics.get('version')}",
        "",
        f"- Event type: `{metrics.get('event_type')}`",
        f"- Fee assumption: {metrics.get('fee_bps')} bps per side",
        f"- Split sizes: {json.dumps(metrics.get('split_sizes'), sort_keys=True)}",
        "",
    ]
    for name, aggregate in metrics.get("splits", {}).items():
        lines += [f"## {name}", "", f"- Events: {aggregate['events']}", f"- Days: {aggregate['days']}", ""]
        lines += ["| Horizon | n | Mean net bps | 95% CI | Positive rate | Profit factor | Verdict |",
                  "|---:|---:|---:|---|---:|---:|---|"]
        for horizon, summary in aggregate.get("by_horizon", {}).items():
            ci = summary.get("ci") or {}
            lines.append(
                f"| {horizon} | {summary.get('n')} | {summary.get('mean')} "
                f"| [{ci.get('lo')}, {ci.get('hi')}] | {summary.get('positive_rate')} "
                f"| {summary.get('profit_factor')} | {summary.get('verdict')} |"
            )
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "- These are conditional associations on historical data, not causal proof.",
        "- Net results subtract fees, spread, slippage and funding assumptions.",
        "- Test results are reported once; re-tuning requires a new experiment ID.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(metrics: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    metrics_path = out / "metrics.json"
    report_path = out / "report.md"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(metrics), encoding="utf-8")
    return {"metrics": str(metrics_path), "report": str(report_path)}
