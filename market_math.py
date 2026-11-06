"""
market_math.py
==============
Cross-Sectional Relative Weakness & Accelerated Breakdown Engine.
Pure math engine. Zero network I/O. Standard library only.

Candle format (each candle): [ts, open, high, low, close, baseVol]
Callers pass exactly 16 candles; last one is the live/partial candle.

Bump __version__ on every change. bot.py refuses to start on mismatch.
"""

import time

__version__ = "2026.11.09"

# ---- Fees --------------------------------------------------------------
FEE_ROUND_TRIP_PCT = 0.22

# ---- 15-minute relative weakness window (SHORT sweet spot range) ------
PCT_15M_MIN_DROP = -5.5   # most extreme drop we still accept
PCT_15M_MAX_DROP = -1.8   # must be at least this weak

# ---- Sweet spot filters ------------------------------------------------
ACCELERATION_MIN_RATIO = 1.0   # rate_3m / rate_6m must exceed this
VOLUME_EXPANSION_MIN = 2.5     # effective live vol vs avg_15m vol
BREAKDOWN_BUFFER_PCT = 0.10    # must break below low_10m by at least this
ANTI_CHASE_MAX_PCT = 0.60      # must not be further than this below low_10m

# Volume normalization (partial candle handling)
_VOL_MAX_EXTRAPOLATION = 3.0
_MIN_ELAPSED_SEC = 20.0

# ---- Order book fragility (SHORT view) --------------------------------
DEPTH_BAND_PCT = 0.01
MIN_SIDE_DEPTH_USD = 8000.0
FRAGILITY_RATIO_MIN = 1.60

# ---- Spread ------------------------------------------------------------
MAX_SPREAD_PCT = 0.15

# ---- Ratchet / risk ----------------------------------------------------
BREAKEVEN_TRIGGER_PCT = 0.50
RATCHET_TRIGGER_PCT = 1.20
RATCHET_KEEP_RATIO = 0.60
INVALIDATION_BUFFER_PCT = 0.35
STAGNATION_WINDOW_SEC = 180.0
STAGNATION_GROSS_TARGET = 0.25


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# =========================================================================
# SWEET SPOT
# =========================================================================
def evaluate_sweet_spot(candles, pct_15m, now_ms=None):
    """
    SHORT-side sweet spot validator.
    Returns dict with is_valid + reason (RANGE / ACCEL / VOLUME /
    BREAKDOWN / CHASE / EARLY / OK).
    """
    result = {
        "is_valid": False,
        "reason": "INVALID",
        "pct_15m": pct_15m,
        "drop_3m": 0.0,
        "drop_6m": 0.0,
        "vol_ratio": 0.0,
        "low_10m": 0.0,
        "live_close": 0.0,
    }
    if not candles or len(candles) < 16:
        return result
    candles = candles[-16:]  # defensive: exactly the last 16

    try:
        live_close = float(candles[-1][4])
        candle_ts = int(candles[-1][0])
        live_vol = float(candles[-1][5])
    except (IndexError, TypeError, ValueError):
        return result

    result["live_close"] = live_close
    if live_close <= 0:
        return result

    # ---- 1) 15m drop must be inside the sweet spot window -------------
    if not (PCT_15M_MIN_DROP <= pct_15m <= PCT_15M_MAX_DROP):
        result["reason"] = "RANGE"
        return result

    # ---- 2) Acceleration: rate_3m > rate_6m, both drops positive ------
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

    if drop_6m <= 0.0 or drop_3m <= 0.0:
        result["reason"] = "ACCEL"
        return result

    rate_3m = drop_3m / 3.0
    rate_6m = drop_6m / 6.0
    if rate_3m <= rate_6m * ACCELERATION_MIN_RATIO:
        result["reason"] = "ACCEL"
        return result

    # ---- 3) Volume expansion vs 15m average ---------------------------
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
    effective_vol = live_vol * multiplier
    vol_ratio = effective_vol / avg_vol_15m
    result["vol_ratio"] = vol_ratio

    if vol_ratio < VOLUME_EXPANSION_MIN:
        result["reason"] = "VOLUME"
        return result

    # ---- 4) Breakdown of the 10-minute low ----------------------------
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

    # Must be at least BREAKDOWN_BUFFER_PCT below low_10m
    if live_close >= low_10m * (1.0 - BREAKDOWN_BUFFER_PCT / 100.0):
        result["reason"] = "BREAKDOWN"
        return result

    # Anti-chase: must not be more than ANTI_CHASE_MAX_PCT below low_10m
    if live_close < low_10m * (1.0 - ANTI_CHASE_MAX_PCT / 100.0):
        result["reason"] = "CHASE"
        return result

    result["is_valid"] = True
    result["reason"] = "OK"
    return result


