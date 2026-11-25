"""Read-only Phase B collector entry point.

The scheduled workflow is inert until PHASE_B_COLLECTOR_ENABLED is set to true.
This module never authenticates with Bitget and never submits orders.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .cycle import Config, CycleResult, SLOT_MS, run_cycle


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc).isoformat()


def slot_for(now_ms: int, slot_ms: int = SLOT_MS) -> int:
    return (int(now_ms) // int(slot_ms)) * int(slot_ms)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect one read-only Bitget futures research bundle")
    parser.add_argument("--out-dir", default="artifacts")
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--max-bytes", type=int, default=300_000)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--rate-per-sec", type=float, default=4.0)
    parser.add_argument("--burst", type=int, default=4)
    parser.add_argument("--micro", action="store_true", help="Enable the optional micro-capture sampler")
    parser.add_argument("--micro-seconds", type=float, default=60.0)
    parser.add_argument("--now-ms", type=int, default=None)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def _write_outputs(result: CycleResult, out_dir: str | Path, now_ms: int) -> Path:
    if result.bundle_path:
        cycle_dir = Path(result.bundle_path).parent
    else:
        cycle_dir = Path(out_dir) / f"cycle-{result.slot_ms}"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    summary = result.summary()
    summary.update({
        "slot_ms": result.slot_ms,
        "started_ms": result.started_ms,
        "finished_ms": result.finished_ms,
        "manifest": result.manifest,
        "bundle_path": result.bundle_path,
        "data_source": "Bitget USDT-FUTURES public market data",
        "trading_enabled": False,
        "generated_at_utc": _iso(now_ms),
    })
    (cycle_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    log_lines = [
        f"slot={summary.get('slot')}",
        f"outcome={summary.get('outcome')}",
        f"symbols_ok={summary.get('symbols_ok')} symbols_failed={summary.get('symbols_failed')}",
        f"bundle={result.bundle_path}",
        f"trading_enabled=False",
    ]
    for error in result.errors[:20]:
        log_lines.append(json.dumps(error, sort_keys=True))
    (cycle_dir / "logs.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return cycle_dir


async def run(args: argparse.Namespace, *, client: Any | None = None) -> CycleResult | None:
    now_ms = int(args.now_ms if args.now_ms is not None else time.time() * 1000)
    config = Config(
        top_n=int(args.top_n),
        micro_enabled=bool(args.micro),
        micro_seconds=float(args.micro_seconds),
        concurrency=int(args.concurrency),
        rate_per_sec=float(args.rate_per_sec),
        burst=int(args.burst),
        bundle_max_bytes=int(args.max_bytes),
    )
    try:
        result = await run_cycle(
            client=client,
            now_ms=now_ms,
            config=config,
            out_dir=args.out_dir,
        )
    except Exception as exc:  # keep a failure record for the artifact upload
        slot = slot_for(now_ms)
        cycle_dir = Path(args.out_dir) / f"cycle-{slot}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "slot": _iso(slot),
            "slot_ms": slot,
            "outcome": "failed",
            "error": type(exc).__name__,
            "message": str(exc)[:500],
            "data_source": "Bitget USDT-FUTURES public market data",
            "trading_enabled": False,
            "generated_at_utc": _iso(now_ms),
        }
        (cycle_dir / "summary.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (cycle_dir / "logs.txt").write_text(
            f"collector failed: {type(exc).__name__}: {str(exc)[:500]}\n", encoding="utf-8"
        )
        return None
    _write_outputs(result, args.out_dir, now_ms)
    return result


def collector_enabled() -> bool:
    return os.getenv("PHASE_B_COLLECTOR_ENABLED", "").strip().lower() == "true"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not collector_enabled():
        print("Phase B collector is disabled; set PHASE_B_COLLECTOR_ENABLED=true to run.")
        return 2
    result = asyncio.run(run(args))
    if result is None:
        return 1
    if not args.quiet:
        print(json.dumps(result.summary(), sort_keys=True))
    return 0 if result.outcome in ("success", "partial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
