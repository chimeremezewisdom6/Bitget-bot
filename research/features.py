"""Deterministic feature calculations shared by collection and evaluation.

All functions are pure: they take market rows and return plain dictionaries.
No network, credentials, file writes or wall-clock reads beyond the explicit
``now_ms`` default.
"""
from __future__ import annotations

import math
import statistics
import time
from typing import Any, Iterable, Sequence

CANDLE_MS = 60_000
VOLATILITY_FLAG_THRESHOLD = 0.7


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def parse_candle(row: Any) -> dict[str, Any] | None:
    """Normalise a Bitget candle row (list) or an internal candle dict."""
    if isinstance(row, dict):
        ts = row.get("ts", row.get("candle_timestamp_ms", row.get("timestamp")))
        open_ = row.get("open", row.get("o"))
        high = row.get("high", row.get("h"))
        low = row.get("low", row.get("l"))
        close = row.get("close", row.get("c"))
        base_volume = row.get("base_volume", row.get("baseVol", row.get("v")))
        quote_turnover = row.get("quote_turnover", row.get("quoteVol", row.get("q")))
    else:
        try:
            ts, open_, high, low, close, base_volume, quote_turnover = row[:7]
        except (TypeError, ValueError):
            return None
    ts_value = _num(ts)
    open_value = _num(open_)
    high_value = _num(high)
    low_value = _num(low)
    close_value = _num(close)
    if ts_value is None or None in (open_value, high_value, low_value, close_value):
        return None
    if close_value <= 0:
        return None
    return {
        "ts": int(ts_value),
        "open": open_value,
        "high": high_value,
        "low": low_value,
        "close": close_value,
        "base_volume": _num(base_volume, 0.0) or 0.0,
        "quote_turnover": _num(quote_turnover, 0.0) or 0.0,
    }


