"""Bounded 60-second book/fills pilot for a small coin watchlist."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Iterable

from research.features import spread_bps, taker_imbalance

from .bundle import serialise

DEFAULT_SECONDS = 60
DEFAULT_INTERVAL_S = 2.0
DEFAULT_SYMBOLS = 5
BOOK_LIMIT = 10
FILLS_LIMIT = 100


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _depth(levels: Iterable[Any]) -> float:
    total = 0.0
    for level in levels or []:
        try:
            price = _num(level[0])
            quantity = _num(level[1])
        except (TypeError, IndexError):
            continue
        if price > 0 and quantity > 0:
            total += price * quantity
    return round(total, 6)


async def capture(
    client: Any,
    symbols: Iterable[str],
    *,
    seconds: float = DEFAULT_SECONDS,
    interval_s: float = DEFAULT_INTERVAL_S,
    now_fn: Callable[[], float] = time.time,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    book_limit: int = BOOK_LIMIT,
    fills_limit: int = FILLS_LIMIT,
) -> dict[str, Any]:
    symbol_list = list(symbols)[:DEFAULT_SYMBOLS]
    target_samples = max(1, int(seconds / interval_s))
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    intervals: list[float] = []
    requests_before = getattr(getattr(client, "stats", None), "requests", 0)
    previous = None

    for sample_index in range(target_samples):
        sample_started = now_fn()
        if previous is not None:
            intervals.append((sample_started - previous) * 1000.0)
        previous = sample_started
        calls = []
        for symbol in symbol_list:
            calls.append(("/api/v3/market/orderbook", {
                "category": "USDT-FUTURES", "symbol": symbol, "limit": str(book_limit),
            }))
            calls.append(("/api/v3/market/fills", {
                "category": "USDT-FUTURES", "symbol": symbol, "limit": str(fills_limit),
            }))
        responses = await client.gather(calls, concurrency=10)
        for index, symbol in enumerate(symbol_list):
            book_response = responses[index * 2]
            fills_response = responses[index * 2 + 1]
            if isinstance(book_response, Exception) or isinstance(fills_response, Exception):
                errors.append({
                    "symbol": symbol,
                    "sample": sample_index,
                    "error": type(
                        book_response if isinstance(book_response, Exception) else fills_response
                    ).__name__,
                })
                continue
            book = (book_response or {}).get("data", {}) or {}
            fills = (fills_response or {}).get("data", []) or []
            best_bid = _num((book.get("b") or [[0, 0]])[0][0])
            best_ask = _num((book.get("a") or [[0, 0]])[0][0])
            flow = taker_imbalance(fills, now_ms=int(sample_started * 1000))
            rows.append({
                "symbol": symbol,
                "sample_ts_ms": int(sample_started * 1000),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_bps": spread_bps(best_bid, best_ask),
                "bid_depth_top10_usdt": _depth(book.get("b", [])),
                "ask_depth_top10_usdt": _depth(book.get("a", [])),
                "buy_base": flow["buy_base"],
                "sell_base": flow["sell_base"],
                "imbalance": flow["imbalance"],
                "fills_count": flow["count"],
                "fills_span_s": flow["span_s"],
            })
        elapsed = now_fn() - sample_started
        if sample_index < target_samples - 1:
            await sleep(max(0.0, interval_s - elapsed))

    by_sample: dict[int, set[str]] = {}
    for row in rows:
        by_sample.setdefault(row["sample_ts_ms"], set()).add(row["symbol"])
    complete_samples = sum(1 for symbols_seen in by_sample.values() if len(symbols_seen) == len(symbol_list))
    requests_after = getattr(getattr(client, "stats", None), "requests", 0)
    return {
        "symbols": symbol_list,
        "target_samples": target_samples,
        "samples_ok": complete_samples,
        "rows": rows,
        "errors": errors,
        "metrics": {
            "requests": requests_after - requests_before,
            "bytes": sum(len(serialise(row)) + 1 for row in rows),
            "mean_interval_ms": round(sum(intervals) / len(intervals), 3) if intervals else None,
            "max_gap_ms": round(max(intervals), 3) if intervals else None,
            "book_limit": book_limit,
            "fills_limit": fills_limit,
            "interval_s": interval_s,
            "seconds": seconds,
        },
    }
