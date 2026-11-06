"""
market_math.py
==============
Cross-Sectional Relative Weakness & Accelerated Breakdown Engine.

v2026.11.17: dedicated PANIC path.
  Ranker sees movers down to -30% in 15m (was -8% floor).
  Deep movers (< -8%) routed to evaluate_momentum_panic() —
  6 checks instead of 10. Catches live liquidation cascades.
"""

import time

__version__ = "2026.11.17"

FEE_ROUND_TRIP_PCT = 0.22

# ---- Normal path ----
PCT_15M_MIN_DROP = -30.0           # was -8.0 (ranker floor; deep routed to panic)
PCT_15M_MAX_DROP = -1.0
DROP3_MIN_PCT = 0.60
DROP6_MIN_PCT = -0.30
ACCELERATION_MIN_RATIO = 0.7
VOLUME_EXPANSION_MIN = 1.8
_VOL_MAX_EXTRAPOLATION = 3.0
_MIN_ELAPSED_SEC = 20.0

BREAKDOWN_BUFFER_PCT = 0.05
ANTI_CHASE_MAX_PCT = 1.00

MACRO_1H_MAX_PCT = 3.0
MACRO_4H_MAX_PCT = 4.0

DEPTH_BAND_PCT = 0.01
MIN_SIDE_DEPTH_USD = 2000.0
MAX_BID_DEPTH_USD = 150000.0
FRAGILITY_RATIO_MIN = 1.40

MAX_SPREAD_PCT = 0.20

# ---- Panic path ----
DEEP_MOVER_THRESHOLD = -8.0        # pct_15m below this => panic path
PANIC_DROP_MIN_PCT = 8.0           # drop from peak to qualify
PANIC_FRESH_HOURS = 1.0            # was 2.0 — tighter
PANIC_DROP3_MIN = 0.30             # very low bar — must still be moving
PANIC_VOL_MIN = 1.5
PANIC_SIDE_DEPTH_MIN = 1000.0
PANIC_WHALE_BID_MAX = 500000.0

# ---- Ratchet ----
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
# NORMAL PATH — 10 checks
# =========================================================================
def evaluate_momentum(candles, pct_15m, now_ms=None):
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

    try:
        lows = [float(c[3]) for c in candles[-11:-1]]
        if lows:
            result["low_10m"] = min(lows)
    except (IndexError, TypeError, ValueError):
        pass

    result["is_valid"] = True
    result["reason"] = "OK"
    return result


def evaluate_position(live_close, low_10m):
    result = {"is_valid": False, "reason": "INVALID", "chase_pct": 0.0}
    if live_close <= 0 or low_10m <= 0:
        return result
    if live_close >= low_10m * (1.0 - BREAKDOWN_BUFFER_PCT / 100.0):
        result["reason"] = "NO_BREAKDOWN"
        return result
    if live_close < low_10m * (1.0 - ANTI_CHASE_MAX_PCT / 100.0):
        result["reason"] = "CHASE"
        result["chase_pct"] = (low_10m - live_close) / low_10m * 100.0
        return result
    result["chase_pct"] = (low_10m - live_close) / low_10m * 100.0
    result["is_valid"] = True
    result["reason"] = "OK"
    return result


