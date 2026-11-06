"""
market_math.py
==============
Cross-Sectional Relative Weakness & Accelerated Breakdown Engine.

Bump __version__ on every change. bot.py refuses to start on mismatch.

v2026.11.13 upgrades:
  - ACCEL_DROP_3M_MIN raised 0.25% -> 1.50% (from 12-crash fingerprint study)
  - New MACRO_ALIGN_MAX_PCT = 1.5 — reject SHORTs inside relief bounces
  - compute_crash_metrics now returns actual high timestamp (fixes "in 0m")
"""

import time

__version__ = "2026.11.13"

FEE_ROUND_TRIP_PCT = 0.22

PCT_15M_MIN_DROP = -7.0
PCT_15M_MAX_DROP = -1.5

DROP6_MIN_PCT = 0.15
ACCEL_DROP_3M_MIN = 1.50            # was 0.25 — matches real collapses
ACCELERATION_MIN_RATIO = 1.0
VOLUME_EXPANSION_MIN = 3.0
BREAKDOWN_BUFFER_PCT = 0.05
ANTI_CHASE_MAX_PCT = 0.60

MACRO_ALIGN_MAX_PCT = 1.5           # NEW — price must be <= low_4h * 1.015

_VOL_MAX_EXTRAPOLATION = 3.0
_MIN_ELAPSED_SEC = 20.0

DEPTH_BAND_PCT = 0.01
MIN_SIDE_DEPTH_USD = 5000.0
MAX_BID_DEPTH_USD = 100000.0
FRAGILITY_RATIO_MIN = 1.80

MAX_SPREAD_PCT = 0.15

BREAKEVEN_TRIGGER_PCT = 0.50
RATCHET_TRIGGER_PCT = 1.20
RATCHET_KEEP_RATIO = 0.60
INVALIDATION_BUFFER_PCT = 0.20
STAGNATION_WINDOW_SEC = 180.0
STAGNATION_GROSS_TARGET = 0.25


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def evaluate_sweet_spot(candles, pct_15m, now_ms=None):
    result = {
        "is_valid": False, "reason": "INVALID",
        "pct_15m": pct_15m,
        "drop_3m": 0.0, "drop_6m": 0.0, "vol_ratio": 0.0,
        "low_10m": 0.0, "live_close": 0.0,
    }
    if not candles or len(candles) < 16:
        return result
    candles = candles[-16:]

    try:
        live_close = float(candles[-1][4])
        candle_ts = int(candles[-1][0])
        live_vol = float(candles[-1][5])
    except (IndexError, TypeError, ValueError):
        return result

    result["live_close"] = live_close
    if live_close <= 0:
        return result

    if not (PCT_15M_MIN_DROP <= pct_15m <= PCT_15M_MAX_DROP):
        result["reason"] = "RANGE"
        return result

    try:
        close_9m_ago = float(candles[-10][4])
        close_3m_ago = float(candles[-4][4])
    except (IndexError, TypeError, ValueError):
        return result
    if close_9m_ago <= 0 or close_3m_ago <= 0:
        return result

    drop_6m = (close_9m_ago - close_3m_ago) / close_9m_ago * 100.0
    drop_3m = (close_3m_ago - live_close) / close_3m_ago * 100.0
    result["drop_6m"] = drop_6m
    result["drop_3m"] = drop_3m

    # Raised gate: real collapses show drop3 >= 1.5% at ignition
    if drop_3m < ACCEL_DROP_3M_MIN:
        result["reason"] = "ACCEL_WEAK"
        return result

    if drop_6m <= DROP6_MIN_PCT:
        result["reason"] = "ACCEL_BOUNCE"
        return result

    rate_3m = drop_3m / 3.0
    rate_6m = drop_6m / 6.0
    if rate_3m < rate_6m * ACCELERATION_MIN_RATIO:
        result["reason"] = "ACCEL_SLOW"
        return result

    try:
        avg_vol_15m = sum(float(c[5]) for c in candles[-16:-1]) / 15.0
    except (IndexError, TypeError, ValueError):
        return result
    if avg_vol_15m <= 0:
        result["reason"] = "VOLUME"
        return result

    if now_ms is None:
        now_ms = int(time.time() * 1000)
    elapsed_s = max(1.0, (now_ms - candle_ts) / 1000.0)
    if elapsed_s < _MIN_ELAPSED_SEC:
        result["reason"] = "EARLY"
        return result

    multiplier = min(60.0 / elapsed_s, _VOL_MAX_EXTRAPOLATION)
    vol_ratio = (live_vol * multiplier) / avg_vol_15m
    result["vol_ratio"] = vol_ratio

    if vol_ratio < VOLUME_EXPANSION_MIN:
        result["reason"] = "VOLUME"
        return result

    try:
        lows = [float(c[3]) for c in candles[-11:-1]]
    except (IndexError, TypeError, ValueError):
        return result
    if not lows:
        return result
    low_10m = min(lows)
    result["low_10m"] = low_10m
    if low_10m <= 0:
        return result

    if live_close >= low_10m * (1.0 - BREAKDOWN_BUFFER_PCT / 100.0):
        result["reason"] = "BREAKDOWN"
        return result

    if live_close < low_10m * (1.0 - ANTI_CHASE_MAX_PCT / 100.0):
        result["reason"] = "CHASE"
        return result

    result["is_valid"] = True
    result["reason"] = "OK"
    return result


