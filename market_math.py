"""
market_math.py
==============
Multi-strategy momentum engine.

v2026.11.22 — Four trade types:
  MOMENTUM  : 8%+ clean move in <30 min, proven 4:1+ asymmetry, SHORT only
  RANGE     : 24h range >=6%, net displacement <=10%, entry at edges
  ROTATION  : every 30 min, pick best momentum-persistence coin
  VOLUME    : every 30 min, best dump%/volume (SHORT) vs pump%/volume (LONG)
"""

import math
import time

__version__ = "2026.11.22"

FEE_ROUND_TRIP_PCT = 0.22

# ---- Momentum ----
MOVE_THRESHOLD_PCT = 8.0
MOVE_MAX_DURATION_SEC = 1800
MOVE_MAX_INTERIM_REVERSAL_PCT = 2.0
PRICE_WINDOW_SEC = 1800
REVERSAL_START_RETRACE_PCT = 1.0
REVERSAL_START_CONFIRM_SEC = 60
REVERSAL_MEASURE_MAX_SEC = 1800
REVERSAL_STABILITY_SEC = 300
MIN_ASYMMETRY_RATIO = 4.0
NOISE_ASYMMETRY_MAX = 1.5
MOMENTUM_EXIT_REVERSAL_PCT = 2.0
MOMENTUM_EXIT_HARD_STOP_PCT = 3.0
MOMENTUM_MAX_HOLD_SEC = 1800.0

# ---- Range ----
RANGE_MIN_RANGE_PCT = 6.0
RANGE_MAX_NET_DISPLACEMENT_PCT = 10.0
RANGE_MIN_CROSSOVERS_1H = 2
RANGE_ENTRY_BUFFER_PCT = 1.0
RANGE_BREAK_BUFFER_PCT = 1.0
RANGE_MAX_HOLD_SEC = 3600.0

# ---- Rotation / Volume ----
ROTATION_MIN_HISTORY_SEC = 900
ROTATION_EXIT_HARD_STOP_PCT = 3.0
ROTATION_MAX_HOLD_SEC = 1800.0

VOLUME_EXIT_HARD_STOP_PCT = 3.0
VOLUME_MAX_HOLD_SEC = 1800.0

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


# =========================================================================
# MOMENTUM
# =========================================================================
def find_qualifying_move(price_window, now_ts):
    result = {
        "qualified": False, "reason": "DATA", "direction": None,
        "start_price": 0.0, "start_ts": 0,
        "peak_price": 0.0, "peak_ts": 0,
        "move_pct": 0.0, "move_duration_sec": 0,
        "move_speed_pct_per_min": 0.0,
    }
    if not price_window or len(price_window) < 3:
        return result

    window = [(t, p) for t, p in price_window if p > 0]
    if len(window) < 3:
        return result

    current_ts, current_price = window[-1]
    max_price, max_ts = max(window, key=lambda x: x[1])
    min_price, min_ts = min(window, key=lambda x: x[1])

    down_pct = (max_price - current_price) / max_price * 100.0 if max_price > 0 else 0.0
    up_pct = (current_price - min_price) / min_price * 100.0 if min_price > 0 else 0.0

    if down_pct >= MOVE_THRESHOLD_PCT and down_pct >= up_pct:
        direction = "down"
        start_price = max_price
        start_ts = max_ts
        move_pct = down_pct
    elif up_pct >= MOVE_THRESHOLD_PCT:
        direction = "up"
        start_price = min_price
        start_ts = min_ts
        move_pct = up_pct
    else:
        result["reason"] = "NO_MOVE"
        return result

    duration = current_ts - start_ts
    if duration > MOVE_MAX_DURATION_SEC:
        result["reason"] = "TOO_SLOW"
        return result
    if duration <= 0:
        result["reason"] = "ZERO_DURATION"
        return result

    move_slice = [(t, p) for t, p in window if start_ts <= t <= current_ts]
    if not move_slice:
        result["reason"] = "NO_SLICE"
        return result

    if direction == "down":
        running_low = start_price
        for t, p in move_slice:
            if p < running_low:
                running_low = p
            else:
                retrace = (p - running_low) / running_low * 100.0
                if retrace > MOVE_MAX_INTERIM_REVERSAL_PCT:
                    result["reason"] = f"INTERIM_{retrace:.2f}"
                    return result
    else:
        running_high = start_price
        for t, p in move_slice:
            if p > running_high:
                running_high = p
            else:
                retrace = (running_high - p) / running_high * 100.0
                if retrace > MOVE_MAX_INTERIM_REVERSAL_PCT:
                    result["reason"] = f"INTERIM_{retrace:.2f}"
                    return result

    result["qualified"] = True
    result["reason"] = "OK"
    result["direction"] = direction
    result["start_price"] = start_price
    result["start_ts"] = start_ts
    result["peak_price"] = current_price
    result["peak_ts"] = current_ts
    result["move_pct"] = move_pct
    result["move_duration_sec"] = duration
    result["move_speed_pct_per_min"] = move_pct / (duration / 60.0)
    return result


