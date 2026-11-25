"""One 5-minute read-only collection cycle.

Phase A: this module is not imported by the existing scanner. It writes only
into its bundle directory; it never touches the repository report tree.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from research import events as event_module
from research.features import (
    absorption_proxy,
    breakout_state,
    closed_candles,
    depth_within_pct,
    first_move_ts,
    oi_delta,
    return_pct,
    spread_bps,
    turnover_z,
    volatility_60,
)

from . import bundle, flow, micro, spot, universe
from .bitget_public import PublicClient, TokenBucket

CATEGORY = "USDT-FUTURES"
SLOT_MS = 300_000
CATCHUP_MS = 1_800_000


@dataclass
class Config:
    top_n: int = 200
    max_spread_bps: float = 10.0
    min_depth_usdt: float = 20_000.0
    min_turnover_usdt: float = 50_000.0
    spot_max_symbols: int = 50
    micro_enabled: bool = False
    micro_symbols: int = 5
    micro_seconds: float = 60.0
    micro_interval_s: float = 2.0
    concurrency: int = 6
    rate_per_sec: float = 5.0
    burst: int = 5
    bundle_max_bytes: int = 1_500_000
    catchup_ms: int = CATCHUP_MS


@dataclass
class CycleResult:
    slot_ms: int
    started_ms: int
    finished_ms: int
    outcome: str
    symbols_requested: int
    symbols_ok: int
    symbols_failed: int
    candles_new: int
    events: int
    duplicates: int
    bundle_path: str | None
    manifest: dict[str, Any]
    errors: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "slot": _iso(self.slot_ms),
            "outcome": self.outcome,
            "symbols_requested": self.symbols_requested,
            "symbols_ok": self.symbols_ok,
            "symbols_failed": self.symbols_failed,
            "candles_new": self.candles_new,
            "events": self.events,
            "duplicates": self.duplicates,
            "duration_ms": self.finished_ms - self.started_ms,
            "artifact": self.manifest.get("artifact"),
            "bundle_size_bytes": self.manifest.get("size_bytes"),
            "metrics": self.metrics,
            "errors": self.errors[:20],
        }


def _iso(ts_ms: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _payload_rows(payload: Any, key: str = "data") -> list[Any]:
    if isinstance(payload, Exception) or not isinstance(payload, dict):
        return []
    data = payload.get(key)
    if isinstance(data, dict):
        data = data.get("list", [])
    return data if isinstance(data, list) else []


def _liquidation_status(payload: Any) -> str:
    if isinstance(payload, Exception):
        return "ERROR"
    if not isinstance(payload, dict):
        return "MISSING"
    return "PARTIAL_PAGE"


def _liquidation_map(payload: Any) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for item in _payload_rows(payload):
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        side = str(item.get("side", "")).lower()
        value = _num(item.get("price")) * _num(item.get("amount"))
        if not symbol or value <= 0 or side not in ("buy", "sell"):
            continue
        row = result.setdefault(symbol, {"long": 0.0, "short": 0.0, "records": 0})
        # Bitget documents buy as long-position liquidation and sell as short.
        row["long" if side == "buy" else "short"] += value
        row["records"] += 1
    return result


def _liquidation_fields(row: dict[str, float] | None) -> dict[str, Any]:
    row = row or {"long": 0.0, "short": 0.0, "records": 0}
    long_usdt = float(row.get("long", 0.0))
    short_usdt = float(row.get("short", 0.0))
    total = long_usdt + short_usdt
    if long_usdt > short_usdt:
        side = "LONG"
    elif short_usdt > long_usdt:
        side = "SHORT"
    else:
        side = "MIXED" if total > 0 else None
    return {
        "liquidation_long_usdt": long_usdt,
        "liquidation_short_usdt": short_usdt,
        "liquidation_total_usdt": total,
        "liquidation_records": int(row.get("records", 0)),
        "liquidation_side": side,
    }


def _book_row(perp: universe.Perp, payload: Any, now_ms: int) -> dict[str, Any]:
    book = (payload or {}).get("data", {}) if isinstance(payload, dict) else {}
    bids = list(book.get("b", []) or [])[:10]
    asks = list(book.get("a", []) or [])[:10]
    mid = perp.mid
    bid_depth = depth_within_pct(bids, mid)
    ask_depth = depth_within_pct(asks, mid)
    total_depth = bid_depth + ask_depth
    return {
        "symbol": perp.symbol,
        "ts_ms": int(_num(book.get("ts"), now_ms)),
        "bids": bids,
        "asks": asks,
        "spread_bps": spread_bps(perp.bid, perp.ask),
        "bid_depth_0_5pct_usdt": bid_depth,
        "ask_depth_0_5pct_usdt": ask_depth,
        "book_imbalance_0p5": (
            (bid_depth - ask_depth) / total_depth if total_depth > 0 else None
        ),
    }


def _oi_row(symbol: str, payload: Any) -> dict[str, Any] | None:
    rows = _payload_rows(payload)
    if not rows:
        return None
    latest = rows[-1] if isinstance(rows[-1], dict) else {}
    return {
        "symbol": symbol,
        "ts_ms": int(_num(latest.get("timestamp"))),
        "open_interest": _num(latest.get("openInterest")),
        "one_side_open_interest": _num(latest.get("oneSideOpenInterest")),
        "open_interest_value": _num(latest.get("openInterestValue")),
        "delta_15m_pct": oi_delta(payload, 15),
        "delta_30m_pct": oi_delta(payload, 30),
        "delta_60m_pct": oi_delta(payload, 60),
    }


async def run_cycle(
    *,
    client: Any | None = None,
    slot_ms: int | None = None,
    now_ms: int | None = None,
    config: Config | None = None,
    out_dir: str | Path | None = None,
) -> CycleResult:
    config = config or Config()
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    slot = int(slot_ms if slot_ms is not None else (now // SLOT_MS) * SLOT_MS)
    if client is not None:
        return await _run(client, slot, now, config, out_dir)

    import aiohttp

    async with aiohttp.ClientSession() as session:
        public = PublicClient(
            session,
            limiter=TokenBucket(config.rate_per_sec, config.burst),
        )
        return await _run(public, slot, now, config, out_dir)


async def _run(
    client: Any,
    slot: int,
    now: int,
    config: Config,
    out_dir: str | Path | None,
) -> CycleResult:
    started = now
    errors: list[dict[str, Any]] = []
    try:
        instruments_payload = await client.get(
            "/api/v3/market/instruments", {"category": CATEGORY}
        )
        tickers_payload = await client.get("/api/v3/market/tickers", {"category": CATEGORY})
        candidates = universe.rank_candidates(
            tickers_payload.get("data", []),
            instruments_payload.get("data", []),
            top_n=config.top_n,
            min_turnover=config.min_turnover_usdt,
        )
        book_calls = [
            ("/api/v3/market/orderbook", {
                "category": CATEGORY, "symbol": row["symbol"], "limit": "100",
            })
            for row in candidates.rows
        ]
        book_responses = await client.gather(book_calls, concurrency=config.concurrency)
        books = {}
        for row, response in zip(candidates.rows, book_responses):
            if isinstance(response, Exception):
                errors.append({"symbol": row["symbol"], "source": "orderbook",
                               "message": type(response).__name__})
                continue
            books[row["symbol"]] = (response or {}).get("data", {}) or {}
        selection = universe.select(
            candidates,
            books,
            max_spread_bps=config.max_spread_bps,
            min_depth_usdt=config.min_depth_usdt,
        )
        if not selection.selected:
            raise RuntimeError("No symbol passed the liquidity filters")

        symbols = [item.symbol for item in selection.selected]
        calls = []
        for symbol in symbols:
            calls.append(("/api/v3/market/candles", {
                "category": CATEGORY, "symbol": symbol, "interval": "1m", "limit": "100",
            }))
            calls.append(("/api/v3/market/fills", {
                "category": CATEGORY, "symbol": symbol, "limit": "100",
            }))
            calls.append(("/api/v3/market/open-interest-history", {
                "symbol": symbol, "period": "5m",
            }))
        responses = await client.gather(calls, concurrency=config.concurrency)
        candles_by_symbol: dict[str, Any] = {}
        fills_by_symbol: dict[str, Any] = {}
        oi_by_symbol: dict[str, Any] = {}
        for index, symbol in enumerate(symbols):
            candles_by_symbol[symbol] = responses[index * 3]
            fills_by_symbol[symbol] = responses[index * 3 + 1]
            oi_by_symbol[symbol] = responses[index * 3 + 2]
            for source, response in (
                ("candles", candles_by_symbol[symbol]),
                ("fills", fills_by_symbol[symbol]),
                ("open_interest", oi_by_symbol[symbol]),
            ):
                if isinstance(response, Exception):
                    errors.append({"symbol": symbol, "source": source,
                                   "message": type(response).__name__})

        liquidations_payload = await client.get(
            "/api/v3/market/liquidations", {"category": CATEGORY, "limit": "100"}
        )
        liq_map = _liquidation_map(liquidations_payload)
        liq_status = _liquidation_status(liquidations_payload)
        try:
            spot_rows = await spot.spot_snapshot(
                client, selection.selected, max_symbols=config.spot_max_symbols, now_ms=now
            )
        except Exception as exc:
            spot_rows = []
            errors.append({"symbol": "*", "source": "spot", "message": type(exc).__name__})

        micro_result = None
        if config.micro_enabled:
            try:
                micro_result = await micro.capture(
                    client,
                    symbols[: config.micro_symbols],
                    seconds=config.micro_seconds,
                    interval_s=config.micro_interval_s,
                    now_fn=lambda: time.time(),
                )
            except Exception as exc:
                errors.append({"symbol": "*", "source": "micro", "message": type(exc).__name__})

        spot_by_symbol = {row.symbol: row for row in spot_rows}
        features: list[dict[str, Any]] = []
        flow_rows: list[dict[str, Any]] = []
        book_rows: list[dict[str, Any]] = []
        oi_rows: list[dict[str, Any]] = []
        candle_rows: dict[tuple[str, int], dict[str, Any]] = {}
        duplicates = 0
        cutoff = slot - config.catchup_ms
        for perp in selection.selected:
            symbol = perp.symbol
            candle_payload = candles_by_symbol.get(symbol)
            if isinstance(candle_payload, Exception) or not isinstance(candle_payload, dict):
                continue
            raw_candles = candle_payload.get("data", []) or []
            closed = closed_candles(raw_candles, now)
            for candle in closed:
                if candle["ts"] < cutoff:
                    continue
                key = (symbol, candle["ts"])
                if key in candle_rows:
                    duplicates += 1
                candle_rows[key] = {"symbol": symbol, **candle}

            volatility = volatility_60(raw_candles, now)
            z = turnover_z(raw_candles, now)
            flow_row = flow.flow_snapshot(fills_by_symbol.get(symbol), symbol, now_ms=now)
            flow_rows.append(flow_row)
            book_row = _book_row(perp, books.get(symbol), now)
            book_rows.append(book_row)
            oi_row = _oi_row(symbol, oi_by_symbol.get(symbol))
            if oi_row is not None:
                oi_rows.append(oi_row)
            breakout = breakout_state(raw_candles, now)
            spot_row = spot_by_symbol.get(symbol)
            return_1m = return_pct(closed, 1)
            return_5m = return_pct(closed, 5)
            return_15m = return_pct(closed, 15)
            book_imbalance = book_row.get("book_imbalance_0p5")
            absorption = absorption_proxy(
                flow_row.get("imbalance"),
                return_5m,
                None,
                book_imbalance=book_imbalance,
                min_imbalance=0.5,
            )
            perp_move_ts = first_move_ts(closed)
            spot_move_ts = spot_row.move_5m_ts_ms if spot_row else None
            spot_lead_ms = (
                perp_move_ts - spot_move_ts
                if perp_move_ts is not None and spot_move_ts is not None
                else None
            )
            liq_fields = _liquidation_fields(liq_map.get(symbol))
            features.append({
                "symbol": symbol,
                "ts_ms": now,
                "price": perp.last,
                "turnover24h_usdt": perp.turnover24h,
                "turnover_band": universe.classify_turnover(perp.turnover24h),
                "taker_fee_bps": (
                    perp.taker_fee * 10_000.0 if perp.taker_fee is not None else None
                ),
                "fee_status": (
                    "PROVIDED" if perp.taker_fee is not None else "FEE_ESTIMATED"
                ),
                "funding_rate": perp.funding_rate,
                "return_1m_pct": return_1m,
                "return_5m_pct": return_5m,
                "return_15m_pct": return_15m,
                "return_60m_pct": return_pct(closed, 60),
                "turnover_1m_usdt": closed[-1]["quote_turnover"] if closed else None,
                "turnover_z_60m": z.get("turnover_z"),
                "oi_delta_15m_pct": oi_row.get("delta_15m_pct") if oi_row else None,
                "oi_delta_30m_pct": oi_row.get("delta_30m_pct") if oi_row else None,
                "oi_delta_60m_pct": oi_row.get("delta_60m_pct") if oi_row else None,
                "taker_imbalance": flow_row.get("imbalance"),
                "taker_coverage_pct": flow_row.get("coverage_pct"),
                "taker_quality": flow_row.get("quality"),
                "spread_bps": perp.spread_bps,
                "bid_depth_0_5pct_usdt": perp.bid_depth_usdt,
                "ask_depth_0_5pct_usdt": perp.ask_depth_usdt,
                "book_imbalance_0p5": book_imbalance,
                "spot_basis_bps": spot_row.basis_bps if spot_row else None,
                "spot_return_5m_pct": spot_row.ret_5m_pct if spot_row else None,
                "spot_turnover_z": spot_row.turnover_z if spot_row else None,
                "spot_move_5m_ts_ms": spot_move_ts,
                "perp_move_5m_ts_ms": perp_move_ts,
                "spot_lead_ms": spot_lead_ms,
                "spot_status": (
                    "MAPPED" if spot_row and spot_row.basis_bps is not None
                    else (getattr(spot_row, "error", None) or "SPOT_UNMAPPED")
                ),
                "breakout_60m": breakout.get("breakout_60m"),
                "breakout_direction": breakout.get("direction"),
                "failed_breakout": breakout.get("failed_breakout"),
                "absorption": absorption,
                "liquidation_status": liq_status,
                **liq_fields,
                **volatility,
            })

        detected = []
        for feature in features:
            for event_type in event_module.DETECTORS:
                event = event_module.detect(feature, event_type)
                if event is not None:
                    detected.append(event)
        detected = event_module.dedupe(detected, min_gap_ms=SLOT_MS)

        sections = {
            "universe": [item.as_dict() for item in selection.selected],
            "exclusions": selection.excluded,
            "candles": list(candle_rows.values()),
            "features": features,
            "flow": flow_rows,
            "book": book_rows,
            "oi": oi_rows,
            "liquidations": _payload_rows(liquidations_payload),
            "spot": [row.as_dict() for row in spot_rows],
            "micro": (micro_result or {}).get("rows", []),
            "events": [event.compact() for event in detected],
        }
        finished = max(started, int(time.time() * 1000))
        requested = len(selection.selected)
        ok = len(features)
        failed = requested - ok
        ratio = ok / requested if requested else 0.0
        outcome = "success" if ratio >= 0.95 else "partial" if ratio >= 0.5 else "failed"
        fee_estimated = sum(
            1 for feature in features if feature.get("fee_status") == "FEE_ESTIMATED"
        )
        meta = {
            "schema_version": bundle.BUNDLE_VERSION,
            "slot": _iso(slot),
            "git_sha": os.getenv("GITHUB_SHA", ""),
            "started_ms": started,
            "finished_ms": finished,
            "outcome": outcome,
            "symbols_ok": ok,
            "symbols_failed": failed,
            "duplicates": duplicates,
            "fee_estimated": fee_estimated,
            "data_source": "Bitget USDT-FUTURES public market data",
            "trading_enabled": False,
            "sample_sizes": selection.sample_sizes,
            "band_counts": selection.band_counts,
            "config": {
                "top_n": config.top_n,
                "max_spread_bps": config.max_spread_bps,
                "min_depth_usdt": config.min_depth_usdt,
                "spot_max_symbols": config.spot_max_symbols,
                "micro_enabled": config.micro_enabled,
            },
        }
        target_dir = Path(out_dir or tempfile.mkdtemp(prefix="bitget-cycle-")) / f"cycle-{slot}"
        bundle_path, manifest = bundle.build_bundle(
            sections, meta, target_dir, max_bytes=config.bundle_max_bytes
        )
        metrics = client.stats.summary() if hasattr(client, "stats") else {}
        metrics["micro"] = (micro_result or {}).get("metrics")
        metrics["fee_estimated"] = fee_estimated
        return CycleResult(
            slot_ms=slot,
            started_ms=started,
            finished_ms=finished,
            outcome=outcome,
            symbols_requested=requested,
            symbols_ok=ok,
            symbols_failed=failed,
            candles_new=len(candle_rows),
            events=len(detected),
            duplicates=duplicates,
            bundle_path=str(bundle_path),
            manifest=manifest,
            errors=errors,
            metrics=metrics,
        )
    except Exception as exc:
        finished = max(started, int(time.time() * 1000))
        errors.append({"symbol": "*", "source": "cycle", "message": type(exc).__name__})
        bundle_path = None
        manifest: dict[str, Any] = {}
        try:
            target_dir = Path(out_dir or tempfile.mkdtemp(prefix="bitget-cycle-")) / f"cycle-{slot}"
            failure_meta = {
                "schema_version": bundle.BUNDLE_VERSION,
                "slot": _iso(slot),
                "git_sha": os.getenv("GITHUB_SHA", ""),
                "started_ms": started,
                "finished_ms": finished,
                "outcome": "failed",
                "symbols_ok": 0,
                "symbols_failed": 0,
                "duplicates": 0,
                "data_source": "Bitget USDT-FUTURES public market data",
                "trading_enabled": False,
            }
            written, manifest = bundle.build_bundle(
                {"errors": errors}, failure_meta, target_dir, max_bytes=config.bundle_max_bytes
            )
            bundle_path = str(written)
        except Exception:
            bundle_path = None
            manifest = {}
        return CycleResult(
            slot_ms=slot,
            started_ms=started,
            finished_ms=finished,
            outcome="failed",
            symbols_requested=0,
            symbols_ok=0,
            symbols_failed=0,
            candles_new=0,
            events=0,
            duplicates=0,
            bundle_path=bundle_path,
            manifest=manifest,
            errors=errors,
            metrics=client.stats.summary() if hasattr(client, "stats") else {},
        )
