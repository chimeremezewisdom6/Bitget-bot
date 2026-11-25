"""Public fills sampling with explicit coverage quality flags."""
from __future__ import annotations

from typing import Any, Iterable

from research.features import taker_imbalance

FILLS_LIMIT = 100


def flow_snapshot(
    payload: dict[str, Any] | Exception | None,
    symbol: str,
    *,
    now_ms: int | None = None,
) -> dict[str, Any]:
    if isinstance(payload, Exception):
        return {
            "symbol": symbol, "count": 0, "buy_base": 0.0, "sell_base": 0.0,
            "imbalance": None, "span_s": 0.0, "newest_age_s": None,
            "coverage_pct": 0.0, "quality": "ERROR",
            "error": type(payload).__name__,
        }
    rows = (payload or {}).get("data", []) if isinstance(payload, dict) else []
    result = taker_imbalance(rows, now_ms=now_ms)
    return {"symbol": symbol, **result}


async def collect_flow(
    client: Any,
    symbols: Iterable[str],
    *,
    now_ms: int | None = None,
    limit: int = FILLS_LIMIT,
) -> list[dict[str, Any]]:
    symbol_list = list(symbols)
    calls = [
        ("/api/v3/market/fills", {
            "category": "USDT-FUTURES", "symbol": symbol, "limit": str(limit),
        })
        for symbol in symbol_list
    ]
    responses = await client.gather(calls, concurrency=6)
    return [
        flow_snapshot(response, symbol, now_ms=now_ms)
        for symbol, response in zip(symbol_list, responses)
    ]