def closed_candles(rows: Iterable[Any], now_ms: int | None = None) -> list[dict[str, Any]]:
    """Return unique, chronological, fully closed one-minute candles."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    by_ts: dict[int, dict[str, Any]] = {}
    for row in rows or []:
        candle = parse_candle(row)
        if candle is None:
            continue
        if candle["ts"] + CANDLE_MS > now:
            continue
        by_ts[candle["ts"]] = candle
    return [by_ts[key] for key in sorted(by_ts)]


def close_to_close_changes(closes: Sequence[float]) -> list[float]:
    changes = []
    for index in range(1, len(closes)):
        previous = closes[index - 1]
        current = closes[index]
        if previous <= 0 or current <= 0:
            continue
        changes.append(100.0 * (current / previous - 1.0))
    return changes


def _has_consecutive_minutes(candles: Sequence[dict[str, Any]]) -> bool:
    return all(
        candles[index]["ts"] - candles[index - 1]["ts"] == CANDLE_MS
        for index in range(1, len(candles))
    )


def volatility_60(
    rows: Iterable[Any],
    now_ms: int | None = None,
    threshold: float = VOLATILITY_FLAG_THRESHOLD,
) -> dict[str, Any]:
    """Dynamic volatility over the latest 60 close-to-close one-minute changes.

    Requires 61 fully closed candles. A missing interval produces
    ``volatility_status="GAP"`` and no flag. Only the maximum absolute change
    determines the 0.7% flag; mean, sum and standard deviation are recorded
    separately.
    """
    candles = closed_candles(rows, now_ms)
    empty = {
        "volatility_status": "INSUFFICIENT_CANDLES",
        "candles_used": len(candles),
        "max_abs_1m_pct": None,
        "mean_abs_1m_pct": None,
        "sum_abs_1m_pct": None,
        "vol60_pct": None,
        "vol60_bps": None,
        "flag_0_7": None,
        "threshold": threshold,
        "first_ts": None,
        "last_ts": None,
    }
    if len(candles) < 61:
        return empty

    window = candles[-61:]
    changes = close_to_close_changes([candle["close"] for candle in window])
    if len(changes) != 60:
        return empty

    absolute = [abs(value) for value in changes]
    maximum = max(absolute)
    mean = statistics.fmean(absolute)
    total = math.fsum(absolute)
    stdev = statistics.stdev(changes)
    status = "OK" if _has_consecutive_minutes(window) else "GAP"

    return {
        "volatility_status": status,
        "candles_used": 60,
        "max_abs_1m_pct": round(maximum, 6),
        "mean_abs_1m_pct": round(mean, 6),
        "sum_abs_1m_pct": round(total, 6),
        "vol60_pct": round(stdev, 6),
        "vol60_bps": round(stdev * 100.0, 6),
        # Round at 1e-9 percentage points so an exact 0.7% boundary is not
        # rejected by binary floating-point representation.
        "flag_0_7": (round(maximum, 9) >= float(threshold)) if status == "OK" else None,
        "threshold": threshold,
        "first_ts": window[0]["ts"],
        "last_ts": window[-1]["ts"],
    }


def return_pct(candles: Sequence[dict[str, Any]], minutes: int) -> float | None:
    if minutes <= 0 or len(candles) <= minutes:
        return None
    current = candles[-1]["close"]
    previous = candles[-1 - minutes]["close"]
    if previous <= 0 or current <= 0:
        return None
    return round(100.0 * (current / previous - 1.0), 6)


def first_move_ts(
    candles: Sequence[dict[str, Any]],
    *,
    minutes: int = 5,
    threshold_pct: float = 0.2,
) -> int | None:
    """First closed-candle timestamp whose trailing return crosses the threshold."""
    if minutes <= 0:
        return None
    for index in range(minutes, len(candles)):
        previous = candles[index - minutes]["close"]
        current = candles[index]["close"]
        if previous <= 0 or current <= 0:
            continue
        if abs(100.0 * (current / previous - 1.0)) >= threshold_pct:
            return int(candles[index]["ts"])
    return None


def turnover_z(rows: Iterable[Any], now_ms: int | None = None, window: int = 60) -> dict[str, Any]:
    candles = closed_candles(rows, now_ms)
    if len(candles) < window + 1:
        return {"turnover_z": None, "samples": len(candles), "last": None, "mean": None, "stdev": None}
    baseline = [candle["quote_turnover"] for candle in candles[-window - 1:-1]]
    last = candles[-1]["quote_turnover"]
    mean = statistics.fmean(baseline)
    stdev = statistics.stdev(baseline) if len(baseline) > 1 else 0.0
    z = (last - mean) / stdev if stdev > 0 else None
    return {
        "turnover_z": round(z, 6) if z is not None else None,
        "samples": len(baseline),
        "last": last,
        "mean": round(mean, 6),
        "stdev": round(stdev, 6),
    }


def _oi_points(payload: Any) -> list[tuple[int, float]]:
    if isinstance(payload, dict):
        data = payload.get("data", payload)
    else:
        data = payload
    if isinstance(data, dict):
        data = data.get("list", [])
    points = []
    for row in data or []:
        if not isinstance(row, dict):
            continue
        ts = _num(row.get("timestamp", row.get("ts")))
        value = _num(row.get("openInterest", row.get("open_interest")))
        if ts is None or value is None or value <= 0:
            continue
        points.append((int(ts), value))
    return sorted(points)


def oi_delta(payload: Any, minutes: int, tolerance_ms: int = 150_000) -> float | None:
    """Percent change in aggregate open interest over ``minutes``.

    Uses the point closest to the target timestamp within ``tolerance_ms``.
    Missing or stale history returns ``None`` rather than zero.
    """
    points = _oi_points(payload)
    if len(points) < 2:
        return None
    latest_ts, latest_value = points[-1]
    target = latest_ts - minutes * CANDLE_MS
    candidates = [(abs(ts - target), ts, value) for ts, value in points[:-1]]
    distance, _, old_value = min(candidates)
    if distance > tolerance_ms or old_value <= 0:
        return None
    return round(100.0 * (latest_value / old_value - 1.0), 6)


def taker_imbalance(
    fills: Iterable[dict[str, Any]],
    *,
    now_ms: int | None = None,
    interval_ms: int = 300_000,
) -> dict[str, Any]:
    """Aggregate a public fills sample and report its coverage honestly."""
    rows = [row for row in (fills or []) if isinstance(row, dict)]
    buy_base = sell_base = buy_quote = sell_quote = 0.0
    timestamps = []
    for row in rows:
        size = _num(row.get("size", row.get("amount")))
        price = _num(row.get("price"))
        ts = _num(row.get("ts", row.get("timestamp")))
        if size is None or size <= 0:
            continue
        if ts is not None:
            timestamps.append(int(ts))
        notional = size * (price or 0.0)
        side = str(row.get("side", "")).lower()
        if side == "buy":
            buy_base += size
            buy_quote += notional
        elif side == "sell":
            sell_base += size
            sell_quote += notional
    total = buy_base + sell_base
    imbalance = (buy_base - sell_base) / total if total > 0 else None
    span_s = (max(timestamps) - min(timestamps)) / 1000.0 if len(timestamps) > 1 else 0.0
    newest_age_s = (
        max(0.0, (int(now_ms if now_ms is not None else time.time() * 1000) - max(timestamps)) / 1000.0)
        if timestamps
        else None
    )
    coverage_pct = min(100.0, span_s / (interval_ms / 1000.0) * 100.0) if interval_ms > 0 else 0.0
    if not rows:
        quality = "EMPTY"
    elif newest_age_s is not None and newest_age_s > 60:
        quality = "STALE"
    elif len(rows) >= 50 and span_s >= 60:
        quality = "ADEQUATE"
    else:
        quality = "SAMPLED"
    return {
        "count": len(rows),
        "buy_base": buy_base,
        "sell_base": sell_base,
        "buy_quote": buy_quote,
        "sell_quote": sell_quote,
        "imbalance": round(imbalance, 6) if imbalance is not None else None,
        "span_s": round(span_s, 3),
        "newest_age_s": round(newest_age_s, 3) if newest_age_s is not None else None,
        "coverage_pct": round(coverage_pct, 3),
        "quality": quality,
    }


def spread_bps(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    return round((ask - bid) / mid * 10_000.0, 6) if mid > 0 else None


def depth_within_pct(levels: Iterable[Any], mid: float | None, pct: float = 0.005) -> float:
    if mid is None or mid <= 0:
        return 0.0
    total = 0.0
    for level in levels or []:
        try:
            price = _num(level[0])
            quantity = _num(level[1])
        except (TypeError, IndexError):
            continue
        if price is None or quantity is None or price <= 0 or quantity <= 0:
            continue
        if abs(price / mid - 1.0) <= pct:
            total += price * quantity
    return round(total, 6)


def basis_bps(perp_mid: float | None, spot_mid: float | None) -> float | None:
    if perp_mid is None or spot_mid is None or perp_mid <= 0 or spot_mid <= 0:
        return None
    return round((perp_mid / spot_mid - 1.0) * 10_000.0, 6)


def absorption_proxy(
    imbalance: float | None,
    price_change_pct: float | None,
    opposite_depth_change_pct: float | None,
    *,
    book_imbalance: float | None = None,
    min_imbalance: float = 0.4,
    max_price_move_pct: float = 0.1,
    min_depth_change_pct: float = -10.0,
    require_depth_known: bool = False,
    require_book_imbalance: bool = False,
    min_abs_book_imbalance: float = 0.2,
) -> dict[str, Any]:
    """Approximate absorption: aggressive flow with little price progress.

    The fade direction opposes the aggressor. A missing depth change is
    reported as ``depth_known=False`` and can be rejected explicitly.
    """
    depth_known = opposite_depth_change_pct is not None
    book_known = book_imbalance is not None
    direction = "SHORT" if (imbalance or 0) > 0 else "LONG"
    book_aligned = bool(
        book_known
        and (
            (direction == "SHORT" and book_imbalance <= -min_abs_book_imbalance)
            or (direction == "LONG" and book_imbalance >= min_abs_book_imbalance)
        )
    )
    absorbed = (
        imbalance is not None
        and price_change_pct is not None
        and abs(imbalance) >= min_imbalance
        and abs(price_change_pct) <= max_price_move_pct
        and (not depth_known or opposite_depth_change_pct >= min_depth_change_pct)
        and (not require_depth_known or depth_known)
        and (not require_book_imbalance or book_aligned)
    )
    return {
        "absorbed": bool(absorbed),
        "direction": direction if absorbed else None,
        "depth_known": depth_known,
        "book_known": book_known,
        "book_aligned": book_aligned,
        "imbalance": imbalance,
        "price_change_pct": price_change_pct,
        "opposite_depth_change_pct": opposite_depth_change_pct,
        "book_imbalance": book_imbalance,
    }


def breakout_state(
    rows: Iterable[Any],
    now_ms: int | None = None,
    lookback: int = 60,
    confirm_bars: int = 3,
) -> dict[str, Any]:
    """Describe a 60-bar breakout and whether it failed within ``confirm_bars``."""
    candles = closed_candles(rows, now_ms)
    if len(candles) < lookback + confirm_bars + 1:
        return {"breakout_60m": None, "direction": None, "failed_breakout": None}
    recent = candles[-(confirm_bars + 1):]
    history = candles[-(lookback + confirm_bars + 1):-(confirm_bars + 1)]
    high = max(candle["high"] for candle in history)
    low = min(candle["low"] for candle in history)
    first = recent[0]
    direction = None
    if first["close"] > high:
        direction = "LONG"
    elif first["close"] < low:
        direction = "SHORT"
    if direction is None:
        return {"breakout_60m": False, "direction": None, "failed_breakout": False}
    later = recent[1:]
    failed = (
        any(candle["close"] < high for candle in later)
        if direction == "LONG"
        else any(candle["close"] > low for candle in later)
    )
    return {"breakout_60m": True, "direction": direction, "failed_breakout": failed}