def evaluate_macro(hourly_candles, current_price):
    result = {
        "is_aligned": False, "reason": "INVALID",
        "low_1h": 0.0, "low_4h": 0.0,
        "pct_above_1h": 0.0, "pct_above_4h": 0.0, "which": "",
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
# PANIC PATH — 6 checks
# =========================================================================
def evaluate_panic_context(hourly_candles, current_price, now_ms=None):
    result = {
        "is_panic": False, "is_fresh": False,
        "drop_pct": 0.0, "peak": 0.0, "hours_since_peak": 999.0,
    }
    if not hourly_candles or len(hourly_candles) < 3 or current_price <= 0:
        return result
    try:
        last3 = hourly_candles[-3:]
        peaks = [(float(c[2]), int(c[0])) for c in last3]
        peak, peak_ts_ms = max(peaks, key=lambda x: x[0])
    except (IndexError, TypeError, ValueError):
        return result
    if peak <= 0 or peak_ts_ms <= 0:
        return result
    drop_pct = (peak - current_price) / peak * 100.0
    result["drop_pct"] = drop_pct
    result["peak"] = peak
    if drop_pct < PANIC_DROP_MIN_PCT:
        return result
    result["is_panic"] = True
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    hours_since_peak = (now_ms - peak_ts_ms) / 3600000.0
    result["hours_since_peak"] = hours_since_peak
    if hours_since_peak <= PANIC_FRESH_HOURS:
        result["is_fresh"] = True
    return result


def evaluate_momentum_panic(candles, pct_15m, now_ms=None):
    """
    Panic-mode momentum. Deliberately minimal:
      - Must be dropping right now
      - Must be making fresh 1m low (cascade still active)
      - drop3 >= 0.30% (still falling)
      - vol_ratio >= 1.5x (still expanding)
    """
    result = {
        "is_valid": False, "reason": "INVALID",
        "pct_15m": pct_15m,
        "drop_3m": 0.0, "drop_6m": 0.0, "vol_ratio": 0.0,
        "live_close": 0.0, "prev_close": 0.0,
    }
    if not candles or len(candles) < 16:
        return result
    candles = candles[-16:]

    try:
        live_close = float(candles[-1][4])
        prev_close = float(candles[-2][4])
        candle_ts = int(candles[-1][0])
        live_vol = float(candles[-1][5])
    except (IndexError, TypeError, ValueError):
        return result
    result["live_close"] = live_close
    result["prev_close"] = prev_close
    if live_close <= 0 or prev_close <= 0:
        return result

    if pct_15m >= 0:
        result["reason"] = "NOT_DROPPING"
        return result

    if live_close >= prev_close:
        result["reason"] = "NO_FRESH_LOW"
        return result

    try:
        close_9m_ago = float(candles[-10][4])
        close_3m_ago = float(candles[-4][4])
    except (IndexError, TypeError, ValueError):
        return result

    drop_6m = (close_9m_ago - close_3m_ago) / close_9m_ago * 100.0
    drop_3m = (close_3m_ago - live_close) / close_3m_ago * 100.0
    result["drop_6m"] = drop_6m
    result["drop_3m"] = drop_3m

    if drop_3m < PANIC_DROP3_MIN:
        result["reason"] = "ACCEL_WEAK"
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

    if vol_ratio < PANIC_VOL_MIN:
        result["reason"] = "VOLUME"
        return result

    result["is_valid"] = True
    result["reason"] = "OK"
    return result


# =========================================================================
# BOOK
# =========================================================================
def evaluate_book(bids, asks, mid_price, panic_mode=False,
                  band_pct=DEPTH_BAND_PCT):
    result = {"is_valid": False, "reason": "INVALID",
              "depth_ratio": 0.0, "d_bid": 0.0, "d_ask": 0.0,
              "panic_override": panic_mode}
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

    if panic_mode:
        if d_bid < PANIC_SIDE_DEPTH_MIN:
            result["reason"] = "THIN_BID"
            return result
        if d_bid > PANIC_WHALE_BID_MAX:
            result["reason"] = "WHALE_BID"
            return result
        result["is_valid"] = True
        result["reason"] = "OK"
        return result

    if d_bid < MIN_SIDE_DEPTH_USD:
        result["reason"] = "THIN_BID"
        return result
    if d_bid > MAX_BID_DEPTH_USD:
        result["reason"] = "WHALE_BID"
        return result
    if ratio < FRAGILITY_RATIO_MIN:
        result["reason"] = "LOW_RATIO"
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


def evaluate_ratchet(entry_price, current_price, breakdown_level,
                     peak_net, peak_gross, elapsed_seconds):
    result = {
        "should_exit": False, "exit_reason": "HOLD",
        "net_pnl": 0.0, "gross_pnl": 0.0,
        "updated_peak_net": peak_net, "updated_peak_gross": peak_gross,
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
