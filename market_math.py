"""
market_math.py
==============
Pure mathematical engine for the Coiled Spring Ignition strategy.
Zero network I/O. Standard library only.

Candle format:
    [timestamp, open, high, low, close, base_volume]
       [0]     [1]    [2]   [3]    [4]     [5]

Bump __version__ on every change. bot.py refuses to start on mismatch.
"""

import time

__version__ = "2026.11.07"

FEE_ROUND_TRIP_PCT = 0.22
BOX_RANGE_MAX_PCT = 0.55
VOLUME_EXPANSION_MIN = 3.0
DISPLACEMENT_MIN_PCT = 0.10
ANTI_CHASE_MAX_PCT = 0.60
DEPTH_FRAGILITY_MIN = 1.15        # was 1.35 — relax the final gate
DEPTH_BAND_PCT = 0.01
MIN_SIDE_DEPTH_USD = 100.0
MAX_SPREAD_PCT = 0.15
FAKEOUT_WINDOW_SEC = 40.0
BREAKEVEN_TRIGGER_PCT = 0.50
RATCHET_TRIGGER_PCT = 1.20
RATCHET_KEEP_RATIO = 0.60
STAGNATION_WINDOW_SEC = 40.0
STAGNATION_PEAK_FLOOR = 0.30

# Volume normalization tuning
_MIN_ELAPSED_SEC = 10.0           # need this much candle history to evaluate
_MAX_EXTRAPOLATION = 4.0          # cap partial->full projection at 4x


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def calculate_compression_box(candles):
    invalid = {
        "box_high": 0.0,
        "box_low": 0.0,
        "box_range_pct": 999.0,
        "base_volume": 0.0,
        "is_compressed": False,
    }
    if not candles or len(candles) < 2:
        return invalid

    highs, lows, vols = [], [], []
    for c in candles:
        try:
            highs.append(float(c[2]))
            lows.append(float(c[3]))
            vols.append(float(c[5]))
        except (IndexError, TypeError, ValueError):
            return invalid

    if not highs or not lows:
        return invalid

    box_high = max(highs)
    box_low = min(lows)
    if box_low <= 0:
        return invalid

    box_range_pct = (box_high - box_low) / box_low * 100.0
    base_volume = sum(vols) / len(vols)

    return {
        "box_high": box_high,
        "box_low": box_low,
        "box_range_pct": box_range_pct,
        "base_volume": base_volume,
        "is_compressed": (box_range_pct <= BOX_RANGE_MAX_PCT) and (base_volume > 0),
    }


def evaluate_ignition_trigger(live_candle, box_high, box_low, base_volume,
                              now_ms=None):
    """
    Volume is normalized against elapsed candle time so partial candles are
    not unfairly rejected. Result now carries a 'reason' field so the caller
    can build a funnel counter.
    """
    result = {
        "is_ignition": False,
        "direction": None,
        "vol_ratio": 0.0,
        "chase_pct": 0.0,
        "reason": "INVALID",
    }
    if not live_candle or base_volume <= 0 or box_high <= 0 or box_low <= 0:
        return result

    try:
        live_high = float(live_candle[2])
        live_low = float(live_candle[3])
        live_close = float(live_candle[4])
        live_vol = float(live_candle[5])
        candle_open_ms = int(live_candle[0])
    except (IndexError, TypeError, ValueError):
        return result

    if live_close <= 0:
        return result

    if now_ms is None:
        now_ms = int(time.time() * 1000)
    elapsed_s = max(1.0, (now_ms - candle_open_ms) / 1000.0)
    if elapsed_s < _MIN_ELAPSED_SEC:
        result["reason"] = "TOO_EARLY"
        return result

    # 1.0x at full candle (60s), up to _MAX_EXTRAPOLATION near the open.
    multiplier = min(60.0 / elapsed_s, _MAX_EXTRAPOLATION)
    vol_ratio = (live_vol / base_volume) * multiplier
    result["vol_ratio"] = vol_ratio

    if vol_ratio < VOLUME_EXPANSION_MIN:
        result["reason"] = "VOLUME"
        return result

    long_disp = box_high * (1.0 + DISPLACEMENT_MIN_PCT / 100.0)
    if live_high > long_disp:
        chase = (live_close - box_high) / box_high * 100.0
        result["chase_pct"] = chase
        if chase <= ANTI_CHASE_MAX_PCT:
            result["is_ignition"] = True
            result["direction"] = "LONG"
            result["reason"] = "OK"
        else:
            result["reason"] = "CHASE"
        return result

    short_disp = box_low * (1.0 - DISPLACEMENT_MIN_PCT / 100.0)
    if live_low < short_disp:
        chase = (box_low - live_close) / box_low * 100.0
        result["chase_pct"] = chase
        if chase <= ANTI_CHASE_MAX_PCT:
            result["is_ignition"] = True
            result["direction"] = "SHORT"
            result["reason"] = "OK"
        else:
            result["reason"] = "CHASE"
        return result

    result["reason"] = "DISPLACEMENT"
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


