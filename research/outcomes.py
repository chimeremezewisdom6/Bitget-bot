"""Forward-outcome scoring with explicit trading costs and no look-ahead."""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from .features import closed_candles


def _round(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def score_event(
    event: Any,
    candles: Iterable[Any],
    *,
    horizon_min: int = 15,
    fee_bps: float = 6.0,
    spread_bps: float | None = None,
    slippage_bps: float = 0.0,
    funding_bps: float = 0.0,
    entry_latency_bars: int = 1,
    now_ms: int | None = None,
) -> dict[str, Any] | None:
    """Score one event at ``horizon_min`` using the next bar open as entry.

    Returns ``None`` when there is not enough forward data. Costs are always
    subtracted; a missing fee is caller responsibility (pass ``fee_bps``).
    """
    rows = closed_candles(candles, now_ms)
    if not rows:
        return None
    if isinstance(event, dict):
        direction = event.get("direction")
        ts_ms = event.get("ts_ms")
        event_id = event.get("event_id")
        symbol = event.get("symbol")
        event_type = event.get("type")
    else:
        direction = getattr(event, "direction", None)
        ts_ms = getattr(event, "ts_ms", None)
        event_id = getattr(event, "event_id", None)
        symbol = getattr(event, "symbol", None)
        event_type = getattr(event, "type", None)
    if direction not in ("LONG", "SHORT") or ts_ms is None:
        return None

    entry_index = next((index for index, row in enumerate(rows) if row["ts"] > int(ts_ms)), None)
    if entry_index is None:
        return None
    entry_index += max(0, entry_latency_bars - 1)
    exit_index = entry_index + max(1, horizon_min)
    if exit_index >= len(rows):
        return None

    entry = rows[entry_index]["open"]
    exit_price = rows[exit_index]["close"]
    if entry <= 0 or exit_price <= 0:
        return None

    sign = 1.0 if direction == "LONG" else -1.0
    gross_bps = sign * (exit_price / entry - 1.0) * 10_000.0

    window = rows[entry_index:exit_index + 1]
    highest = max(row["high"] for row in window)
    lowest = min(row["low"] for row in window)
    if direction == "LONG":
        mfe_bps = (highest / entry - 1.0) * 10_000.0
        mae_bps = (lowest / entry - 1.0) * 10_000.0
    else:
        mfe_bps = (1.0 - lowest / entry) * 10_000.0
        mae_bps = (1.0 - highest / entry) * 10_000.0

    spread_cost = float(spread_bps) if spread_bps is not None else 0.0
    costs_bps = 2.0 * float(fee_bps) + spread_cost + float(slippage_bps) + float(funding_bps)
    net_bps = gross_bps - costs_bps

    return {
        "event_id": event_id,
        "symbol": symbol,
        "type": event_type,
        "direction": direction,
        "horizon_min": horizon_min,
        "entry_ts_ms": rows[entry_index]["ts"],
        "exit_ts_ms": rows[exit_index]["ts"],
        "entry_price": entry,
        "exit_price": exit_price,
        "gross_bps": _round(gross_bps),
        "costs_bps": {
            "fee": _round(2.0 * float(fee_bps)),
            "spread": _round(spread_cost),
            "slippage": _round(float(slippage_bps)),
            "funding": _round(float(funding_bps)),
            "total": _round(costs_bps),
        },
        "net_bps": _round(net_bps),
        "mfe_bps": _round(mfe_bps),
        "mae_bps": _round(mae_bps),
        "bars_held": horizon_min,
        "quality": {"entry": "next_bar_open", "closed_candles_only": True},
    }


def score_events(
    events: Sequence[Any],
    candles_by_symbol: dict[str, Sequence[Any]],
    *,
    horizons: Sequence[int] = (5, 15, 30, 60),
    fee_bps: float = 6.0,
    now_ms: int | None = None,
) -> list[dict[str, Any]]:
    outcomes = []
    for event in events:
        symbol = event.get("symbol") if isinstance(event, dict) else getattr(event, "symbol", None)
        candles = candles_by_symbol.get(symbol or "", [])
        for horizon in horizons:
            scored = score_event(event, candles, horizon_min=horizon, fee_bps=fee_bps, now_ms=now_ms)
            if scored is not None:
                outcomes.append(scored)
    return outcomes