def check_reversal_started(direction, peak_price, current_price,
                           reversal_start_ts, now_ts):
    if peak_price <= 0 or current_price <= 0:
        return 0.0, False, 0
    if direction == "down":
        retrace = (current_price - peak_price) / peak_price * 100.0
    else:
        retrace = (peak_price - current_price) / peak_price * 100.0
    if retrace >= REVERSAL_START_RETRACE_PCT:
        if reversal_start_ts == 0:
            return retrace, False, now_ts
        if now_ts - reversal_start_ts >= REVERSAL_START_CONFIRM_SEC:
            return retrace, True, reversal_start_ts
        return retrace, False, reversal_start_ts
    return retrace, False, 0


def measure_reversal(price_window, direction, peak_ts, peak_price, now_ts):
    result = {
        "complete": False, "reason": "MEASURING",
        "reversal_end_price": 0.0, "reversal_end_ts": 0,
        "reversal_pct": 0.0, "reversal_duration_sec": 0,
        "reversal_speed_pct_per_min": 0.0,
    }
    if not price_window or peak_price <= 0 or peak_ts <= 0:
        return result

    post_peak = [(t, p) for t, p in price_window if t > peak_ts and p > 0]
    if not post_peak:
        return result

    elapsed = now_ts - peak_ts

    if direction == "down":
        extreme_price, extreme_ts = max(post_peak, key=lambda x: x[1])
        reversal_pct = (extreme_price - peak_price) / peak_price * 100.0
    else:
        extreme_price, extreme_ts = min(post_peak, key=lambda x: x[1])
        reversal_pct = (peak_price - extreme_price) / peak_price * 100.0

    duration = extreme_ts - peak_ts
    if duration <= 0:
        return result

    result["reversal_end_price"] = extreme_price
    result["reversal_end_ts"] = extreme_ts
    result["reversal_pct"] = reversal_pct
    result["reversal_duration_sec"] = duration
    if reversal_pct > 0:
        result["reversal_speed_pct_per_min"] = reversal_pct / (duration / 60.0)

    if elapsed >= REVERSAL_MEASURE_MAX_SEC:
        result["complete"] = True
        result["reason"] = "WINDOW_ELAPSED"
    elif (reversal_pct >= REVERSAL_START_RETRACE_PCT
          and (now_ts - extreme_ts) >= REVERSAL_STABILITY_SEC):
        result["complete"] = True
        result["reason"] = "STABILIZED"

    return result


def compute_asymmetry(move_speed_pct_per_min, reversal_speed_pct_per_min):
    if move_speed_pct_per_min <= 0:
        return 0.0
    if reversal_speed_pct_per_min <= 0:
        return 20.0
    return move_speed_pct_per_min / reversal_speed_pct_per_min


def classify_asymmetry(asym):
    if asym >= MIN_ASYMMETRY_RATIO:
        return "MOMENTUM"
    if asym <= NOISE_ASYMMETRY_MAX:
        return "NOISE"
    return "MIDDLE"


