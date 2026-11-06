"""
market_math.py
==============
Pure computational engine for the Coiled Spring Breakout strategy.

ZERO network I/O. ZERO external dependencies. Standard library only.
All functions are deterministic, allocation-light, and sub-millisecond.

Data format convention (Bitget V2 candle shape):
    candle = [ts, open, high, low, close, baseVol, quoteVol]
    index    0    1     2     3     4        5          6
"""

FEE_ROUND_TRIP_PCT = 0.22


def _f(x, default=0.0):
    """Safe float cast that never raises."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 1. BOX COMPRESSION — "Find the Sleeping Coin"
# ---------------------------------------------------------------------------
def calculate_box_compression(candles, box_range_max=1.25):
    """
    Given a list of closed 1-minute candles, compute the compression box.

    Returns a dict:
        box_high       : float
        box_low        : float
        box_range_pct  : float  ( (H - L) / L * 100 )
        base_volume    : float  (mean of per-candle base volume )
        is_compressed  : bool
    """
    empty = {
        "box_high": 0.0,
        "box_low": 0.0,
        "box_range_pct": 999.0,
        "base_volume": 0.0,
        "is_compressed": False,
    }
    if not candles or len(candles) < 2:
        return empty

    highs = [_f(c[2]) for c in candles]
    lows = [_f(c[3]) for c in candles]
    vols = [_f(c[5]) for c in candles]

    box_high = max(highs)
    box_low = min(lows)
    if box_low <= 0:
        return empty

    box_range_pct = (box_high - box_low) / box_low * 100.0
    base_volume = sum(vols) / len(vols) if vols else 0.0

    return {
        "box_high": box_high,
        "box_low": box_low,
        "box_range_pct": box_range_pct,
        "base_volume": base_volume,
        "is_compressed": box_range_pct <= box_range_max,
    }


# ---------------------------------------------------------------------------
# 2. IGNITE TRIGGER — "Minute 1 of the Move"
# ---------------------------------------------------------------------------
def check_ignite_trigger(candles, box_high, box_low, base_volume,
                         volume_mult=3.0, anti_chase_pct=0.60):
    """
    Detect a breakout of the compression box on the live (last) candle.

    Returns:
        direction         : "long" | "short" | None
        is_valid          : bool
        breakout_price    : float  (box edge that was broken)
        volume_ratio      : float  (live_vol / base_vol)
        chase_distance_pct: float  (how far price has already extended)
    """
    result = {
        "direction": None,
        "is_valid": False,
        "breakout_price": 0.0,
        "volume_ratio": 0.0,
        "chase_distance_pct": 0.0,
    }
    if not candles or box_high <= 0 or box_low <= 0 or base_volume <= 0:
        return result

    live = candles[-1]
    live_high = _f(live[2])
    live_low = _f(live[3])
    live_close = _f(live[4])
    live_vol = _f(live[5])
    if live_close <= 0:
        return result

    volume_ratio = live_vol / base_volume
    result["volume_ratio"] = volume_ratio
    if volume_ratio < volume_mult:
        return result

    if live_high > box_high:
        chase = (live_close - box_high) / box_high * 100.0
        result["direction"] = "long"
        result["breakout_price"] = box_high
        result["chase_distance_pct"] = chase
        result["is_valid"] = chase <= anti_chase_pct
        return result

    if live_low < box_low:
        chase = (box_low - live_close) / box_low * 100.0
        result["direction"] = "short"
        result["breakout_price"] = box_low
        result["chase_distance_pct"] = chase
        result["is_valid"] = chase <= anti_chase_pct
        return result

    return result


# ---------------------------------------------------------------------------
# 3. ORDER BOOK DEPTH IMBALANCE
# ---------------------------------------------------------------------------
def calculate_depth_imbalance(bids, asks, mid_price, band_pct=0.01):
    """
    USD-weighted depth within a band around mid.

    bids, asks : list of [price, qty] (strings or floats)
    mid_price  : float
    band_pct   : float (0.01 == 1.0%)

    Returns:
        bid_usd   : float
        ask_usd   : float
        ratio     : float  (bid_usd / ask_usd; >=1.5 is a LONG green light)
        favorable : bool   ( True when ratio >= 1.5 )
    """
    if mid_price <= 0:
        return {"bid_usd": 0.0, "ask_usd": 0.0, "ratio": 0.0, "favorable": False}

    bid_floor = mid_price * (1.0 - band_pct)
    ask_ceil = mid_price * (1.0 + band_pct)

    bid_usd = 0.0
    ask_usd = 0.0
    for p, q in bids:
        pf = _f(p)
        if pf >= bid_floor:
            bid_usd += pf * _f(q)
    for p, q in asks:
        pf = _f(p)
        if pf <= ask_ceil:
            ask_usd += pf * _f(q)

    ratio = bid_usd / ask_usd if ask_usd > 0 else 999.0
    return {
        "bid_usd": bid_usd,
        "ask_usd": ask_usd,
        "ratio": ratio,
        "favorable": ratio >= 1.5,
    }


# ---------------------------------------------------------------------------
# 4. POSITION SIZING (Micro-capital, $5 min-notional aware)
# ---------------------------------------------------------------------------
def calculate_order_qty(balance, price, leverage, volume_place, min_order_volume,
                        min_notional=5.0, margin_use_ratio=0.90):
    """
    Compute the order quantity in string form, enforcing:
      - margin_use_ratio * balance * leverage >= min_notional
      - qty >= min_order_volume
      - qty rounded to volumePlace decimals
      - post-rounding notional >= min_notional

    Returns:
        qty_str    : str
        qty_float  : float
        notional   : float
        valid      : bool
        reason     : str
    """
    if price <= 0 or balance <= 0:
        return {"qty_str": "0", "qty_float": 0.0, "notional": 0.0,
                "valid": False, "reason": "invalid_inputs"}

    vp = int(volume_place)

    margin = balance * margin_use_ratio
    notional = margin * leverage
    if notional < min_notional:
        return {"qty_str": "0", "qty_float": 0.0, "notional": notional,
                "valid": False, "reason": "notional_below_min"}

    raw_qty = notional / price
    qty_rounded = round(raw_qty, vp)

    if qty_rounded <= 0:
        return {"qty_str": "0", "qty_float": 0.0, "notional": 0.0,
                "valid": False, "reason": "qty_rounds_to_zero"}

    if min_order_volume > 0 and qty_rounded < min_order_volume:
        return {"qty_str": "0", "qty_float": 0.0,
                "notional": qty_rounded * price,
                "valid": False, "reason": "qty_below_min_order_volume"}

    final_notional = qty_rounded * price
    if final_notional < min_notional:
        return {"qty_str": f"{qty_rounded:.{vp}f}",
                "qty_float": qty_rounded,
                "notional": final_notional,
                "valid": False, "reason": "final_notional_below_min"}

    return {
        "qty_str": f"{qty_rounded:.{vp}f}",
        "qty_float": qty_rounded,
        "notional": final_notional,
        "valid": True,
        "reason": "ok",
    }


# ---------------------------------------------------------------------------
# 5. RATCHET STATE MACHINE (4-second pulse decision engine)
# ---------------------------------------------------------------------------
def evaluate_ratchet_state(entry_price, current_price, direction, peak_net,
                           elapsed_seconds, box_high, box_low):
    """
    Evaluate the position against the asymmetric risk ladder.

    Actions returned:
        "HOLD"
        "FAKEOUT_CLOSE"      (price re-entered box within 40s)
        "STAGNATION_CLOSE"   (still negative after 40s, never armed)
        "BREAKEVEN_CLOSE"    (dropped back to net <= 0 after arming at +0.50%)
        "RATCHET_CLOSE"      (pulled back 40% from peak after arming at +1.20%)

    Returns:
        gross_pct        : float
        net_pct          : float  (gross - 0.22 fee drag)
        peak_net         : float  (updated high-water mark of net_pct)
        floor            : float | None
        action           : str
        breakeven_armed  : bool
    """
    if entry_price <= 0 or current_price <= 0:
        return {
            "gross_pct": 0.0,
            "net_pct": 0.0,
            "peak_net": peak_net,
            "floor": None,
            "action": "HOLD",
            "breakeven_armed": False,
        }

    if direction == "long":
        gross_pct = (current_price - entry_price) / entry_price * 100.0
    else:
        gross_pct = (entry_price - current_price) / entry_price * 100.0

    net_pct = gross_pct - FEE_ROUND_TRIP_PCT
    new_peak = max(peak_net, net_pct)

    breakeven_armed = new_peak >= 0.50
    ratchet_armed = new_peak >= 1.20

    floor = None
    action = "HOLD"

    # ---- Fakeout shield (first 40 s) ----
    if elapsed_seconds <= 40.0:
        if direction == "long" and current_price <= box_high:
            action = "FAKEOUT_CLOSE"
        elif direction == "short" and current_price >= box_low:
            action = "FAKEOUT_CLOSE"

    # ---- Ratchet / breakeven ladder ----
    if action == "HOLD":
        if ratchet_armed:
            floor = new_peak * 0.60
            if net_pct <= floor:
                action = "RATCHET_CLOSE"
        elif breakeven_armed:
            floor = 0.0
            if net_pct <= 0.0:
                action = "BREAKEVEN_CLOSE"

    # ---- Stagnation cut (40 s, still negative, never armed) ----
    if action == "HOLD" and not breakeven_armed and not ratchet_armed:
        if elapsed_seconds >= 40.0 and net_pct < 0.0:
            action = "STAGNATION_CLOSE"

    return {
        "gross_pct": gross_pct,
        "net_pct": net_pct,
        "peak_net": new_peak,
        "floor": floor,
        "action": action,
        "breakeven_armed": breakeven_armed,
    }
