"""
market_math.py
==============
Velocity-based momentum learning engine.

v2026.11.20: learns asymmetry per coin.
  Spike = velocity >= 5x baseline, direction down.
  Asymmetry = peak_velocity / reversal_velocity (higher = quieter reversal).
  Only coins with median asymmetry >= 4.0 are tradable.

Exit logic: momentum death (velocity back to baseline) or symmetric reversal.
No stop loss. No profit target. Time cap only.
"""

import time

__version__ = "2026.11.20"

FEE_ROUND_TRIP_PCT = 0.22

# ---- Learning ----
SPIKE_VELOCITY_THRESHOLD = 5.0
MIN_ASYMMETRY_RATIO = 4.0
NOISE_ASYMMETRY_MAX = 2.0
SPIKE_WINDOW_SEC = 1200.0
SPIKE_SETTLED_RATIO = 2.0
SPIKE_SETTLED_CONSECUTIVE = 3
SPIKE_MIN_SETTLE_AFTER_PEAK_SEC = 60.0
VELOCITY_HISTORY_SEC = 600.0
MIN_SAMPLES_FOR_VELOCITY = 5

# ---- Exit ----
MOMENTUM_DEATH_RATIO = 1.2
MOMENTUM_DEATH_CONSECUTIVE = 3
SYMMETRIC_REVERSAL_MULTIPLE = 2.0
SYMMETRIC_REVERSAL_CONSECUTIVE = 2
HARD_STOP_PCT = 5.0
MAX_HOLD_SEC = 1200.0
MIN_HOLD_FOR_EXIT_CHECK_SEC = 30.0

# ---- Book ----
DEPTH_BAND_PCT = 0.01
MIN_SIDE_DEPTH_USD = 1000.0
MAX_BID_DEPTH_USD = 500000.0
MAX_SPREAD_PCT = 0.20


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def compute_ticker_velocity(price_history, now_ts):
    """Velocity multiple + baseline + direction from 4-15s ticker samples."""
    result = {
        "velocity_multiple": 0.0,
        "recent_pct_per_min": 0.0,
        "baseline_pct_per_min": 0.0,
        "samples": 0,
        "direction": 0,
        "reason": "INVALID",
    }
    if not price_history or len(price_history) < MIN_SAMPLES_FOR_VELOCITY:
        return result

    cutoff = now_ts - VELOCITY_HISTORY_SEC
    history = [(t, p) for t, p in price_history if t >= cutoff and p > 0]
    if len(history) < MIN_SAMPLES_FOR_VELOCITY:
        return result
    result["samples"] = len(history)

    if len(history) < 4:
        return result
    recent = history[-4:]
    p_first = recent[0][1]
    p_last = recent[-1][1]
    dt_recent = recent[-1][0] - recent[0][0]
    if dt_recent <= 0 or p_first <= 0:
        return result

    recent_return = (p_last - p_first) / p_first
    recent_per_min = recent_return * (60.0 / dt_recent)
    result["recent_pct_per_min"] = recent_per_min * 100.0
    result["direction"] = 1 if recent_per_min > 0 else -1

    baseline_slice = history[:-4]
    if len(baseline_slice) < 3:
        return result

    baseline_rates = []
    for i in range(1, len(baseline_slice)):
        t0, p0 = baseline_slice[i - 1]
        t1, p1 = baseline_slice[i]
        dt = t1 - t0
        if dt <= 0 or p0 <= 0:
            continue
        dp = abs((p1 - p0) / p0)
        rate_per_min = dp * (60.0 / dt)
        baseline_rates.append(rate_per_min)

    if not baseline_rates:
        return result
    baseline_rates.sort()
    baseline_per_min = baseline_rates[len(baseline_rates) // 2]
    if baseline_per_min <= 0.00001:
        baseline_per_min = 0.00001
    result["baseline_pct_per_min"] = baseline_per_min * 100.0

    multiple = abs(recent_per_min) / baseline_per_min
    result["velocity_multiple"] = multiple
    result["reason"] = "OK"
    return result


def is_spike(vel_result):
    """Velocity >= 5x baseline, direction down."""
    if vel_result["reason"] != "OK":
        return False
    if vel_result["direction"] >= 0:
        return False
    return vel_result["velocity_multiple"] >= SPIKE_VELOCITY_THRESHOLD


def check_momentum_death(vel_result):
    """Velocity back to baseline — momentum has died."""
    if vel_result["reason"] != "OK":
        return False
    baseline = vel_result["baseline_pct_per_min"]
    if baseline <= 0.00001:
        return False
    recent = abs(vel_result["recent_pct_per_min"])
    return recent <= MOMENTUM_DEATH_RATIO * baseline


def check_symmetric_reversal(vel_result):
    """Up-velocity >= SYMMETRIC_REVERSAL_MULTIPLE * baseline."""
    if vel_result["reason"] != "OK":
        return False
    if vel_result["recent_pct_per_min"] <= 0:
        return False
    baseline = vel_result["baseline_pct_per_min"]
    if baseline <= 0.00001:
        return False
    up_ratio = vel_result["recent_pct_per_min"] / baseline
    return up_ratio >= SYMMETRIC_REVERSAL_MULTIPLE


def evaluate_book(bids, asks, mid_price):
    """Sanity check for book depth. Rejects thin bids and whale walls."""
    result = {"is_valid": False, "reason": "INVALID",
              "depth_ratio": 0.0, "d_bid": 0.0, "d_ask": 0.0}
    if mid_price <= 0 or not bids or not asks:
        return result

    bid_floor = mid_price * (1.0 - DEPTH_BAND_PCT)
    ask_ceil = mid_price * (1.0 + DEPTH_BAND_PCT)

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

    if d_bid < MIN_SIDE_DEPTH_USD:
        result["reason"] = "THIN_BID"
        return result
    if d_bid > MAX_BID_DEPTH_USD:
        result["reason"] = "WHALE_BID"
        return result
    result["is_valid"] = True
    result["reason"] = "OK"
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


def verdict_for(asymmetry):
    if asymmetry >= MIN_ASYMMETRY_RATIO:
        return "MOMENTUM"
    if asymmetry < NOISE_ASYMMETRY_MAX:
        return "NOISE"
    return "MIDDLE"
