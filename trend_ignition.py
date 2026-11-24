"""Transparent Bitget trend-ignition analysis; research only, never an order signal."""
from datetime import datetime, timezone


def _n(value):
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _closed(candles, now_ms=None):
    now_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = []
    for row in candles or []:
        try:
            ts = int(row[0])
            if ts + 60_000 <= now_ms and len(row) >= 7:
                rows.append({
                    "ts": ts, "o": _n(row[1]), "h": _n(row[2]),
                    "l": _n(row[3]), "c": _n(row[4]), "v": _n(row[5]),
                    "q": _n(row[6]),
                })
        except (TypeError, ValueError, IndexError):
            continue
    by_ts = {row["ts"]: row for row in rows}
    return [by_ts[key] for key in sorted(by_ts)]


def _oi_series(payload):
    data = (payload or {}).get("data", {}) or {}
    values = data.get("list", []) if isinstance(data, dict) else []
    rows = []
    for item in values or []:
        try:
            ts = int(item.get("timestamp", item.get("ts", 0)))
            oi_value = _n(item.get("openInterestValue"))
            oi_base = _n(item.get("openInterest"))
            value = oi_value if oi_value > 0 else oi_base
            if ts > 0 and value > 0:
                rows.append((ts, value, "USDT_VALUE" if oi_value > 0 else "BASE_COIN"))
        except (TypeError, ValueError, AttributeError):
            continue
    return sorted({row[0]: row for row in rows}.values())


def _oi_change(series, minutes):
    if len(series) < 2:
        return None
    latest_ts, latest_value, unit = series[-1]
    target = latest_ts - minutes * 60_000
    earlier = min(series, key=lambda row: abs(row[0] - target))
    if earlier[0] >= latest_ts or abs(earlier[0] - target) > max(10, minutes * 60_000 * 0.35):
        return None
    if earlier[2] != unit or earlier[1] <= 0:
        return None
    return round((latest_value / earlier[1] - 1) * 100, 4)



def _fill_rows(payload):
    data = (payload or {}).get("data", [])
    if isinstance(data, dict):
        data = data.get("list", [])
    rows = []
    for item in data or []:
        try:
            ts = int(item.get("ts", item.get("cTime", item.get("timestamp", 0))))
            if ts and ts < 10_000_000_000:
                ts *= 1000
            side = str(item.get("side", "")).lower()
            size = _n(item.get("size", item.get("qty", item.get("baseVolume", 0))))
            if ts > 0 and side in ("buy", "sell") and size > 0:
                rows.append((ts, side, size))
        except (TypeError, ValueError, AttributeError):
            continue
    return sorted(rows)


def _taker_windows(payload):
    rows = _fill_rows(payload)
    if not rows:
        return {str(m): {"status": "NO_RECENT_FILLS", "sample_count": 0} for m in (5, 10, 15)}
    latest = rows[-1][0]
    output = {}
    for minutes in (5, 10, 15):
        cutoff = latest - minutes * 60_000
        sample = [x for x in rows if cutoff <= x[0] <= latest]
        covered = (latest - rows[0][0]) / 60_000
        buy = sum(x[2] for x in sample if x[1] == "buy")
        sell = sum(x[2] for x in sample if x[1] == "sell")
        total = buy + sell
        complete = covered >= minutes and len(sample) >= 2 and total > 0
        output[str(minutes)] = {
            "status": "OK" if complete else "INSUFFICIENT_TRADE_HISTORY",
            "buy_volume": round(buy, 8), "sell_volume": round(sell, 8),
            "imbalance": round((buy - sell) / total, 6) if total else None,
            "buy_share_pct": round(buy / total * 100, 3) if total else None,
            "sample_count": len(sample), "available_history_minutes": round(covered, 3),
        }
    return output


def _turnover_windows(rows):
    output = {}
    for minutes in (1, 5, 10, 15):
        if len(rows) < minutes * 2:
            output[str(minutes)] = {"status": "INSUFFICIENT_CANDLES"}
            continue
        recent = sum(x["q"] for x in rows[-minutes:])
        prior = sum(x["q"] for x in rows[-2 * minutes:-minutes])
        output[str(minutes)] = {
            "status": "OK" if prior > 0 else "ZERO_BASELINE",
            "recent_turnover": round(recent, 6),
            "prior_equal_window_turnover": round(prior, 6),
            "acceleration_multiple": round(recent / prior, 4) if prior > 0 else None,
        }
    return output