def evaluate_book_fragility(bids, asks, mid_price, direction,
                            band_pct=DEPTH_BAND_PCT,
                            min_side_depth=MIN_SIDE_DEPTH_USD):
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

    if direction == "LONG":
        if d_ask < min_side_depth:
            return result
        ratio = (d_bid / d_ask) if d_ask > 0 else 999.0
        result["depth_ratio"] = ratio
        result["is_fragile"] = ratio >= DEPTH_FRAGILITY_MIN
    elif direction == "SHORT":
        if d_bid < min_side_depth:
            return result
        ratio = (d_ask / d_bid) if d_bid > 0 else 999.0
        result["depth_ratio"] = ratio
        result["is_fragile"] = ratio >= DEPTH_FRAGILITY_MIN

    return result


def calculate_order_qty(balance, price, leverage, volume_place, min_order_volume,
                        min_notional=5.0):
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


def evaluate_ratchet(entry_price, current_price, direction, peak_net,
                     elapsed_seconds, box_high, box_low,
                     skip_fakeout=False):
    result = {
        "should_exit": False,
        "exit_reason": "HOLD",
        "net_pnl": 0.0,
        "gross_pnl": 0.0,
        "updated_peak_net": peak_net,
    }
    if entry_price <= 0 or current_price <= 0 or box_high <= 0 or box_low <= 0:
        return result

    if direction == "LONG":
        gross = (current_price - entry_price) / entry_price * 100.0
    else:
        gross = (entry_price - current_price) / entry_price * 100.0

    net = gross - FEE_ROUND_TRIP_PCT
    peak = peak_net if peak_net > net else net

    result["gross_pnl"] = gross
    result["net_pnl"] = net
    result["updated_peak_net"] = peak

    if not skip_fakeout and elapsed_seconds <= FAKEOUT_WINDOW_SEC:
        if direction == "LONG" and current_price <= box_high:
            result["should_exit"] = True
            result["exit_reason"] = "FAKEOUT_SCRATCH"
            return result
        if direction == "SHORT" and current_price >= box_low:
            result["should_exit"] = True
            result["exit_reason"] = "FAKEOUT_SCRATCH"
            return result

    if peak >= RATCHET_TRIGGER_PCT:
        floor = peak * RATCHET_KEEP_RATIO
        if net <= floor:
            result["should_exit"] = True
            result["exit_reason"] = "RATCHET_BANK"
            return result

    if peak >= BREAKEVEN_TRIGGER_PCT and net <= 0.0:
        result["should_exit"] = True
        result["exit_reason"] = "BREAKEVEN_SHIELD"
        return result

    if (elapsed_seconds >= STAGNATION_WINDOW_SEC
            and peak < STAGNATION_PEAK_FLOOR
            and net < 0.0):
        result["should_exit"] = True
        result["exit_reason"] = "STAGNATION_CUT"
        return result

    return result
