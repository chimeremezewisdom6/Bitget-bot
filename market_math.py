"""
market_math.py
==============
Pure mathematical engine for the Coiled Spring Ignition strategy.

Zero network I/O. Standard library only. Deterministic and testable.
Sub-millisecond per call on any input in the 30-candle / 20-level regime.

Candle format (normalized 6-element):
    [timestamp, open, high, low, close, base_volume]
       [0]     [1]    [2]   [3]    [4]     [5]
"""

FEE_ROUND_TRIP_PCT = 0.22
BOX_RANGE_MAX_PCT = 1.25
VOLUME_EXPANSION_MIN = 3.0
DISPLACEMENT_MIN_PCT = 0.10          # 0.10% beyond the box boundary
ANTI_CHASE_MAX_PCT = 0.60            # 0.60% max distance from boundary
DEPTH_FRAGILITY_MIN = 1.50
DEPTH_BAND_PCT = 0.01                # 1.0% band around mid
FAKEOUT_WINDOW_SEC = 40.0
BREAKEVEN_TRIGGER_PCT = 0.50
RATCHET_TRIGGER_PCT = 1.20
RATCHET_KEEP_RATIO = 0.60
STAGNATION_WINDOW_SEC = 40.0
STAGNATION_PEAK_FLOOR = 0.30


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 1. COMPRESSION BOX
# ---------------------------------------------------------------------------
def calculate_compression_box(candles):
    """
    candles: list of 30 closed 1-minute candles [ts, o, h, l, c, v]

    Returns:
        box_high        : float
        box_low         : float
        box_range_pct   : float
        base_volume     : float
        is_compressed   : bool
    """
    invalid = {
        "box_high": 0.0,
        "box_low": 0.0,
        "box_range_pct": 999.0,
        "base_volume": 0.0,
        "is_compressed": False,
    }
    if not candles or len(candles) < 2:
        return invalid

    highs = []
    lows = []
    vols = []
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


# ---------------------------------------------------------------------------
# 2. IGNITION TRIGGER
# ---------------------------------------------------------------------------
def evaluate_ignition_trigger(live_candle, box_high, box_low, base_volume):
    """
    live_candle: [ts, o, h, l, c, v]

    Returns:
        is_ignition : bool
        direction   : "LONG" | "SHORT" | None
        vol_ratio   : float
        chase_pct   : float
    """
    result = {
        "is_ignition": False,
        "direction": None,
        "vol_ratio": 0.0,
        "chase_pct": 0.0,
    }
    if not live_candle or base_volume <= 0 or box_high <= 0 or box_low <= 0:
        return result

    try:
        live_high = float(live_candle[2])
        live_low = float(live_candle[3])
        live_close = float(live_candle[4])
        live_vol = float(live_candle[5])
    except (IndexError, TypeError, ValueError):
        return result

    if live_close <= 0:
        return result

    vol_ratio = live_vol / base_volume
    result["vol_ratio"] = vol_ratio
    if vol_ratio < VOLUME_EXPANSION_MIN:
        return result

    # LONG: displacement above box_high by >= 0.10%
    long_disp = box_high * (1.0 + DISPLACEMENT_MIN_PCT / 100.0)
    if live_high > long_disp:
        chase = (live_close - box_high) / box_high * 100.0
        result["chase_pct"] = chase
        if chase <= ANTI_CHASE_MAX_PCT:
            result["is_ignition"] = True
            result["direction"] = "LONG"
        return result

    # SHORT: displacement below box_low by >= 0.10%
    short_disp = box_low * (1.0 - DISPLACEMENT_MIN_PCT / 100.0)
    if live_low < short_disp:
        chase = (box_low - live_close) / box_low * 100.0
        result["chase_pct"] = chase
        if chase <= ANTI_CHASE_MAX_PCT:
            result["is_ignition"] = True
            result["direction"] = "SHORT"
        return result

    return result