# =========================================================================
# RANGE
# =========================================================================
def evaluate_range_coin(range_pct, net_pct, crossovers_1h):
    result = {
        "is_range": False, "reason": "INVALID",
        "range_pct": range_pct, "net_pct": net_pct,
        "crossovers_1h": crossovers_1h,
    }
    if range_pct <= 0:
        return result
    if range_pct < RANGE_MIN_RANGE_PCT:
        result["reason"] = "RANGE_TOO_SMALL"
        return result
    if abs(net_pct) > RANGE_MAX_NET_DISPLACEMENT_PCT:
        result["reason"] = "DISPLACED"
        return result
    if crossovers_1h < RANGE_MIN_CROSSOVERS_1H:
        result["reason"] = "LOW_OSCILLATION"
        return result
    result["is_range"] = True
    result["reason"] = "OK"
    return result


def evaluate_range_entry(current_price, range_low, range_high):
    result = {
        "should_enter": False, "side": None, "reason": "WAIT",
        "pct_from_high": 0.0, "pct_from_low": 0.0, "range_mid": 0.0,
    }
    if range_high <= 0 or range_low <= 0 or current_price <= 0:
        return result
    if range_high <= range_low:
        return result

    range_mid = (range_high + range_low) / 2.0
    result["range_mid"] = range_mid

    pct_from_high = (range_high - current_price) / range_high * 100.0
    pct_from_low = (current_price - range_low) / range_low * 100.0
    result["pct_from_high"] = round(pct_from_high, 2)
    result["pct_from_low"] = round(pct_from_low, 2)

    if pct_from_high <= RANGE_ENTRY_BUFFER_PCT:
        result["should_enter"] = True
        result["side"] = "SHORT"
        result["reason"] = "NEAR_HIGH"
        return result
    if pct_from_low <= RANGE_ENTRY_BUFFER_PCT:
        result["should_enter"] = True
        result["side"] = "LONG"
        result["reason"] = "NEAR_LOW"
        return result
    result["reason"] = "MIDDLE"
    return result


# =========================================================================
# ROTATION
# =========================================================================
def compute_rotation_score(price_history, now_ts):
    result = {
        "score": 0.0, "direction": None,
        "change_15m_pct": 0.0, "change_5m_pct": 0.0,
    }
    if not price_history:
        return result

    cutoff_15m = now_ts - 900
    prices_15m = [(t, p) for t, p in price_history if t >= cutoff_15m and p > 0]
    if len(prices_15m) < 4:
        return result

    oldest_15m = prices_15m[0][1]
    newest = prices_15m[-1][1]
    if oldest_15m <= 0:
        return result
    change_15m_pct = (newest - oldest_15m) / oldest_15m * 100.0
    result["change_15m_pct"] = change_15m_pct

    cutoff_5m = now_ts - 300
    prices_5m = [(t, p) for t, p in prices_15m if t >= cutoff_5m]
    if len(prices_5m) < 2:
        return result
    oldest_5m = prices_5m[0][1]
    if oldest_5m <= 0:
        return result
    change_5m_pct = (newest - oldest_5m) / oldest_5m * 100.0
    result["change_5m_pct"] = change_5m_pct

    if change_15m_pct * change_5m_pct > 0:
        consistency = 1.0
    else:
        consistency = 0.5

    score = abs(change_15m_pct) * abs(change_5m_pct) * consistency
    result["score"] = score
    result["direction"] = "LONG" if change_15m_pct > 0 else "SHORT"
    return result


# =========================================================================
# VOLUME
# =========================================================================
def compute_volume_scores(current_price, high_24h, low_24h, volume_24h_usd):
    result = {
        "short_score": 0.0, "long_score": 0.0,
        "dump_pct": 0.0, "pump_pct": 0.0,
    }
    if (current_price <= 0 or high_24h <= 0 or low_24h <= 0
            or volume_24h_usd <= 0):
        return result
    if high_24h < low_24h:
        return result

    dump_pct = (high_24h - current_price) / high_24h * 100.0
    pump_pct = (current_price - low_24h) / low_24h * 100.0
    result["dump_pct"] = dump_pct
    result["pump_pct"] = pump_pct

    vol_m = volume_24h_usd / 1_000_000.0
    denom = max(1.0, math.log10(vol_m + 1.0))

    if dump_pct > 0:
        result["short_score"] = dump_pct / denom
    if pump_pct > 0:
        result["long_score"] = pump_pct / denom
    return result