def evaluate_macro_alignment(hourly_candles, current_price,
                             max_pct_above_low=MACRO_ALIGN_MAX_PCT):
    """
    Reject SHORTs inside a relief bounce.

    Reference low = min(low_1h, low_4h) = low_4h (wider window dominates).
    Reject when current_price is more than max_pct_above_low above it.
    """
    result = {
        "is_aligned": False, "reason": "INVALID",
        "low_1h": 0.0, "low_4h": 0.0, "ref_low": 0.0,
        "pct_above_ref": 0.0,
    }
    if not hourly_candles or len(hourly_candles) < 4 or current_price <= 0:
        return result

    try:
        low_1h = float(hourly_candles[-1][3])
        low_4h = min(float(c[3]) for c in hourly_candles[-4:])
    except (IndexError, TypeError, ValueError):
        return result

    if low_1h <= 0 or low_4h <= 0:
        return result

    result["low_1h"] = low_1h
    result["low_4h"] = low_4h
    ref_low = min(low_1h, low_4h)
    result["ref_low"] = ref_low

    pct_above = (current_price - ref_low) / ref_low * 100.0
    result["pct_above_ref"] = pct_above

    if pct_above <= max_pct_above_low:
        result["is_aligned"] = True
        result["reason"] = "OK"
    else:
        result["reason"] = "TOO_HIGH_ABOVE_LOW"
    return result


def evaluate_spread(bids, asks, max_spread_pct=MAX_SPREAD_PCT):
    result = {"is_ok": False, "spread_pct": 999.0, "mid": 0.0}
    if not bids or not asks:
        return result
    try:
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
    except (IndexError, TypeError, ValueError):
        return result
    if best_bid <= 0 or best_ask <= 0 or best_ask <= best_bid:
        return result
    mid = (best_bid + best_ask) / 2.0
    spread_pct = (best_ask - best_bid) / mid * 100.0
    result["spread_pct"] = spread_pct
    result["mid"] = mid
    result["is_ok"] = spread_pct <= max_spread_pct
    return result


def evaluate_book_fragility(bids, asks, mid_price,
                            band_pct=DEPTH_BAND_PCT,
                            min_side_depth=MIN_SIDE_DEPTH_USD,
                            max_bid_depth=MAX_BID_DEPTH_USD):
    result = {"is_fragile": False, "reason": "INVALID",
              "depth_ratio": 0.0, "d_bid": 0.0, "d_ask": 0.0}
    if mid_price <= 0 or not bids or not asks:
        return result

    bid_floor = mid_price * (1.0 - band_pct)
    ask_ceil = mid_price * (1.0 + band_pct)

    d_bid = 0.0
    d_ask = 0.0
    for p, q in bids:
        pf = _f(p)
        if pf >= bid_floor:
            d_bid += pf * _f(q)
    for p, q in asks:
        pf = _f(p)
        if pf <= ask_ceil:
            d_ask += pf * _f(q)

    result["d_bid"] = d_bid
    result["d_ask"] = d_ask
    ratio = (d_ask / d_bid) if d_bid > 0 else 0.0
    result["depth_ratio"] = ratio

    if d_bid < min_side_depth:
        result["reason"] = "THIN_BID"
        return result
    if d_bid > max_bid_depth:
        result["reason"] = "WHALE_BID"
        return result
    if ratio >= FRAGILITY_RATIO_MIN:
        result["is_fragile"] = True
        result["reason"] = "OK"
    else:
        result["reason"] = "LOW_RATIO"
    return result