def _path_efficiency(rows):
    output = {}
    for minutes in (5, 10, 15, 30, 60):
        if len(rows) < minutes:
            output[str(minutes)] = None
            continue
        sample = rows[-minutes:]
        start, end = sample[0]["c"], sample[-1]["c"]
        path = sum(abs(sample[i]["c"] / sample[i-1]["c"] - 1)
                   for i in range(1, len(sample)) if sample[i-1]["c"] > 0)
        net = abs(end / start - 1) if start > 0 else 0
        output[str(minutes)] = {
            "efficiency": round(net / path, 6) if path > 0 else None,
            "absolute_net_move_pct": round(net * 100, 5),
            "path_length_pct": round(path * 100, 5),
        }
    return output


def analyze_trend_ignition(symbol, candles, oi_payload, fills_payload=None, now_ms=None):
    """Score early long/short pressure from closed 1m candles and 5m OI history.

    OI is market-wide aggregate, not long-vs-short positioning. Price/OI
    combinations are described as positioning context, never certainty.
    """
    rows = _closed(candles, now_ms)
    if len(rows) < 60:
        return {
            "type": "trend_ignition", "symbol": symbol, "status": "INSUFFICIENT_CANDLES",
            "candles_available": len(rows), "directions": {},
        }

    last = rows[-1]
    prior20 = rows[-21:-1]
    prior60 = rows[-60:-1]
    high20 = max(x["h"] for x in prior20)
    low20 = min(x["l"] for x in prior20)
    high60 = max(x["h"] for x in prior60)
    low60 = min(x["l"] for x in prior60)
    close = last["c"]
    price_5m = (close / rows[-6]["c"] - 1) * 100 if rows[-6]["c"] else 0
    price_15m = (close / rows[-16]["c"] - 1) * 100 if rows[-16]["c"] else 0
    price_30m = (close / rows[-31]["c"] - 1) * 100 if rows[-31]["c"] else 0
    price_60m = (close / rows[-60]["c"] - 1) * 100 if rows[-60]["c"] else 0

    recent_turnover = sum(x["q"] for x in rows[-5:]) / 5
    baseline_turnover = sum(x["q"] for x in rows[-25:-5]) / 20
    volume_multiple = recent_turnover / baseline_turnover if baseline_turnover > 0 else None

    oi = _oi_series(oi_payload)
    taker_windows = _taker_windows(fills_payload)
    turnover_windows = _turnover_windows(rows)
    efficiency_windows = _path_efficiency(rows)
    oi_changes = {m: _oi_change(oi, m) for m in (5, 15, 30, 60)}
    oi_unit = oi[-1][2] if oi else None

    windows = {}
    for minutes in (5, 10, 15, 20, 30, 60):
        sample = rows[-minutes:]
        green = sum(x["c"] > x["o"] for x in sample)
        red = sum(x["c"] < x["o"] for x in sample)
        doji = minutes - green - red
        windows[str(minutes)] = {
            "green": green, "red": red, "doji": doji,
            "green_pct": round(green / minutes * 100, 1),
            "red_pct": round(red / minutes * 100, 1),
            "net_move_pct": round((sample[-1]["c"] / sample[0]["o"] - 1) * 100, 4) if sample[0]["o"] else None,
        }

    # Candle anatomy and local structure help distinguish persistent pressure
    # from one isolated wick or one outsized candle.
    recent = rows[-10:]
    body_ratios = []
    for x in recent:
        span = x["h"] - x["l"]
        body_ratios.append(abs(x["c"] - x["o"]) / span if span > 0 else 0)
    green10 = sum(x["c"] > x["o"] for x in recent)
    red10 = sum(x["c"] < x["o"] for x in recent)
    higher_highs = sum(recent[i]["h"] > recent[i-1]["h"] for i in range(1, len(recent)))
    lower_lows = sum(recent[i]["l"] < recent[i-1]["l"] for i in range(1, len(recent)))
    breakout_up = close > high20
    breakout_down = close < low20
    major_break_up = close > high60
    major_break_down = close < low60

    directions = {}
    for direction in ("LONG", "SHORT"):
        sign = 1 if direction == "LONG" else -1
        p5, p15 = price_5m * sign, price_15m * sign
        oi15 = oi_changes.get(15)
        oi30 = oi_changes.get(30)
        green_pressure = green10 >= 7 if direction == "LONG" else red10 >= 7
        body_pressure = sum(
            x["c"] > x["o"] if direction == "LONG" else x["c"] < x["o"]
            for x in recent
        ) >= 6 and sum(body_ratios) / len(body_ratios) >= 0.45
        breakout = breakout_up if direction == "LONG" else breakout_down
        major_break = major_break_up if direction == "LONG" else major_break_down
        taker_key = taker_windows.get("5", {})
        taker_imbalance = taker_key.get("imbalance")
        taker_confirm = taker_key.get("status") == "OK" and taker_imbalance is not None and (taker_imbalance > 0 if direction == "LONG" else taker_imbalance < 0)
        oi_build = oi15 is not None and oi15 >= 0.25
        oi_build_30 = oi30 is not None and oi30 >= 0.5
        volume_surge = volume_multiple is not None and volume_multiple >= 1.5
        price_accel = p5 > 0.10 and p15 > 0.15
        structure = higher_highs >= 5 if direction == "LONG" else lower_lows >= 5
        checks = {
            "price_acceleration_5m_15m": price_accel,
            "open_interest_build_15m": oi_build,
            "taker_imbalance_5m_confirmed": taker_confirm,
            "volume_surge_5m_vs_prior20m": volume_surge,
            "directional_candle_pressure": green_pressure and body_pressure,
            "20m_range_breakout": breakout,
            "60m_range_breakout": major_break,
            "higher_high_lower_low_structure": structure,
        }
        score = sum(checks.values())
        if oi15 is None:
            positioning = "OI_HISTORY_UNAVAILABLE"
        elif (price_15m > 0 and oi15 > 0) or (price_15m < 0 and oi15 > 0):
            positioning = "NEW_POSITION_BUILDING_AGGREGATE"
        elif price_15m * oi15 < 0:
            positioning = "POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING"
        else:
            positioning = "NO_CLEAR_OI_CONFIRMATION"
        directions[direction] = {
            "score": score, "score_out_of": len(checks),
            "stage": "IGNITION_CANDIDATE" if score >= 4 else (
                "EARLY_PRESSURE" if score >= 3 else "NO_STRONG_IGNITION"
            ),
            "checks": checks,
            "price_change_pct": {
                "5m": round(price_5m, 4), "15m": round(price_15m, 4),
                "30m": round(price_30m, 4), "60m": round(price_60m, 4),
            },
            "open_interest_change_pct": oi_changes,
            "taker_imbalance_5_10_15m": taker_windows,
            "turnover_acceleration_1_5_10_15m": turnover_windows,
            "price_path_efficiency_5_10_15_30_60m": efficiency_windows,
            "open_interest_unit": oi_unit,
            "positioning_context": positioning,
        }

    return {
        "type": "trend_ignition", "symbol": symbol,
        "analyzed_at_utc": datetime.fromtimestamp((now_ms or int(datetime.now(timezone.utc).timestamp()*1000))/1000, timezone.utc).isoformat(),
        "status": "ANALYZED", "candles_available": len(rows),
        "last_closed_candle_ms": last["ts"],
        "price": close, "volume_multiple_5m_vs_prior20m": round(volume_multiple, 3) if volume_multiple is not None else None,
        "candle_windows": windows,
        "turnover_acceleration_1_5_10_15m": turnover_windows,
        "taker_imbalance_5_10_15m": taker_windows,
        "price_path_efficiency_5_10_15_30_60m": efficiency_windows,
        "candle_structure": {
            "green_last10": green10, "red_last10": red10,
            "mean_body_to_range_last10": round(sum(body_ratios)/len(body_ratios), 3),
            "higher_high_steps_last10": higher_highs, "lower_low_steps_last10": lower_lows,
            "breakout_20m_high": breakout_up, "breakdown_20m_low": breakout_down,
            "breakout_60m_high": major_break_up, "breakdown_60m_low": major_break_down,
        },
        "directions": directions,
        "interpretation_warning": "Aggregate OI does not identify whether longs or shorts opened; combine price, candles, volume and OI as evidence, not certainty. Research only; no orders.",
    }