# =========================================================================
# EXIT LOGIC PER TYPE
# =========================================================================
def check_momentum_exit(entry_price, extreme_since_entry, current_price,
                        elapsed_sec):
    result = {
        "should_exit": False, "exit_reason": "HOLD",
        "gross_pnl": 0.0, "net_pnl": 0.0, "retrace_from_extreme_pct": 0.0,
    }
    if entry_price <= 0 or current_price <= 0:
        return result

    gross = (entry_price - current_price) / entry_price * 100.0
    net = gross - FEE_ROUND_TRIP_PCT
    result["gross_pnl"] = gross
    result["net_pnl"] = net

    if net <= -MOMENTUM_EXIT_HARD_STOP_PCT:
        result["should_exit"] = True
        result["exit_reason"] = "HARD_STOP"
        return result
    if elapsed_sec >= MOMENTUM_MAX_HOLD_SEC:
        result["should_exit"] = True
        result["exit_reason"] = "TIME_EXIT"
        return result
    if extreme_since_entry > 0:
        retrace = (current_price - extreme_since_entry) / extreme_since_entry * 100.0
        result["retrace_from_extreme_pct"] = retrace
        if retrace >= MOMENTUM_EXIT_REVERSAL_PCT:
            result["should_exit"] = True
            result["exit_reason"] = "REVERSAL_CONFIRMED"
            return result
    return result


def check_range_exit(entry_price, side, range_high, range_low, range_mid,
                     current_price, elapsed_sec):
    result = {
        "should_exit": False, "exit_reason": "HOLD",
        "gross_pnl": 0.0, "net_pnl": 0.0,
    }
    if entry_price <= 0 or current_price <= 0:
        return result

    if side == "SHORT":
        gross = (entry_price - current_price) / entry_price * 100.0
    else:
        gross = (current_price - entry_price) / entry_price * 100.0

    net = gross - FEE_ROUND_TRIP_PCT
    result["gross_pnl"] = gross
    result["net_pnl"] = net

    if (side == "SHORT"
            and current_price > range_high * (1.0 + RANGE_BREAK_BUFFER_PCT / 100.0)):
        result["should_exit"] = True
        result["exit_reason"] = "RANGE_BREAK_UP"
        return result
    if (side == "LONG"
            and current_price < range_low * (1.0 - RANGE_BREAK_BUFFER_PCT / 100.0)):
        result["should_exit"] = True
        result["exit_reason"] = "RANGE_BREAK_DOWN"
        return result

    if side == "SHORT" and current_price <= range_mid:
        result["should_exit"] = True
        result["exit_reason"] = "TARGET_MID"
        return result
    if side == "LONG" and current_price >= range_mid:
        result["should_exit"] = True
        result["exit_reason"] = "TARGET_MID"
        return result

    if elapsed_sec >= RANGE_MAX_HOLD_SEC:
        result["should_exit"] = True
        result["exit_reason"] = "TIME_EXIT"
        return result
    return result


def check_fixed_cycle_exit(entry_price, side, current_price, elapsed_sec,
                           hard_stop_pct, max_hold_sec):
    result = {
        "should_exit": False, "exit_reason": "HOLD",
        "gross_pnl": 0.0, "net_pnl": 0.0,
    }
    if entry_price <= 0 or current_price <= 0:
        return result

    if side == "SHORT":
        gross = (entry_price - current_price) / entry_price * 100.0
    else:
        gross = (current_price - entry_price) / entry_price * 100.0

    net = gross - FEE_ROUND_TRIP_PCT
    result["gross_pnl"] = gross
    result["net_pnl"] = net

    if net <= -hard_stop_pct:
        result["should_exit"] = True
        result["exit_reason"] = "HARD_STOP"
        return result
    if elapsed_sec >= max_hold_sec:
        result["should_exit"] = True
        result["exit_reason"] = "TIME_EXIT"
        return result
    return result


# =========================================================================
# BOOK / SPREAD / SIZING
# =========================================================================
def evaluate_book(bids, asks, mid_price):
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
    result["depth_ratio"] = (d_ask / d_bid) if d_bid > 0 else 0.0
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