def calculate_order_qty(balance, price, leverage, volume_place,
                        min_order_volume, min_notional=5.0):
    if balance <= 0 or price <= 0 or leverage <= 0:
        return None
    notional = balance * 0.90 * leverage
    if notional < min_notional:
        return None
    vp = int(volume_place)
    qty = round(notional / price, vp)
    if qty <= 0:
        return None
    if min_order_volume > 0 and qty < min_order_volume:
        return None
    if qty * price < min_notional:
        return None
    return f"{qty:.{vp}f}"


def evaluate_ratchet(entry_price, current_price, breakdown_level,
                     peak_net, peak_gross, elapsed_seconds):
    result = {
        "should_exit": False, "exit_reason": "HOLD",
        "net_pnl": 0.0, "gross_pnl": 0.0,
        "updated_peak_net": peak_net,
        "updated_peak_gross": peak_gross,
    }
    if entry_price <= 0 or current_price <= 0:
        return result

    gross = (entry_price - current_price) / entry_price * 100.0
    net = gross - FEE_ROUND_TRIP_PCT
    new_peak_net = peak_net if peak_net > net else net
    new_peak_gross = peak_gross if peak_gross > gross else gross

    result["gross_pnl"] = gross
    result["net_pnl"] = net
    result["updated_peak_net"] = new_peak_net
    result["updated_peak_gross"] = new_peak_gross

    if breakdown_level > 0:
        if current_price > breakdown_level * (1.0 + INVALIDATION_BUFFER_PCT / 100.0):
            result["should_exit"] = True
            result["exit_reason"] = "INVALIDATION_STOP"
            return result

    if new_peak_net >= BREAKEVEN_TRIGGER_PCT and net <= 0.0:
        result["should_exit"] = True
        result["exit_reason"] = "BREAKEVEN_SHIELD"
        return result

    if new_peak_net >= RATCHET_TRIGGER_PCT:
        floor = RATCHET_KEEP_RATIO * new_peak_net
        if net <= floor:
            result["should_exit"] = True
            result["exit_reason"] = "RATCHET_BANK"
            return result

    if (elapsed_seconds >= STAGNATION_WINDOW_SEC
            and new_peak_gross < STAGNATION_GROSS_TARGET
            and gross < 0.0):
        result["should_exit"] = True
        result["exit_reason"] = "STAGNATION_CUT"
        return result

    return result


def compute_crash_metrics(hourly_candles):
    """
    FIX: also returns the actual timestamp of the 4h-high candle, so the
    observer reports real elapsed minutes since the peak — not "0m".
    """
    out = {
        "high_1h": 0.0, "high_4h": 0.0, "low_4h": 0.0,
        "current_price": 0.0, "high_4h_ts_ms": 0,
    }
    if not hourly_candles or len(hourly_candles) < 4:
        return out
    try:
        out["current_price"] = float(hourly_candles[-1][4])
        out["high_1h"] = float(hourly_candles[-1][2])
        last4 = hourly_candles[-4:]
        highs_with_ts = [(float(c[2]), int(c[0])) for c in last4]
        high_4h, high_4h_ts_ms = max(highs_with_ts, key=lambda x: x[0])
        out["high_4h"] = high_4h
        out["high_4h_ts_ms"] = high_4h_ts_ms
        out["low_4h"] = min(float(c[3]) for c in last4)
    except (IndexError, TypeError, ValueError):
        pass
    return out


def drop_pct_from_high(high, current):
    if high <= 0 or current <= 0 or current >= high:
        return 0.0
    return (high - current) / high * 100.0


def classify_velocity(time_to_crash_minutes):
    if time_to_crash_minutes < 20.0:
        return "PANIC"
    if time_to_crash_minutes < 40.0:
        return "MEDIUM"
    return "SLOW_BLEED"