# =========================================================================
# ORDER BOOK
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


def evaluate_book_fragility(bids, asks, mid_price,
                            band_pct=DEPTH_BAND_PCT,
                            min_side_depth=MIN_SIDE_DEPTH_USD):
    """
    SHORT-side fragility:
      - require d_bid >= min_side_depth (enough liquidity on our close side)
      - require d_ask / d_bid >= FRAGILITY_RATIO_MIN (ask wall dominates,
        buyers absent -> continuation down expected)
    """
    result = {"is_fragile": False, "depth_ratio": 0.0,
              "d_bid": 0.0, "d_ask": 0.0}
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

    if d_bid < min_side_depth:
        return result

    ratio = (d_ask / d_bid) if d_bid > 0 else 0.0
    result["depth_ratio"] = ratio
    result["is_fragile"] = ratio >= FRAGILITY_RATIO_MIN
    return result


# =========================================================================
# SIZING
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


# =========================================================================
# RATCHET (SHORT)
# =========================================================================
def evaluate_ratchet(entry_price, current_price, breakdown_level,
                     peak_net, peak_gross, elapsed_seconds):
    """
    SHORT ratchet. breakdown_level = the 10m-low that was broken at entry;
    if price climbs back above (1 + INVALIDATION_BUFFER_PCT/100) * that
    level, the breakdown is invalidated and we exit.

    peak_gross tracks gross (pre-fee) high-water — used only by stagnation.
    """
    result = {
        "should_exit": False,
        "exit_reason": "HOLD",
        "net_pnl": 0.0,
        "gross_pnl": 0.0,
        "updated_peak_net": peak_net,
        "updated_peak_gross": peak_gross,
    }
    if entry_price <= 0 or current_price <= 0:
        return result

    # SHORT: profit when current < entry
    gross = (entry_price - current_price) / entry_price * 100.0
    net = gross - FEE_ROUND_TRIP_PCT
    new_peak_net = peak_net if peak_net > net else net
    new_peak_gross = peak_gross if peak_gross > gross else gross

    result["gross_pnl"] = gross
    result["net_pnl"] = net
    result["updated_peak_net"] = new_peak_net
    result["updated_peak_gross"] = new_peak_gross

    # Invalidation: price climbed back above breakdown level by +0.35%
    if breakdown_level > 0:
        if current_price > breakdown_level * (1.0 + INVALIDATION_BUFFER_PCT / 100.0):
            result["should_exit"] = True
            result["exit_reason"] = "INVALIDATION_STOP"
            return result

    # Breakeven shield
    if new_peak_net >= BREAKEVEN_TRIGGER_PCT and net <= 0.0:
        result["should_exit"] = True
        result["exit_reason"] = "BREAKEVEN_SHIELD"
        return result

    # Ratchet
    if new_peak_net >= RATCHET_TRIGGER_PCT:
        floor = RATCHET_KEEP_RATIO * new_peak_net
        if net <= floor:
            result["should_exit"] = True
            result["exit_reason"] = "RATCHET_BANK"
            return result

    # Stagnation cut
    if (elapsed_seconds >= STAGNATION_WINDOW_SEC
            and new_peak_gross < STAGNATION_GROSS_TARGET
            and gross < 0.0):
        result["should_exit"] = True
        result["exit_reason"] = "STAGNATION_CUT"
        return result

    return result
