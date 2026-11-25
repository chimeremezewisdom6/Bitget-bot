"""Phase B data-quality watchdog. It reports gaps; it never fabricates data."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .artifacts import UrllibTransport, download_bundles

SLOT_MS = 300_000


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(int(ts_ms) / 1000.0, timezone.utc).isoformat()


def _ms(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def classify(
    summaries: Sequence[dict[str, Any]],
    *,
    now_ms: int,
    stale_minutes: int = 15,
    window_minutes: int = 60,
) -> dict[str, Any]:
    window_start = int(now_ms) - int(window_minutes) * 60_000
    slots = sorted({_ms(item.get("slot_ms")) for item in summaries if _ms(item.get("slot_ms")) >= window_start})
    expected = max(1, int(window_minutes) // 5)
    missing = max(0, expected - len(slots))
    latest_ms = max(slots) if slots else 0
    age_minutes = (int(now_ms) - latest_ms) / 60_000.0 if latest_ms else None
    failed = [item for item in summaries if item.get("outcome") == "failed"]
    partial = [item for item in summaries if item.get("outcome") == "partial"]
    truncated = [
        item for item in summaries
        if ((item.get("manifest") or {}).get("quality") or {}).get("truncated_sections")
    ]
    degraded = []
    delayed = []
    for item in summaries:
        ok = _ms(item.get("symbols_ok"))
        failed_symbols = _ms(item.get("symbols_failed"))
        total = ok + failed_symbols
        if total and ok / total < 0.8:
            degraded.append(item)
        started = _ms(item.get("started_ms"))
        slot = _ms(item.get("slot_ms"))
        finished = _ms(item.get("finished_ms"))
        duration = finished - started if finished else 0
        if (slot and started and started - slot > 60_000) or duration > 240_000:
            delayed.append(item)
    if not summaries:
        status = "NO_DATA"
    elif age_minutes is not None and age_minutes > stale_minutes:
        status = "STALE"
    elif missing:
        status = "MISSING"
    elif failed or partial:
        status = "INCOMPLETE"
    elif truncated:
        status = "TRUNCATED"
    elif degraded:
        status = "DEGRADED"
    elif delayed:
        status = "DELAYED"
    else:
        status = "OK"
    return {
        "status": status,
        "now_utc": _iso(now_ms),
        "latest_slot_utc": _iso(latest_ms) if latest_ms else None,
        "latest_age_minutes": round(age_minutes, 3) if age_minutes is not None else None,
        "window_minutes": int(window_minutes),
        "expected_slots": expected,
        "observed_slots": len(slots),
        "missing_slots": missing,
        "failed_collections": len(failed),
        "partial_collections": len(partial),
        "truncated_bundles": len(truncated),
        "degraded_collections": len(degraded),
        "delayed_collections": len(delayed),
        "examples": {
            "failed": [item.get("slot") for item in failed[:5]],
            "partial": [item.get("slot") for item in partial[:5]],
            "truncated": [item.get("slot") for item in truncated[:5]],
            "degraded": [item.get("slot") for item in degraded[:5]],
            "delayed": [item.get("slot") for item in delayed[:5]],
        },
    }


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "# Phase B data watchdog",
        "",
        f"- Status: **{result['status']}**",
        f"- Checked at: {result['now_utc']}",
        f"- Latest slot: {result['latest_slot_utc']}",
        f"- Latest age: {result['latest_age_minutes']} minutes",
        f"- Slots observed/expected in window: {result['observed_slots']}/{result['expected_slots']}",
        f"- Missing slots: {result['missing_slots']}",
        f"- Failed collections: {result['failed_collections']}",
        f"- Partial collections: {result['partial_collections']}",
        f"- Truncated bundles: {result['truncated_bundles']}",
        f"- Degraded collections: {result['degraded_collections']}",
        f"- Delayed collections: {result['delayed_collections']}",
        "",
        "The watchdog only reports. It does not synthesize candles, fills, liquidations or order-book rows, and it does not dispatch recovery.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Phase B data quality")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--prefix", default="bitget-5m-")
    parser.add_argument("--stale-minutes", type=int, default=15)
    parser.add_argument("--window-minutes", type=int, default=60)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-artifacts", type=int, default=24)
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN is not set")
        return 2
    transport = UrllibTransport(token)
    out = Path(args.out)
    artifacts_dir = out / "artifacts"
    download = download_bundles(
        args.repo,
        transport=transport,
        prefix=args.prefix,
        days=1,
        out_dir=artifacts_dir,
        max_artifacts=args.max_artifacts,
        max_bytes=100_000_000,
        summary_only=True,
    )
    summaries: list[dict[str, Any]] = []
    errors = list(download.get("errors", []))
    for result in download.get("downloaded", []):
        if result.get("status") != "OK":
            continue
        summary_path = next(iter(Path(result["path"]).rglob("summary.json")), None)
        if summary_path is None:
            errors.append({"stage": "validate", "path": result.get("path"), "status": "INCOMPLETE"})
            continue
        try:
            summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            errors.append({"stage": "validate", "path": str(summary_path), "status": "SUMMARY_UNREADABLE"})
    result = classify(
        summaries,
        now_ms=int(time.time() * 1000),
        stale_minutes=args.stale_minutes,
        window_minutes=args.window_minutes,
    )
    result["download_errors"] = errors
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "report.md").write_text(render_report(result), encoding="utf-8")
    print(json.dumps({"status": result["status"], "missing": result["missing_slots"]}, sort_keys=True))
    if result["status"] in ("NO_DATA", "STALE"):
        print(f"::error::Phase B data watchdog: {result['status']}")
    elif result["status"] != "OK":
        print(f"::warning::Phase B data watchdog: {result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
