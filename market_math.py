"""
market_math.py
==============
Cross-Sectional Relative Weakness & Accelerated Breakdown Engine.

v2026.11.15: restructured 13 filters -> 5 combined gates.
  - MOMENTUM merges: rng + aw + ab + as + vol
  - POSITION merges: bd + chs
  - MACRO v2: pass if near 1h-low OR 4h-low (catches fresh breakdowns)
  - BOOK merges: fr + fthin + fwhl (ratio >= 1.40, $2K-$150K)
"""

import time

__version__ = "2026.11.15"

FEE_ROUND_TRIP_PCT = 0.22

# ---- MOMENTUM ----
PCT_15M_MIN_DROP = -8.0            # widened from -7.0
PCT_15M_MAX_DROP = -1.0            # widened from -1.5
DROP3_MIN_PCT = 0.60               # was 1.50 — the big loosening
DROP6_MIN_PCT = -0.30              # allow small bounce (was 0.15 strict)
ACCELERATION_MIN_RATIO = 0.7       # allow moderate slowing (was 1.0)
VOLUME_EXPANSION_MIN = 1.8         # was 3.0
_VOL_MAX_EXTRAPOLATION = 3.0
_MIN_ELAPSED_SEC = 20.0

# ---- POSITION ----
BREAKDOWN_BUFFER_PCT = 0.05        # must break below 10m low by 0.05%
ANTI_CHASE_MAX_PCT = 1.00          # not more than 1.0% past breakdown (was 0.60)

# ---- MACRO (v2) ----
MACRO_1H_MAX_PCT = 3.0             # OR: close <= low_1h * 1.03
MACRO_4H_MAX_PCT = 4.0             # OR: close <= low_4h * 1.04

# ---- BOOK ----
DEPTH_BAND_PCT = 0.01
MIN_SIDE_DEPTH_USD = 2000.0        # was 5000 — small alt books allowed
MAX_BID_DEPTH_USD = 150000.0       # was 100K — absorbed walls allowed
FRAGILITY_RATIO_MIN = 1.40         # was 1.80

# ---- SPREAD ----
MAX_SPREAD_PCT = 0.20              # was 0.15

# ---- Ratchet / risk ----
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


# =========================================================================
# GATE 1: MOMENTUM (was rng + aw + ab + as + vol)
# =========================================================================
def evaluate_momentum(candles, pct_15m, now_ms=None):
    """
    Combined momentum gate. Returns:
      RANGE / ACCEL_WEAK / ACCEL_BOUNCE / ACCEL_SLOW / VOLUME / EARLY / OK
    """
    result = {
        "is_valid": False, "reason": "INVALID",
        "pct_15m": pct_15m,
        "drop_3m": 0.0, "drop_6m": 0.0, "vol_ratio": 0.0,
        "live_close": 0.0, "low_10m": 0.0,
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

    if drop_3m < DROP3_MIN_PCT:
        result["reason"] = "ACCEL_WEAK"
        return result

    if drop_6m < DROP6_MIN_PCT:
        result["reason"] = "ACCEL_BOUNCE"
        return result

    rate_3m = drop_3m / 3.0
    rate_6m = drop_6m / 6.0
    if rate_6m > 0.0 and rate_3m < rate_6m * ACCELERATION_MIN_RATIO:
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

    # Store low_10m here for gate 2 to reuse
    try:
        lows = [float(c[3]) for c in candles[-11:-1]]
        if lows:
            result["low_10m"] = min(lows)
    except (IndexError, TypeError, ValueError):
        pass

    result["is_valid"] = True
    result["reason"] = "OK"
    return result


# =========================================================================
# GATE 2: POSITION (was bd + chs)
# =========================================================================
def evaluate_position(live_close, low_10m):
    """
    Breakout OR chase check.
    """
    result = {"is_valid": False, "reason": "INVALID",
              "chase_pct": 0.0}
    if live_close <= 0 or low_10m <= 0:
        return result

    # Must break below 10m low
    if live_close >= low_10m * (1.0 - BREAKDOWN_BUFFER_PCT / 100.0):
        result["reason"] = "NO_BREAKDOWN"
        return result

    # Must not be too far past
    if live_close < low_10m * (1.0 - ANTI_CHASE_MAX_PCT / 100.0):
        result["reason"] = "CHASE"
        result["chase_pct"] = (low_10m - live_close) / low_10m * 100.0
        return result

    result["chase_pct"] = (low_10m - live_close) / low_10m * 100.0
    result["is_valid"] = True
    result["reason"] = "OK"
    return result


# =========================================================================
# GATE 3: MACRO (v2 — 1h OR 4h low)
# =========================================================================
def evaluate_macro(hourly_candles, current_price):
    """
    Pass if price within MACRO_1H_MAX_PCT of 1h low
    OR within MACRO_4H_MAX_PCT of 4h low.
    """
    result = {
        "is_aligned": False, "reason": "INVALID",
        "low_1h": 0.0, "low_4h": 0.0,
        "pct_above_1h": 0.0, "pct_above_4h": 0.0,
        "which": "",
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
    result["pct_above_1h"] = (current_price - low_1h) / low_1h * 100.0
    result["pct_above_4h"] = (current_price - low_4h) / low_4h * 100.0

    if result["pct_above_1h"] <= MACRO_1H_MAX_PCT:
        result["is_aligned"] = True
        result["reason"] = "OK"
        result["which"] = "1H"
        return result
    if result["pct_above_4h"] <= MACRO_4H_MAX_PCT:
        result["is_aligned"] = True
        result["reason"] = "OK"
        result["which"] = "4H"
        return result

    result["reason"] = "TOO_HIGH"
    return result


# =========================================================================
# GATE 4: BOOK (was fr + fthin + fwhl)
# =========================================================================
def evaluate_book(bids, asks, mid_price,
                  band_pct=DEPTH_BAND_PCT,
                  min_side_depth=MIN_SIDE_DEPTH_USD,
                  max_bid_depth=MAX_BID_DEPTH_USD):
    """
    Combined book gate: ratio + thin-bid + whale-bid.
    """
    result = {"is_valid": False, "reason": "INVALID",
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
    if ratio < FRAGILITY_RATIO_MIN:
        result["reason"] = "LOW_RATIO"
        return result

    result["is_valid"] = True
    result["reason"] = "OK"
    return result


# =========================================================================
# GATE 5: SPREAD
# =========================================================================
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


# =========================================================================
# SIZING / RATCHET (unchanged)
# =========================================================================
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


# =========================================================================
# OBSERVER helpers (unchanged)
# =========================================================================
def compute_crash_metrics(hourly_candles):
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