# ---------------------------------------------------------------------------
# 3. BOOK FRAGILITY
# ---------------------------------------------------------------------------
def evaluate_book_fragility(bids, asks, mid_price, direction, band_pct=DEPTH_BAND_PCT):
    """
    bids, asks: list of [price, qty] (strings or floats)
    mid_price : float
    direction : "LONG" | "SHORT"

    Returns:
        is_fragile  : bool
        depth_ratio : float  (relevant ratio for the direction)
        d_bid       : float  (USD depth within band on the bid side)
        d_ask       : float  (USD depth within band on the ask side)
    """
    result = {"is_fragile": False, "depth_ratio": 0.0, "d_bid": 0.0, "d_ask": 0.0}
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
        if d_ask > 0:
            ratio = d_bid / d_ask
        elif d_bid > 0:
            ratio = 999.0
        else:
            ratio = 0.0
        result["depth_ratio"] = ratio
        result["is_fragile"] = ratio >= DEPTH_FRAGILITY_MIN
    elif direction == "SHORT":
        if d_bid > 0:
            ratio = d_ask / d_bid
        elif d_ask > 0:
            ratio = 999.0
        else:
            ratio = 0.0
        result["depth_ratio"] = ratio
        result["is_fragile"] = ratio >= DEPTH_FRAGILITY_MIN

    return result


# ---------------------------------------------------------------------------
# 4. ORDER SIZING
# ---------------------------------------------------------------------------
def calculate_order_qty(balance, price, leverage, volume_place, min_order_volume,
                        min_notional=5.0):
    """
    Computes the market-order quantity string that:
        - uses 90% of available margin at the given leverage,
        - respects the exchange $5.00 minimum notional,
        - matches the contract's volumePlace precision,
        - respects the contract's minOrderVolume.

    Returns:
        qty_str : str  (formatted to volumePlace decimals) or None
    """
    if balance <= 0 or price <= 0 or leverage <= 0:
        return None

    notional = balance * 0.90 * leverage
    if notional < min_notional:
        return None

    vp = int(volume_place)
    raw_qty = notional / price
    qty = round(raw_qty, vp)

    if qty <= 0:
        return None
    if min_order_volume > 0 and qty < min_order_volume:
        return None

    final_notional = qty * price
    if final_notional < min_notional:
        return None

    return f"{qty:.{vp}f}"


# ---------------------------------------------------------------------------
# 5. RATCHET / EXIT ENGINE
# ---------------------------------------------------------------------------
def evaluate_ratchet(entry_price, current_price, direction, peak_net,
                     elapsed_seconds, box_high, box_low):
    """
    The 4-rule asymmetric risk ladder.

    Priority: FAKEOUT > RATCHET > BREAKEVEN > STAGNATION.

    Returns:
        should_exit      : bool
        exit_reason      : str  (HOLD | FAKEOUT_SCRATCH | BREAKEVEN_SHIELD
                                 | RATCHET_BANK | STAGNATION_CUT)
        net_pnl          : float
        gross_pnl        : float
        updated_peak_net : float
    """
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

    # Rule 1 — Fakeout shield (first 40 s only)
    if elapsed_seconds <= FAKEOUT_WINDOW_SEC:
        if direction == "LONG" and current_price <= box_high:
            result["should_exit"] = True
            result["exit_reason"] = "FAKEOUT_SCRATCH"
            return result
        if direction == "SHORT" and current_price >= box_low:
            result["should_exit"] = True
            result["exit_reason"] = "FAKEOUT_SCRATCH"
            return result

    # Rule 3 — 40% dynamic ratchet (checked before breakeven so higher peak wins)
    if peak >= RATCHET_TRIGGER_PCT:
        floor = peak * RATCHET_KEEP_RATIO
        if net <= floor:
            result["should_exit"] = True
            result["exit_reason"] = "RATCHET_BANK"
            return result

    # Rule 2 — Breakeven shield
    if peak >= BREAKEVEN_TRIGGER_PCT and net <= 0.0:
        result["should_exit"] = True
        result["exit_reason"] = "BREAKEVEN_SHIELD"
        return result

    # Rule 4 — Stagnation cut
    if (elapsed_seconds >= STAGNATION_WINDOW_SEC
            and peak < STAGNATION_PEAK_FLOOR
            and net < 0.0):
        result["should_exit"] = True
        result["exit_reason"] = "STAGNATION_CUT"
        return result

    return result
