"""
market_math.py
==============
PREDICT strategy math — noise-filtered features, duration×magnitude kinds,
feature power scoring, strict crowd-backed acceleration gate, economic
live gate, and per-tier ban/unban system.

v2026.12.26
"""
import math

__version__ = "2026.12.26"

FEE_ROUND_TRIP_PCT = 0.22

# ---- Eligibility ----
PRED_VOLUME_MIN_USD = 1_000_000.0
PRED_MIN_FLUCTUATION_PCT_PER_MIN = 0.05
PRED_LOOKBACK_SEC = 3600
PRED_RECENT_WINDOW_SEC = 600
PRED_PRIOR_WINDOW_SEC = 1800
PRED_MAX_HOLD_SEC = 1800.0

# ---- Book ----
DEPTH_BAND_PCT = 0.01
MIN_SIDE_DEPTH_USD = 1000.0
MAX_BID_DEPTH_USD = 500000.0
MAX_SPREAD_PCT = 0.20
PRED_ENTRY_MIN_DEPTH_RATIO = 1.3
PRED_EXIT_DEPTH_RATIO_MAX = 1.2

# ---- Profile bank ----
PRED_PROFILE_MATCH_TOL = 0.35
PRED_PROFILE_MATCH_MIN_FIELDS = 3
PRED_PROFILE_RESEMBLE_TOL = 0.60
PRED_PROFILE_MAX = 12

# ---- Behaviour ----
WHALE_ORDER_USD = 50_000.0
AGGRESSIVE_TAKER_USD = 20_000.0
QUIET_VOLUME_RATIO = 0.5
PANIC_VOLUME_RATIO = 2.0
STALL_PRICE_PCT = 0.05

# ---- Follow-through ----
FOLLOWTHROUGH_HORIZONS_SEC = (30, 60, 120, 180)
LIVE_NET_TARGET_PCT = 0.28

# ---- Feature signal classification ----
FEATURE_EFFECT_MIN_MOVE_PCT = 0.20
FEATURE_BIG_MOVE_PCT = 0.50
FEATURE_NOISE_SIGNAL_RATIO = 0.25
FEATURE_LEADERBOARD_MIN_SAMPLES = 3
MIN_OBS_FOR_PATTERN = 3

KIND_TIMEOUT_SEC = {
    "FLASH": 60.0, "FLASH_BIG": 90.0,
    "PULSE": 180.0, "PULSE_BIG": 240.0,
    "SUSTAINED": 600.0, "SUSTAINED_BIG": 900.0,
}

# ---- Coin filter (heavy absorber detection) ----
MARKETCAP_VOLUME_MAX_RATIO = 10.0
HEAVY_ABSORBER_MIN_VOL_USD = 100_000_000
HEAVY_ABSORBER_MIN_FLUCT = 0.15
RESPONSIVENESS_MIN = 0.02

# ---- Rate-based entry (per BTC/ETH/ZEC insight) ----
LIVE_ENTRY_MIN_FEATURE_RATE = 75.0
LIVE_ENTRY_MAX_OPPONENT_RATE = 55.0
LIVE_ENTRY_MIN_DELTA = 25.0
LIVE_ENTRY_MIN_EXPECTED_GROSS_PCT = 0.40
WIN_THRESHOLD_NET_PCT = 0.18
RATE_BINS_DELTA = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 100)]
RATE_BINS_OPP = [(0, 30), (30, 50), (50, 70), (70, 100)]
RATE_BINS_FEAT = [(0, 50), (50, 70), (70, 85), (85, 100)]

# ---- Acceleration entry (strict two-layer gate) ----
ACCEL_WINDOW_MIN = 3
ACCEL_MIN_RATIO = 3.0
ACCEL_MIN_FILL_RATIO = 2.0
ACCEL_MIN_PER_MIN_VOL_RATIO = 2.0
ACCEL_MIN_PER_MIN_FILL_RATIO = 1.5
ACCEL_FEATURE_MIN_STEP_GROWTH = 1.15
ACCEL_MIN_FEATURE_FILLS = 5

# ---- Economic live gate ----
LIVE_OBS_WINDOW = 20
LIVE_MIN_WINS_OUT_OF_20 = 15
LIVE_MIN_AVG_NET_PCT = 0.15
LIVE_PEAK_WINDOW_MIN = 3

# ---- Live ban system ----
LIVE_BAN_CONSECUTIVE_LOSSES = 2
UNBAN_CONSECUTIVE_PAPER_WINS = 8
UNBAN_MIN_AVG_NET_PCT = 0.20
LIVE_BAN_INDEFINITE = 9_999_999_999.0

# ---- New feature discovery ----
UNEXPLAINED_MOVE_MIN_PCT = 1.1
UNEXPLAINED_MAX_DURATION_SEC = 120
NEW_FEATURE_PROMOTE_MIN_OCCURRENCES = 5
NEW_FEATURE_PROMOTE_MIN_STREAK = 5
NEW_FEATURE_MAX_DESCRIPTION_WORDS = 200

# ---- Winner window ----
WINNER_MOVE_WINDOW_MIN_PCT = 1.0

# ---- Market cap tiers (volume proxy) ----
MARKET_CAP_TIERS = (
    ("micro",  0,            5_000_000),
    ("small",  5_000_000,    20_000_000),
    ("mid",    20_000_000,   100_000_000),
    ("large",  100_000_000,  1_000_000_000),
    ("mega",   1_000_000_000, 1e18),
)

REASON_CATEGORIES = (
    "no_resistance", "heavy_volume", "light_cap_thin_book",
    "overpowered_opposition", "mixed",
    "absorbed_by_opposition", "no_volume", "heavy_cap_inertia",
    "feature_failed",
)


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _raw(v_net):
    return v_net + FEE_ROUND_TRIP_PCT


def _tag_direction(tag):
    if "buy" in tag:
        return "LONG"
    if "sell" in tag:
        return "SHORT"
    return "LONG"


# =========================================================================
# MARKET CAP / VOLUME TIER
# =========================================================================
def market_cap_tier_from_volume(vol_24h_usd):
    if vol_24h_usd is None or vol_24h_usd <= 0:
        return "unknown"
    for name, lo, hi in MARKET_CAP_TIERS:
        if lo <= vol_24h_usd < hi:
            return name
    return "unknown"


def passes_marketcap_volume_rule(market_cap_usd, volume_24h_usd):
    """Exclude if market cap >= 10x 24h volume, or if market cap is unknown."""
    if not market_cap_usd or market_cap_usd <= 0:
        return False, "no_mcap"
    if not volume_24h_usd or volume_24h_usd <= 0:
        return False, "no_volume"
    ratio = market_cap_usd / volume_24h_usd
    if ratio >= MARKETCAP_VOLUME_MAX_RATIO:
        return False, f"ratio_{ratio:.1f}x"
    return True, f"ratio_{ratio:.1f}x"


def passes_coin_filter(feats):
    """Reject coins that can't deliver momentum to beat fees."""
    vol = feats.get("volume_24h_usd", 0.0)
    if vol < PRED_VOLUME_MIN_USD:
        return False, "low_volume"
    fluct = feats.get("fluct_per_min", 0.0)
    if fluct < PRED_MIN_FLUCTUATION_PCT_PER_MIN:
        return False, "low_fluct"
    if vol > HEAVY_ABSORBER_MIN_VOL_USD and fluct < HEAVY_ABSORBER_MIN_FLUCT:
        return False, "heavy_absorber"
    vol_m = vol / 1_000_000.0
    responsiveness = fluct / (vol_m ** 0.5)
    if responsiveness < RESPONSIVENESS_MIN:
        return False, "low_responsiveness"
    return True, "ok"


# =========================================================================
# FLUCTUATION / DUMP
# =========================================================================
def compute_fluctuation_pct_per_min(price_history, now_ts,
                                    lookback_sec=PRED_LOOKBACK_SEC):
    cutoff = now_ts - lookback_sec
    window = [(t, p) for t, p in price_history if t >= cutoff and p > 0]
    if len(window) < 10:
        return 0.0
    bins = {}
    for t, p in window:
        bins.setdefault(int(t // 60), []).append(p)
    minute_prices = [bins[b][-1] for b in sorted(bins.keys())]
    if len(minute_prices) < 5:
        return 0.0
    changes = []
    for i in range(1, len(minute_prices)):
        prev = minute_prices[i - 1]
        if prev > 0:
            changes.append(abs(minute_prices[i] - prev) / prev * 100.0)
    return sum(changes) / len(changes) if changes else 0.0


def compute_recent_dump(price_history, now_ts, window_sec=PRED_RECENT_WINDOW_SEC):
    out = {"peak_price": 0.0, "low_price": 0.0, "low_ts": 0,
           "current_price": 0.0, "dump_pct": 0.0,
           "dump_rate_pct_per_min": 0.0, "recovery_pct": 0.0}
    cutoff = now_ts - window_sec
    window = [(t, p) for t, p in price_history if t >= cutoff and p > 0]
    if len(window) < 2:
        return out
    peak_price, _ = max(window, key=lambda x: x[1])
    low_price, low_ts = min(window, key=lambda x: x[1])
    current_price = window[-1][1]
    if peak_price <= 0 or low_price <= 0:
        return out
    dump_pct = (peak_price - current_price) / peak_price * 100.0
    duration_min = window_sec / 60.0
    recovery_pct = (current_price - low_price) / low_price * 100.0
    out.update({"peak_price": peak_price, "low_price": low_price,
                "low_ts": low_ts, "current_price": current_price,
                "dump_pct": dump_pct,
                "dump_rate_pct_per_min":
                    dump_pct / duration_min if duration_min > 0 else 0.0,
                "recovery_pct": recovery_pct})
    return out


def compute_prior_move_pct(price_history, now_ts,
                           recent_window_sec=PRED_RECENT_WINDOW_SEC,
                           prior_window_sec=PRED_PRIOR_WINDOW_SEC):
    recent_start = now_ts - recent_window_sec
    prior_start = recent_start - prior_window_sec
    window = [(t, p) for t, p in price_history
              if prior_start <= t < recent_start and p > 0]
    if len(window) < 2:
        return 0.0
    first, last = window[0][1], window[-1][1]
    if first <= 0:
        return 0.0
    return abs(last - first) / first * 100.0


# =========================================================================
# PROFILE FEATURE MATCHING
# =========================================================================
def compute_features_for_predict(price_history, now_ts, high_24h, low_24h,
                                 volume_24h_usd):
    out = {"valid": False, "reason": "NO_DATA",
           "fluct_per_min": 0.0, "recent_abs_pct": 0.0,
           "recent_rate_pct_per_min": 0.0, "prior_move_pct": 0.0,
           "prior_rate_pct_per_min": 0.0, "acceleration": 0.0,
           "distance_from_extreme_pct": 0.0, "direction": None,
           "volume_24h_usd": volume_24h_usd,
           "high_24h": high_24h, "low_24h": low_24h}
    if not price_history or len(price_history) < 10:
        return out
    if volume_24h_usd < PRED_VOLUME_MIN_USD:
        out["reason"] = "LOW_VOLUME"
        return out
    fluct = compute_fluctuation_pct_per_min(price_history, now_ts)
    out["fluct_per_min"] = round(fluct, 4)
    if fluct < PRED_MIN_FLUCTUATION_PCT_PER_MIN:
        out["reason"] = "LOW_FLUCTUATION"
        return out
    recent = compute_recent_dump(price_history, now_ts)
    out["recent_abs_pct"] = round(recent["dump_pct"], 3)
    out["recent_rate_pct_per_min"] = round(recent["dump_rate_pct_per_min"], 3)
    prior = compute_prior_move_pct(price_history, now_ts)
    out["prior_move_pct"] = round(prior, 3)
    if PRED_PRIOR_WINDOW_SEC > 0:
        out["prior_rate_pct_per_min"] = round(
            prior / (PRED_PRIOR_WINDOW_SEC / 60.0), 4)
    if out["prior_rate_pct_per_min"] > 0:
        out["acceleration"] = round(
            out["recent_rate_pct_per_min"] / out["prior_rate_pct_per_min"], 2)
    current = price_history[-1][1]
    if recent["dump_pct"] > 0 and high_24h > 0:
        out["distance_from_extreme_pct"] = round(
            (high_24h - current) / high_24h * 100.0, 2)
    elif low_24h > 0 and current > 0:
        out["distance_from_extreme_pct"] = round(
            (current - low_24h) / low_24h * 100.0, 2)
    cutoff_5m = now_ts - 300
    w5 = [(t, p) for t, p in price_history if t >= cutoff_5m and p > 0]
    if len(w5) >= 2:
        ch = w5[-1][1] - w5[0][1]
        if ch > 0:
            out["direction"] = "LONG"
        elif ch < 0:
            out["direction"] = "SHORT"
    if out["direction"] is None:
        out["reason"] = "NO_DIRECTION"
        return out
    out["valid"] = True
    out["reason"] = "OK"
    return out


def _count_feature_matches(features, profile, tol):
    fields = ("fluct_per_min", "recent_abs_pct", "prior_move_pct",
              "acceleration", "distance_from_extreme_pct")
    matched = 0
    for k in fields:
        fv = features.get(k, 0.0)
        pv = profile.get(k, 0.0)
        if fv < 0.02 and pv < 0.02:
            matched += 1
            continue
        ratio = fv / max(pv, 0.01)
        if 1.0 - tol <= ratio <= 1.0 + tol:
            matched += 1
    return matched


def features_match_profile(features, profile, tol=PRED_PROFILE_MATCH_TOL,
                           min_fields=PRED_PROFILE_MATCH_MIN_FIELDS):
    if not features or not features.get("valid"):
        return False
    if features.get("direction") != profile.get("direction"):
        return False
    return _count_feature_matches(features, profile, tol) >= min_fields


def features_resemble_profile(features, profile, tol=PRED_PROFILE_RESEMBLE_TOL):
    if not features or not features.get("valid"):
        return False
    if features.get("direction") != profile.get("direction"):
        return False
    return _count_feature_matches(features, profile, tol) >= PRED_PROFILE_MATCH_MIN_FIELDS


# =========================================================================
# BEHAVIOUR AGGREGATION
# =========================================================================
def summarize_minute_window(ticks, start_ts, end_ts):
    if not ticks:
        return []
    buckets = {}
    for t in ticks:
        m = int((t["ts"] - start_ts) // 60)
        b = buckets.setdefault(m, {
            "minute": m, "prices": [], "vol_usd": 0.0,
            "buy_usd": 0.0, "sell_usd": 0.0, "trades": 0,
            "buy_fills": 0, "sell_fills": 0,
            "whale_buys": 0, "whale_sells": 0})
        b["prices"].append(t["price"])
        b["vol_usd"] += t.get("vol_usd", 0.0)
        b["buy_usd"] += t.get("taker_buy_usd", 0.0)
        b["sell_usd"] += t.get("taker_sell_usd", 0.0)
        b["trades"] += t.get("trades", 0)
        b["buy_fills"] += t.get("taker_buy_fills", 0)
        b["sell_fills"] += t.get("taker_sell_fills", 0)
        if t.get("taker_buy_usd", 0.0) >= WHALE_ORDER_USD:
            b["whale_buys"] += 1
        if t.get("taker_sell_usd", 0.0) >= WHALE_ORDER_USD:
            b["whale_sells"] += 1
    out = []
    for m in sorted(buckets.keys()):
        b = buckets[m]
        if not b["prices"]:
            continue
        out.append({"minute": m,
                    "open": b["prices"][0], "close": b["prices"][-1],
                    "high": max(b["prices"]), "low": min(b["prices"]),
                    "vol_usd": b["vol_usd"], "buy_usd": b["buy_usd"],
                    "sell_usd": b["sell_usd"], "trades": b["trades"],
                    "buy_fills": b["buy_fills"],
                    "sell_fills": b["sell_fills"],
                    "whale_buys": b["whale_buys"],
                    "whale_sells": b["whale_sells"]})
    return out


def tag_behaviour_events(minute_buckets):
    if not minute_buckets:
        return []
    vols = sorted(b["vol_usd"] for b in minute_buckets if b["vol_usd"] > 0)
    if not vols:
        return []
    med = vols[len(vols) // 2]
    tags = []
    for b in minute_buckets:
        move = (b["close"] - b["open"]) / max(b["open"], 1e-9) * 100.0
        abs_move = abs(move)
        buy, sell, vol = b["buy_usd"], b["sell_usd"], b["vol_usd"]
        buy_dom = buy > sell * 1.4 and buy > 0
        sell_dom = sell > buy * 1.4 and sell > 0
        vol_high = vol > med * 1.5
        vol_low = vol < med * 0.5
        vol_panic = vol > med * 3.0
        stalled = abs_move < STALL_PRICE_PCT
        m = b["minute"]

        if sell_dom and vol_high:
            tags.append({"tag": "aggressive_sell_taker_vol", "minute": m})
        if buy_dom and vol_high:
            tags.append({"tag": "aggressive_buy_taker_vol", "minute": m})
        if sell_dom and not vol_high and not vol_low:
            tags.append({"tag": "aggressive_sell_taker", "minute": m})
        if buy_dom and not vol_high and not vol_low:
            tags.append({"tag": "aggressive_buy_taker", "minute": m})
        if sell_dom and vol_high and stalled:
            tags.append({"tag": "aggressive_sell_limit", "minute": m})
        if buy_dom and vol_high and stalled:
            tags.append({"tag": "aggressive_buy_limit", "minute": m})
        if vol_low and sell_dom:
            tags.append({"tag": "weak_sell_taker_vol", "minute": m})
        if vol_low and buy_dom:
            tags.append({"tag": "weak_buy_taker_vol", "minute": m})
        if vol_low and not buy_dom and not sell_dom and sell > buy:
            tags.append({"tag": "weak_sell_taker", "minute": m})
        if vol_low and not buy_dom and not sell_dom and buy > sell:
            tags.append({"tag": "weak_buy_taker", "minute": m})
        if vol_low and move < -0.15:
            tags.append({"tag": "weak_sell_limit_vol", "minute": m})
        if vol_low and move > 0.15:
            tags.append({"tag": "weak_buy_limit_vol", "minute": m})
        if vol_low and stalled and sell > buy:
            tags.append({"tag": "weak_sell_limit", "minute": m})
        if vol_low and stalled and buy > sell:
            tags.append({"tag": "weak_buy_limit", "minute": m})
        if sell_dom and vol_panic:
            tags.append({"tag": "panic_sell_taker", "minute": m})
        if buy_dom and vol_panic:
            tags.append({"tag": "panic_buy_taker", "minute": m})
        if b["whale_sells"] >= 1:
            tags.append({"tag": "whale_sell_taker", "minute": m})
        if b["whale_buys"] >= 1:
            tags.append({"tag": "whale_buy_taker", "minute": m})
    return tags


# =========================================================================
# FOLLOW-THROUGH
# =========================================================================
def measure_tag_followthrough(ticks, tag_ts, direction):
    out = {str(h): None for h in FOLLOWTHROUGH_HORIZONS_SEC}
    if not ticks:
        return out
    ref = None
    for t in ticks:
        if t["ts"] >= tag_ts:
            ref = t["price"]
            break
    if ref is None or ref <= 0:
        return out
    for h in FOLLOWTHROUGH_HORIZONS_SEC:
        target_ts = tag_ts + h
        chosen = None
        for t in ticks:
            if t["ts"] >= target_ts:
                chosen = t["price"]
                break
        if chosen is None:
            continue
        raw = (chosen - ref) / ref * 100.0
        if direction == "SHORT":
            raw = -raw
        out[str(h)] = round(raw - FEE_ROUND_TRIP_PCT, 3)
    return out


# =========================================================================
# FEATURE INSTANCE MEASUREMENT
# =========================================================================
def measure_feature_instance(minute_buckets, i):
    if i + 1 >= len(minute_buckets):
        return None
    b = minute_buckets[i]
    if b["close"] <= 0:
        return None
    next_b = minute_buckets[i + 1]
    immediate_move = (next_b["close"] - b["close"]) / b["close"] * 100.0
    immediate_net = immediate_move - FEE_ROUND_TRIP_PCT
    peak_move = immediate_move
    peak_minute = 1
    for j in range(1, min(LIVE_PEAK_WINDOW_MIN + 1, len(minute_buckets) - i)):
        cb = minute_buckets[i + j]
        ext_move = (cb["close"] - b["close"]) / b["close"] * 100.0
        if abs(ext_move) > abs(peak_move):
            peak_move = ext_move
            peak_minute = j
    return {"immediate_move_pct": round(immediate_move, 3),
            "immediate_net_pct": round(immediate_net, 3),
            "peak_move_pct": round(peak_move, 3),
            "peak_net_pct": round(peak_move - FEE_ROUND_TRIP_PCT, 3),
            "peak_minute": peak_minute,
            "duration_min": peak_minute}


# =========================================================================
# SIDE RATES
# =========================================================================
def compute_side_rates(b, median_vol):
    buy = b.get("buy_usd", 0.0)
    sell = b.get("sell_usd", 0.0)
    total = buy + sell
    if total <= 0 or median_vol <= 0:
        return {"buy": 0.0, "sell": 0.0, "delta_buy_sell": 0.0}
    buy_rate = min(100.0,
                   (buy / total) * 50.0
                   + min(1.0, buy / (median_vol * 2.0)) * 50.0)
    sell_rate = min(100.0,
                    (sell / total) * 50.0
                    + min(1.0, sell / (median_vol * 2.0)) * 50.0)
    return {"buy": round(buy_rate, 1),
            "sell": round(sell_rate, 1),
            "delta_buy_sell": round(buy_rate - sell_rate, 1)}


# =========================================================================
# SIGNAL CLASSIFICATION
# =========================================================================
def signal_worked(peak_net_pct, direction):
    sign = 1 if direction == "LONG" else -1
    return peak_net_pct * sign >= WIN_THRESHOLD_NET_PCT


def classify_feature_signal(observations, direction):
    empty = {"kind": "NOISE", "signal_ratio": 0.0,
             "median_duration": 0.0, "median_magnitude": 0.0,
             "fired": 0, "moved": 0, "big_moved": 0,
             "direction_aligned": direction}
    if not observations or not direction:
        return empty
    sign = 1 if direction == "LONG" else -1
    aligned_nets = []
    durations_of_moves = []
    for o in observations:
        net = o.get("peak_net_pct", o.get("net_pct", 0.0))
        aligned = net * sign
        aligned_nets.append(aligned)
        if aligned >= FEATURE_EFFECT_MIN_MOVE_PCT:
            durations_of_moves.append(o.get("peak_minute", 1))

    fired = len(aligned_nets)
    moved = sum(1 for a in aligned_nets if a >= FEATURE_EFFECT_MIN_MOVE_PCT)
    big_moved = sum(1 for a in aligned_nets if a >= FEATURE_BIG_MOVE_PCT)
    signal_ratio = moved / fired if fired > 0 else 0.0

    median_duration = 0.0
    if durations_of_moves:
        sorted_d = sorted(durations_of_moves)
        median_duration = sorted_d[len(sorted_d) // 2]

    positive_aligned = sorted(a for a in aligned_nets if a > 0)
    median_magnitude = (positive_aligned[len(positive_aligned) // 2]
                        if positive_aligned else 0.0)

    if signal_ratio < FEATURE_NOISE_SIGNAL_RATIO:
        kind = "NOISE"
    else:
        if median_duration <= 1:
            base = "FLASH"
        elif median_duration <= 5:
            base = "PULSE"
        else:
            base = "SUSTAINED"
        kind = base + ("_BIG" if median_magnitude >= FEATURE_BIG_MOVE_PCT else "")

    return {"kind": kind, "signal_ratio": round(signal_ratio, 3),
            "median_duration": round(median_duration, 1),
            "median_magnitude": round(median_magnitude, 3),
            "fired": fired, "moved": moved, "big_moved": big_moved,
            "direction_aligned": direction}


def kind_priority(kind):
    return {"SUSTAINED_BIG": 6, "PULSE_BIG": 5, "FLASH_BIG": 4,
            "SUSTAINED": 3, "PULSE": 2, "FLASH": 1,
            "NOISE": 0}.get(kind, 0)


# =========================================================================
# FEATURE POWER
# =========================================================================
def compute_feature_power(observations, direction):
    empty = {"power": 0.0, "magnitude": 0.0, "velocity": 0.0,
             "directionality": 0.0, "cleanness": 0.0, "samples": 0}
    if not observations:
        return empty
    sign = 1 if direction == "LONG" else -1
    aligned = [o["peak_net_pct"] * sign for o in observations]
    n = len(aligned)
    if n == 0:
        return empty
    median_mag = sorted(abs(a) for a in aligned)[n // 2]
    velocities = []
    for o in observations:
        pm_min = o.get("peak_minute") or 1
        velocities.append(abs(o["peak_net_pct"]) / max(1, pm_min))
    median_vel = sorted(velocities)[len(velocities) // 2] if velocities else 0
    correct = sum(1 for a in aligned if a >= 0.18)
    directionality = correct / n
    if n >= 2:
        mean_aligned = sum(aligned) / n
        variance = sum((a - mean_aligned) ** 2 for a in aligned) / n
        stdev = variance ** 0.5
        abs_mean = abs(mean_aligned)
        cleanness = abs_mean / (stdev + 0.01)
        cleanness = min(1.0, cleanness)
    else:
        cleanness = 0.5
    mag_score = min(40.0, median_mag * 8.0)
    vel_score = min(20.0, median_vel * 10.0)
    dir_score = directionality * 25.0
    clean_score = cleanness * 15.0
    power = mag_score + vel_score + dir_score + clean_score
    return {"power": round(power, 1),
            "magnitude": round(median_mag, 3),
            "velocity": round(median_vel, 3),
            "directionality": round(directionality, 2),
            "cleanness": round(cleanness, 2),
            "samples": n}


def build_feature_power_table(global_tag_stats):
    table = {}
    for tag, samples in global_tag_stats.items():
        if len(samples) < MIN_OBS_FOR_PATTERN:
            continue
        direction = _tag_direction(tag)
        obs_for_power = []
        for s in samples:
            best_val = None
            best_min = 1
            for k, m in (("60", 1), ("120", 2), ("180", 3)):
                v = s.get(k)
                if v is not None and (best_val is None or abs(v) > abs(best_val)):
                    best_val = v
                    best_min = m
            if best_val is None:
                continue
            obs_for_power.append({"peak_net_pct": best_val,
                                   "peak_minute": best_min,
                                   "direction": direction})
        if not obs_for_power:
            continue
        p = compute_feature_power(obs_for_power, direction)
        table[tag] = {**p, "direction": direction}
    return table


def get_opponent_power(feature_tag, opposite_tags_fired, power_table):
    feature_dir = _tag_direction(feature_tag)
    opp_dir = "SHORT" if feature_dir == "LONG" else "LONG"
    best = None
    for tag in opposite_tags_fired:
        if tag == feature_tag:
            continue
        if _tag_direction(tag) != opp_dir:
            continue
        p = power_table.get(tag)
        if p and (best is None or p["power"] > best["power"]):
            best = p
    return best


def build_side_by_side(observations, direction):
    if not observations:
        return None
    sign = 1 if direction == "LONG" else -1
    worked, failed = [], []
    for o in observations:
        aligned = o.get("peak_net_pct", o.get("net_pct", 0.0)) * sign
        o["_aligned"] = aligned
        if aligned >= WIN_THRESHOLD_NET_PCT:
            worked.append(o)
        elif aligned < WIN_THRESHOLD_NET_PCT * 0.6:
            failed.append(o)
    if not worked:
        return None
    best_worked = max(worked, key=lambda x: x["_aligned"])
    best_failed = max(failed, key=lambda x: -x["_aligned"]) if failed else None

    def profile(o):
        return {"coin": o.get("coin"),
                "minute": o.get("minute"),
                "feature_rate": round(o.get("feature_rate", 0.0), 1),
                "opponent_rate": round(o.get("opponent_rate", 0.0), 1),
                "delta": round(o.get("rate_delta", 0.0), 1),
                "tier": o.get("tier"),
                "tier_weight": o.get("tier_weight"),
                "volume_class": o.get("volume_class"),
                "aligned_net": round(o["_aligned"], 2),
                "peak_minute": o.get("peak_minute"),
                "reason": o.get("reason")}

    result = {"worked": profile(best_worked), "failed": None, "why": ""}
    if best_failed is not None:
        result["failed"] = profile(best_failed)
        w, f = result["worked"], result["failed"]
        points = []
        if w["delta"] > f["delta"] + 5:
            points.append(f"delta {w['delta']:.0f} vs {f['delta']:.0f} "
                          f"— worked case had far stronger side separation")
        if w["opponent_rate"] < f["opponent_rate"] - 5:
            points.append(f"opponent {w['opponent_rate']:.0f} vs "
                          f"{f['opponent_rate']:.0f} — failed case faced "
                          f"comparable opposition that absorbed the move")
        if w["feature_rate"] > f["feature_rate"] + 5:
            points.append(f"feature {w['feature_rate']:.0f} vs "
                          f"{f['feature_rate']:.0f} — failed case had weaker "
                          f"initial signal")
        result["why"] = (" ; ".join(points) if points
                         else "similar rate profiles — outcome divergence "
                              "driven by factors outside rate")
    return result


def learn_rate_patterns(observations, direction):
    if not observations:
        return {}
    from collections import defaultdict
    sign = 1 if direction == "LONG" else -1
    delta_stats = defaultdict(lambda: {"n": 0, "wins": 0})
    opp_stats = defaultdict(lambda: {"n": 0, "wins": 0})
    feat_stats = defaultdict(lambda: {"n": 0, "wins": 0})
    for o in observations:
        aligned = o.get("peak_net_pct", 0.0) * sign
        worked = aligned >= WIN_THRESHOLD_NET_PCT
        delta = abs(o.get("rate_delta", 0.0))
        opp = o.get("opponent_rate", 0.0)
        feat = o.get("feature_rate", 0.0)
        for lo, hi in RATE_BINS_DELTA:
            if lo <= delta < hi:
                k = f"{lo}-{hi}"
                delta_stats[k]["n"] += 1
                if worked:
                    delta_stats[k]["wins"] += 1
                break
        for lo, hi in RATE_BINS_OPP:
            if lo <= opp < hi:
                k = f"{lo}-{hi}"
                opp_stats[k]["n"] += 1
                if worked:
                    opp_stats[k]["wins"] += 1
                break
        for lo, hi in RATE_BINS_FEAT:
            if lo <= feat < hi:
                k = f"{lo}-{hi}"
                feat_stats[k]["n"] += 1
                if worked:
                    feat_stats[k]["wins"] += 1
                break

    def summarize(stats):
        out = {}
        for k, s in stats.items():
            if s["n"] >= MIN_OBS_FOR_PATTERN:
                out[k] = {"win_rate": round(s["wins"] / s["n"], 2),
                          "n": s["n"]}
        return out

    return {"by_delta": summarize(delta_stats),
            "by_opponent": summarize(opp_stats),
            "by_feature": summarize(feat_stats)}


# =========================================================================
# RATE ENTRY
# =========================================================================
def check_live_entry_conditions(feature_rate, opponent_rate):
    delta = feature_rate - opponent_rate
    if feature_rate < LIVE_ENTRY_MIN_FEATURE_RATE:
        return False, f"feature_rate {feature_rate:.0f} < {LIVE_ENTRY_MIN_FEATURE_RATE:.0f}"
    if opponent_rate > LIVE_ENTRY_MAX_OPPONENT_RATE:
        return False, f"opponent_rate {opponent_rate:.0f} > {LIVE_ENTRY_MAX_OPPONENT_RATE:.0f}"
    if delta < LIVE_ENTRY_MIN_DELTA:
        return False, f"delta {delta:.0f} < {LIVE_ENTRY_MIN_DELTA:.0f}"
    return True, (f"OK feature={feature_rate:.0f} "
                  f"opp={opponent_rate:.0f} delta={delta:.0f}")


def check_live_entry_with_power(feature_rate, opponent_rate,
                                 feature_power, opponent_power):
    fr = feature_rate or 0
    orr = opponent_rate or 0
    fp = (feature_power or {}).get("power", 0)
    op = (opponent_power or {}).get("power", 0)
    if fp <= 0:
        return False, "feature power unknown (need 3+ obs)"
    if op <= 0:
        if fr >= LIVE_ENTRY_MIN_FEATURE_RATE:
            return True, f"no known opponent power; feature_rate={fr:.0f}"
        return False, f"no opponent power data, rate {fr:.0f} too low"
    power_ratio = fp / max(1.0, op)
    if power_ratio >= 2.0 and fr >= 40:
        return True, (f"power dominance {fp:.0f}/{op:.0f} "
                      f"(ratio {power_ratio:.1f}x); rate {fr:.0f} ok")
    if power_ratio <= 0.5 and orr >= 50:
        return False, (f"opponent power {op:.0f} >> feature {fp:.0f}; "
                       f"rate {fr:.0f} insufficient")
    return check_live_entry_conditions(fr, orr)


# =========================================================================
# ACCELERATION (strict two-layer gate)
# =========================================================================
def detect_acceleration_signal(minute_buckets, direction):
    """Strict gate. All six must pass:

    1. feature total fills >= 5 (blocks 1-whale crowd)
    2. 3-min total volume ratio >= 3.0x
    3. 3-min total fill ratio >= 2.0x
    4. each minute: volume ratio >= 2.0x
    5. each minute: fill ratio >= 1.5x
    6. feature accelerating every step (>= 1.15x growth)
    """
    empty = {"signal": False, "reason": "insufficient data",
             "feature_vols": [], "opponent_vols": [],
             "feature_total": 0.0, "opponent_total": 0.0,
             "ratio": 0.0, "feature_growth": [], "opponent_growth": [],
             "feature_fills": [], "opponent_fills": [],
             "feature_fill_total": 0, "opponent_fill_total": 0,
             "fill_ratio": 0.0,
             "per_minute_vol_ratios": [],
             "per_minute_fill_ratios": [],
             "feature_avg_order": 0.0, "opponent_avg_order": 0.0,
             "path": None}
    if not minute_buckets or len(minute_buckets) < ACCEL_WINDOW_MIN:
        return empty

    window = minute_buckets[-ACCEL_WINDOW_MIN:]
    if direction == "LONG":
        feat_vols = [b["buy_usd"] for b in window]
        opp_vols = [b["sell_usd"] for b in window]
        feat_fills_arr = [b.get("buy_fills", 0) for b in window]
        opp_fills_arr = [b.get("sell_fills", 0) for b in window]
    else:
        feat_vols = [b["sell_usd"] for b in window]
        opp_vols = [b["buy_usd"] for b in window]
        feat_fills_arr = [b.get("sell_fills", 0) for b in window]
        opp_fills_arr = [b.get("buy_fills", 0) for b in window]

    feat_total = sum(feat_vols)
    opp_total = sum(opp_vols)
    feat_fill_total = sum(feat_fills_arr)
    opp_fill_total = sum(opp_fills_arr)

    pm_vol_ratios = []
    pm_fill_ratios = []
    for i in range(len(window)):
        fv, ov = feat_vols[i], opp_vols[i]
        ff, of = feat_fills_arr[i], opp_fills_arr[i]
        pm_vol_ratios.append(round(fv / ov, 2) if ov > 0 else 999.0)
        pm_fill_ratios.append(round(ff / of, 2) if of > 0 else 999.0)

    result = {**empty,
              "feature_vols": [round(v, 0) for v in feat_vols],
              "opponent_vols": [round(v, 0) for v in opp_vols],
              "feature_total": round(feat_total, 0),
              "opponent_total": round(opp_total, 0),
              "feature_fills": feat_fills_arr,
              "opponent_fills": opp_fills_arr,
              "feature_fill_total": feat_fill_total,
              "opponent_fill_total": opp_fill_total,
              "per_minute_vol_ratios": pm_vol_ratios,
              "per_minute_fill_ratios": pm_fill_ratios}

    if feat_fill_total < ACCEL_MIN_FEATURE_FILLS:
        result["reason"] = (f"feature fills {feat_fill_total} < "
                            f"{ACCEL_MIN_FEATURE_FILLS} — whale-dominated")
        return result
    if feat_total <= 0:
        result["reason"] = "no feature-side volume"
        return result
    if opp_total <= 0:
        result["signal"] = True
        result["ratio"] = 999.0
        result["fill_ratio"] = 999.0
        result["path"] = "ZERO_OPPONENT"
        result["reason"] = (f"opponent volume zero, feature crowd "
                            f"{feat_fill_total} fills totaling ${feat_total:.0f}")
        return result

    ratio = feat_total / opp_total
    result["ratio"] = round(ratio, 2)

    if opp_fill_total > 0:
        result["fill_ratio"] = round(feat_fill_total / opp_fill_total, 2)
        if result["fill_ratio"] < ACCEL_MIN_FILL_RATIO:
            result["reason"] = (f"3-min fill ratio {result['fill_ratio']:.2f}x < "
                                f"{ACCEL_MIN_FILL_RATIO}x")
            return result
    else:
        result["fill_ratio"] = 999.0

    if ratio < ACCEL_MIN_RATIO:
        result["reason"] = (f"3-min volume ratio {ratio:.2f}x < "
                            f"{ACCEL_MIN_RATIO}x")
        return result

    for i in range(len(window)):
        if pm_vol_ratios[i] < ACCEL_MIN_PER_MIN_VOL_RATIO:
            result["reason"] = (f"minute {i+1} volume ratio "
                                f"{pm_vol_ratios[i]:.2f}x < "
                                f"{ACCEL_MIN_PER_MIN_VOL_RATIO}x")
            return result
        if pm_fill_ratios[i] < ACCEL_MIN_PER_MIN_FILL_RATIO:
            result["reason"] = (f"minute {i+1} fill ratio "
                                f"{pm_fill_ratios[i]:.2f}x < "
                                f"{ACCEL_MIN_PER_MIN_FILL_RATIO}x")
            return result

    feat_growth = []
    for i in range(1, len(feat_vols)):
        prev = feat_vols[i - 1]
        curr = feat_vols[i]
        feat_growth.append(round(curr / prev, 2) if prev > 0 else 0.0)
    opp_growth = []
    for i in range(1, len(opp_vols)):
        prev = opp_vols[i - 1]
        curr = opp_vols[i]
        opp_growth.append(round(curr / prev, 2) if prev > 0 else 0.0)
    result["feature_growth"] = feat_growth
    result["opponent_growth"] = opp_growth
    result["feature_avg_order"] = round(
        feat_total / max(1, feat_fill_total), 0)
    result["opponent_avg_order"] = round(
        opp_total / max(1, opp_fill_total), 0)

    if not feat_growth:
        result["reason"] = "no growth data"
        return result
    if not all(g >= ACCEL_FEATURE_MIN_STEP_GROWTH for g in feat_growth):
        result["reason"] = (f"feature not accelerating each step "
                            f"({feat_growth}, need all >= "
                            f"{ACCEL_FEATURE_MIN_STEP_GROWTH}x)")
        return result

    result["signal"] = True
    result["path"] = "CROWD_BACKED_MOMENTUM"
    result["reason"] = (f"3-min: {ratio:.1f}x vol + {result['fill_ratio']:.1f}x fills | "
                        f"per-min vol {pm_vol_ratios} fills {pm_fill_ratios} | "
                        f"accelerating {feat_growth}")
    return result


# =========================================================================
# REASON CLASSIFIERS
# =========================================================================
def _feature_side_of_tag(tag):
    if "buy" in tag:
        return "buy"
    if "sell" in tag:
        return "sell"
    return None


def classify_opposite_side(b, feature_side):
    if not feature_side:
        return "unknown"
    buy, sell = b.get("buy_usd", 0.0), b.get("sell_usd", 0.0)
    own = buy if feature_side == "buy" else sell
    opp = sell if feature_side == "buy" else buy
    if own <= 0:
        return "unknown"
    if opp <= 0:
        return "absent"
    ratio = opp / own
    if ratio < 0.3:
        return "quiet"
    if ratio < 0.6:
        return "weak"
    if ratio > 1.2:
        return "dominant"
    if ratio > 0.8:
        return "strong"
    return "normal"


def classify_volume(b, median_vol):
    if median_vol <= 0:
        return "unknown"
    vol = b.get("vol_usd", 0.0)
    if vol < median_vol * 0.5:
        return "light"
    if vol > median_vol * 3.0:
        return "panic"
    if vol > median_vol * 1.5:
        return "heavy"
    return "normal"


def classify_tier_weight(tier):
    if tier in ("micro", "small"):
        return "light"
    if tier == "mid":
        return "medium"
    if tier in ("large", "mega"):
        return "heavy"
    return "unknown"


def classify_reason_category(opposite_state, volume_class, tier_weight, moved):
    if not moved:
        if opposite_state in ("strong", "dominant"):
            return "absorbed_by_opposition"
        if volume_class == "light":
            return "no_volume"
        if tier_weight == "heavy":
            return "heavy_cap_inertia"
        return "feature_failed"
    if opposite_state in ("quiet", "weak", "absent"):
        return "no_resistance"
    if volume_class in ("heavy", "panic"):
        return "heavy_volume"
    if tier_weight == "light":
        return "light_cap_thin_book"
    if opposite_state in ("strong", "dominant"):
        return "overpowered_opposition"
    return "mixed"


def infer_move_reason(category, opposite_state, volume_class,
                       tier_weight, move_pct):
    t = f"{tier_weight}-cap" if tier_weight != "unknown" else "unknown-cap"
    if category == "no_resistance":
        return f"opposite side was {opposite_state} — no resistance ({t})"
    if category == "heavy_volume":
        return f"{volume_class} volume forced the move on {t}"
    if category == "light_cap_thin_book":
        return f"light-cap inertia — thin book moved easily on {t}"
    if category == "overpowered_opposition":
        return f"overpowered {opposite_state} opposite side on {t}"
    if category == "absorbed_by_opposition":
        return f"absorbed by {opposite_state} opposite side on {t}"
    if category == "no_volume":
        return f"volume too light, {volume_class} flow"
    if category == "heavy_cap_inertia":
        return f"{t} inertia, feature couldn't shift price"
    if category == "feature_failed":
        return f"feature fired but {t} price held"
    return f"mixed — {opposite_state} opposition, {volume_class} volume, {t}"


# =========================================================================
# CYCLE-LEVEL RANKING
# =========================================================================
def rank_cycle_features(watch_ticks, winner_sym, start_ts, tier_map=None):
    tier_map = tier_map or {}
    all_obs = {}
    for sym, ticks in watch_ticks.items():
        if not ticks or len(ticks) < 5:
            continue
        minute_buckets = summarize_minute_window(ticks, start_ts,
                                                  start_ts + 1800)
        if len(minute_buckets) < 3:
            continue
        vols = sorted([b["vol_usd"] for b in minute_buckets if b["vol_usd"] > 0])
        med_vol = vols[len(vols) // 2] if vols else 0.0
        tier = tier_map.get(sym, "unknown")
        tier_weight = classify_tier_weight(tier)
        for i, b in enumerate(minute_buckets[:-1]):
            tags = tag_behaviour_events([b])
            if not tags:
                continue
            measurement = measure_feature_instance(minute_buckets, i)
            if not measurement:
                continue
            net = measurement["immediate_net_pct"]
            moved = abs(net) >= FEATURE_EFFECT_MIN_MOVE_PCT
            vol_class = classify_volume(b, med_vol)
            rates = compute_side_rates(b, med_vol)
            for t in tags:
                tag = t["tag"]
                side = _feature_side_of_tag(tag)
                if side == "buy":
                    feature_rate = rates["buy"]
                    opponent_rate = rates["sell"]
                else:
                    feature_rate = rates["sell"]
                    opponent_rate = rates["buy"]
                rate_delta = feature_rate - opponent_rate
                opp_state = classify_opposite_side(b, side) if side else "unknown"
                cat = classify_reason_category(opp_state, vol_class,
                                                 tier_weight, moved)
                reason = infer_move_reason(cat, opp_state, vol_class,
                                             tier_weight, net)
                all_obs.setdefault(tag, []).append({
                    "coin": sym, "minute": b["minute"] + 1,
                    "net_pct": net, "moved": moved,
                    "immediate_move_pct": measurement["immediate_move_pct"],
                    "peak_move_pct": measurement["peak_move_pct"],
                    "peak_net_pct": measurement["peak_net_pct"],
                    "peak_minute": measurement["peak_minute"],
                    "feature_rate": feature_rate,
                    "opponent_rate": opponent_rate,
                    "rate_delta": rate_delta,
                    "opposite_state": opp_state,
                    "volume_class": vol_class,
                    "tier": tier, "tier_weight": tier_weight,
                    "reason_category": cat, "reason": reason,
                    "was_best_mover": sym == winner_sym,
                    "opposite_tags_fired": [
                        t2["tag"] for t2 in tags
                        if t2["tag"] != tag
                        and _tag_direction(t2["tag"]) != _tag_direction(tag)
                    ]})

    result = {}
    for tag, obs in all_obs.items():
        direction = _tag_direction(tag)
        sign = 1 if direction == "LONG" else -1
        cls = classify_feature_signal(obs, direction)
        winner_inst = next((o for o in obs if o["coin"] == winner_sym), None)
        best = None
        best_aligned = -1e9
        for o in obs:
            aligned = o["peak_net_pct"] * sign
            if aligned > best_aligned:
                best_aligned = aligned
                best = o
        better = []
        if winner_inst:
            w_aligned = winner_inst["peak_net_pct"] * sign
            if w_aligned > 0:
                better = [o for o in obs
                          if o["coin"] != winner_sym
                          and o["peak_net_pct"] * sign > w_aligned + 0.10]
        reasons = {c: 0 for c in REASON_CATEGORIES}
        for o in obs:
            reasons[o["reason_category"]] += 1
        side_by_side = build_side_by_side(obs, direction)
        patterns = learn_rate_patterns(obs, direction)
        result[tag] = {"direction": direction,
                       "kind": cls["kind"],
                       "signal_ratio": cls["signal_ratio"],
                       "median_duration": cls["median_duration"],
                       "median_magnitude": cls["median_magnitude"],
                       "fired": len(obs),
                       "moved_count": cls["moved"],
                       "big_moved": cls["big_moved"],
                       "winner_instance": winner_inst,
                       "best": best, "better": better,
                       "side_by_side": side_by_side,
                       "patterns": patterns,
                       "reasons": reasons, "raw_obs": obs}
    return result


# =========================================================================
# TIER GATES / ECONOMIC / BAN
# =========================================================================
def _window_check(raw_values, gate):
    if len(raw_values) < 5:
        return {"pass": False, "reason": "need 5 samples",
                "window": raw_values[-5:] if raw_values else []}
    win = raw_values[-5:]
    avg = sum(win) / len(win)
    floor = gate.get("majority_floor")
    need = gate.get("majority_count", 3)
    min_avg = gate.get("min_avg")
    reasons = []
    majority_ok = True
    passes_floor = None
    if floor is not None:
        passes_floor = sum(1 for v in win if v >= floor)
        if passes_floor < need:
            majority_ok = False
            reasons.append(f"majority {passes_floor}/{len(win)} < {need}")
    avg_ok = True
    if min_avg is not None and avg < min_avg:
        avg_ok = False
        reasons.append(f"avg {avg:.3f}% < {min_avg:.2f}%")
    return {"pass": majority_ok and avg_ok, "window": win,
            "avg": round(avg, 3), "majority_count": passes_floor,
            "reason": "; ".join(reasons) if reasons else "OK"}


def tier_paper_eligible(tier, samples):
    if tier not in ("micro", "small", "mid", "large", "mega", "unknown"):
        return False, {"reason": "no gate"}
    raws = []
    for s in samples:
        if s.get("tier") != tier:
            continue
        vals = [s.get(k) for k in ("60", "120", "180")
                if s.get(k) is not None]
        if vals:
            raws.append(_raw(max(vals, key=abs)))
    gate = {"majority_floor": 0.40, "majority_count": 3}
    return _window_check(raws, gate)["pass"], _window_check(raws, gate)


def feature_tier_live_ready(tag, tier, live_history):
    th = (live_history.get(tag) or {}).get(tier)
    if not th:
        return False, "no history", {}
    obs_all = th.get("observations") or []
    obs = [o for o in obs_all
           if o.get("reason_category") != "live_trade"][-LIVE_OBS_WINDOW:]
    if len(obs) < LIVE_OBS_WINDOW:
        return False, f"{len(obs)}/{LIVE_OBS_WINDOW} paper obs", {}
    nets = [o["net_pct"] for o in obs]
    wins = sum(1 for n in nets if n > 0)
    avg = sum(nets) / len(nets)
    stats = {"obs": len(obs), "wins": wins, "avg_net": round(avg, 3),
             "avg_peak": round(sum(o.get("peak_net_pct", o["net_pct"])
                                   for o in obs) / len(obs), 3),
             "avg_duration_min": round(sum(o.get("peak_minute", 1)
                                           for o in obs) / len(obs), 2)}
    if wins < LIVE_MIN_WINS_OUT_OF_20:
        return False, f"wins {wins}/20 < {LIVE_MIN_WINS_OUT_OF_20}", stats
    if avg < LIVE_MIN_AVG_NET_PCT:
        return False, f"avg {avg:+.3f}% < {LIVE_MIN_AVG_NET_PCT}%", stats
    return True, f"OK ({wins}/20, avg {avg:+.3f}%)", stats


def tier_should_ban(live_trades):
    if len(live_trades) < LIVE_BAN_CONSECUTIVE_LOSSES:
        return False, f"{len(live_trades)}/{LIVE_BAN_CONSECUTIVE_LOSSES} live trades"
    last = live_trades[-LIVE_BAN_CONSECUTIVE_LOSSES:]
    if all(n < 0 for n in last):
        return True, (f"{LIVE_BAN_CONSECUTIVE_LOSSES} consecutive losses: "
                      + ", ".join(f"{n:+.3f}%" for n in last))
    return False, "last 2 not both losses"


def tier_unban_check(observations, banned_at):
    paper_obs = [o for o in observations
                 if o.get("reason_category") != "live_trade"
                 and o.get("ts", 0) >= banned_at]
    if len(paper_obs) < UNBAN_CONSECUTIVE_PAPER_WINS:
        return False, (f"{len(paper_obs)}/{UNBAN_CONSECUTIVE_PAPER_WINS} "
                       f"paper obs since ban")
    last8 = paper_obs[-UNBAN_CONSECUTIVE_PAPER_WINS:]
    for o in last8:
        if o["net_pct"] <= 0:
            return False, f"non-win in last 8 (net={o['net_pct']:+.3f}%)"
    avg = sum(o["net_pct"] for o in last8) / len(last8)
    if avg < UNBAN_MIN_AVG_NET_PCT:
        return False, f"avg {avg:+.3f}% < {UNBAN_MIN_AVG_NET_PCT:+.2f}%"
    return True, f"8 consecutive wins since ban, avg {avg:+.3f}%"


# =========================================================================
# GLOBAL RANK
# =========================================================================
def rank_features(global_tag_stats, tag_descriptions=None,
                  live_history=None, new_features=None):
    new_features = new_features or set()
    tag_descriptions = tag_descriptions or {}
    live_history = live_history or {}
    if not global_tag_stats:
        return []
    ranked = []
    for tag, samples in global_tag_stats.items():
        if len(samples) < FEATURE_LEADERBOARD_MIN_SAMPLES:
            continue
        direction = _tag_direction(tag)
        obs_for_cls = []
        for s in samples:
            best_val = None
            for k in ("60", "120", "180"):
                v = s.get(k)
                if v is not None and (best_val is None or abs(v) > abs(best_val)):
                    best_val = v
            if best_val is None:
                continue
            obs_for_cls.append({"net_pct": best_val,
                                "peak_net_pct": best_val,
                                "peak_minute": 2,
                                "tier": s.get("tier", "unknown")})
        if not obs_for_cls:
            continue
        cls = classify_feature_signal(obs_for_cls, direction)
        tier_stats = {}
        for tier in set(s.get("tier", "unknown") for s in samples):
            tier_samples = [s for s in samples if s.get("tier") == tier]
            p_ok, p_diag = tier_paper_eligible(tier, samples)
            tier_stats[tier] = {"samples": len(tier_samples),
                                 "paper_pass": p_ok,
                                 "paper_window": p_diag.get("window", []),
                                 "paper_avg": p_diag.get("avg"),
                                 "paper_majority": p_diag.get("majority_count"),
                                 "paper_reason": p_diag.get("reason")}
        ranked.append({"tag": tag,
                       "description": tag_descriptions.get(tag, ""),
                       "is_new_feature": tag in new_features,
                       "direction": direction,
                       "kind": cls["kind"],
                       "signal_ratio": cls["signal_ratio"],
                       "median_duration": cls["median_duration"],
                       "median_magnitude": cls["median_magnitude"],
                       "samples": len(obs_for_cls),
                       "tiers": tier_stats})
    ranked.sort(key=lambda x: (kind_priority(x["kind"]), x["signal_ratio"],
                                x["median_magnitude"]), reverse=True)
    return ranked


# =========================================================================
# STORY BUILDERS
# =========================================================================
def build_behaviour_story(ticks, start_price, end_price, start_ts):
    empty = {"story": "no data", "peak_pct": 0.0, "trough_pct": 0.0,
             "net_pct": 0.0, "verdict": "NO_DATA",
             "peak_minute": None, "trough_minute": None, "tags": []}
    if not ticks or start_price <= 0:
        return empty
    minute_buckets = summarize_minute_window(ticks, start_ts,
                                              start_ts + PRED_MAX_HOLD_SEC)
    if len(minute_buckets) < 3:
        return empty
    prices_all = [t["price"] for t in ticks if t["price"] > 0]
    if not prices_all:
        return empty
    peak = max(prices_all)
    trough = min(prices_all)
    peak_pct = (peak - start_price) / start_price * 100.0
    trough_pct = (trough - start_price) / start_price * 100.0
    net_pct = (end_price - start_price) / start_price * 100.0
    tags_fired = tag_behaviour_events(minute_buckets)
    sentences = [f"Net over 30 minutes: {net_pct:+.2f}% "
                 f"(peak {peak_pct:+.2f}%, trough {trough_pct:+.2f}%)."]
    if net_pct > 0.5:
        verdict = "WINNER_LONG"
    elif net_pct < -0.5:
        verdict = "WINNER_SHORT"
    else:
        verdict = "FLAT"
    return {"story": " ".join(sentences),
            "peak_pct": round(peak_pct, 2),
            "trough_pct": round(trough_pct, 2),
            "net_pct": round(net_pct, 2),
            "peak_minute": None, "trough_minute": None,
            "verdict": verdict, "peak_price": peak, "trough_price": trough,
            "tags": tags_fired}


def find_move_window(ticks, start_ts, min_move_pct=WINNER_MOVE_WINDOW_MIN_PCT):
    minute_buckets = summarize_minute_window(ticks, start_ts, start_ts + 1800)
    if len(minute_buckets) < 3:
        return None
    best = None
    for i in range(len(minute_buckets)):
        for j in range(i + 3, min(i + 9, len(minute_buckets) + 1)):
            start, end = minute_buckets[i], minute_buckets[j - 1]
            if start["open"] <= 0:
                continue
            move = (end["close"] - start["open"]) / start["open"] * 100.0
            if best is None or abs(move) > abs(best["move_pct"]):
                best = {"start_minute": start["minute"] + 1,
                        "end_minute": end["minute"] + 1,
                        "move_pct": round(move, 2),
                        "direction": "LONG" if move > 0 else "SHORT"}
    return best if best and abs(best["move_pct"]) >= min_move_pct else None


def summarize_feature_effects(ticks, start_ts, end_ts):
    minute_buckets = summarize_minute_window(ticks, start_ts, end_ts)
    if len(minute_buckets) < 3:
        return {}, {}
    raw = {}
    for i, b in enumerate(minute_buckets[:-1]):
        tags = tag_behaviour_events([b])
        if not tags:
            continue
        next_b = minute_buckets[i + 1]
        if b["close"] <= 0:
            continue
        move = (next_b["close"] - b["close"]) / b["close"] * 100.0
        net = move - FEE_ROUND_TRIP_PCT
        moved = abs(net) >= FEATURE_EFFECT_MIN_MOVE_PCT
        for t in tags:
            raw.setdefault(t["tag"], []).append({
                "minute": b["minute"] + 1,
                "move_pct": round(move, 3),
                "net_pct": round(net, 3),
                "moved": moved})
    summary = {}
    for tag, samples in raw.items():
        n = len(samples)
        mv = [s for s in samples if s["moved"]]
        um = [s for s in samples if not s["moved"]]
        summary[tag] = {"fired": n, "moved_count": len(mv),
                        "unmoved_count": len(um),
                        "hit_rate": round(len(mv) / n, 3),
                        "avg_net_when_moved": round(sum(s["net_pct"] for s in mv) / len(mv), 3) if mv else 0.0,
                        "avg_net_when_unmoved": round(sum(s["net_pct"] for s in um) / len(um), 3) if um else 0.0,
                        "minutes": [s["minute"] for s in samples]}
    return summary, raw


def build_winner_narrative(winner_sym, ticks, start_price, end_price, start_ts):
    if not ticks:
        return None
    story = build_behaviour_story(ticks, start_price, end_price, start_ts)
    move_window = find_move_window(ticks, start_ts)
    lines = [f"  WINNER: {winner_sym} | net={story['net_pct']:+.2f}% | "
             f"peak={story['peak_pct']:+.2f}% | trough={story['trough_pct']:+.2f}%",
             f"    {story['story']}"]
    if move_window:
        lines.append(f"    BIG MOVE: minutes {move_window['start_minute']}-"
                     f"{move_window['end_minute']} | "
                     f"{move_window['move_pct']:+.2f}% "
                     f"({move_window['direction']})")
    return {"lines": lines, "move_window": move_window, "story": story}


# =========================================================================
# NEW FEATURE DISCOVERY
# =========================================================================
def classify_proposed_tag(minute_buckets, move_pct):
    if not minute_buckets:
        return "unclassified_" + ("up" if move_pct > 0 else "down")
    b = minute_buckets[-1]
    buy, sell = b.get("buy_usd", 0.0), b.get("sell_usd", 0.0)
    total = buy + sell
    taker_imb = (buy - sell) / total if total > 0 else 0.0
    avg_size = total / b.get("trades", 1) if b.get("trades", 0) > 0 else 0.0
    if abs(taker_imb) > 0.5 and avg_size >= 5000:
        return "taker_dominant_" + ("buy" if taker_imb > 0 else "sell")
    if b.get("whale_buys", 0) >= 1 and move_pct > 0:
        return "whale_cluster_buy"
    if b.get("whale_sells", 0) >= 1 and move_pct < 0:
        return "whale_cluster_sell"
    if avg_size < 500:
        return "retail_surge_" + ("up" if move_pct > 0 else "down")
    return "unclassified_" + ("up" if move_pct > 0 else "down")


def describe_move_context(minute_buckets, tags_fired, move_pct, elapsed_sec):
    if not minute_buckets:
        return ""
    b = minute_buckets[-1]
    buy = b.get("buy_usd", 0.0)
    sell = b.get("sell_usd", 0.0)
    vol = b.get("vol_usd", 0.0)
    trades = b.get("trades", 0)
    total = buy + sell
    taker_imb = (buy - sell) / total if total > 0 else 0.0
    avg_size = total / trades if trades > 0 else 0.0
    direction = "up" if move_pct > 0 else "down"
    parts = [f"Price moved {direction} {abs(move_pct):.2f}% in {int(elapsed_sec)}s."]
    if abs(taker_imb) > 0.4:
        dom = "buy" if taker_imb > 0 else "sell"
        parts.append(f"Taker {dom} dominated ({abs(taker_imb)*100:.0f}%).")
    else:
        parts.append("Taker flow balanced.")
    if b.get("whale_buys", 0) > b.get("whale_sells", 0):
        parts.append("Whale buy cluster fired.")
    elif b.get("whale_sells", 0) > b.get("whale_buys", 0):
        parts.append("Whale sell cluster fired.")
    parts.append(f"Avg trade ${avg_size:.0f}. Vol ${vol:.0f}.")
    if tags_fired:
        parts.append("Tags: " + ", ".join(t["tag"] for t in tags_fired) + ".")
    else:
        parts.append("No registered tags fired.")
    desc = " ".join(parts)
    words = desc.split()
    if len(words) > NEW_FEATURE_MAX_DESCRIPTION_WORDS:
        desc = " ".join(words[:NEW_FEATURE_MAX_DESCRIPTION_WORDS])
    return desc


def update_candidate_streak(candidates, tag, tier, net_pct):
    entry = candidates.setdefault(tag, {"occurrences": [], "streak": 0,
                                        "streak_successes": [],
                                        "promoted": False})
    if entry["promoted"]:
        return entry
    if tier in ("large", "mega", "unknown"):
        entry["occurrences"].append({"tier": tier, "net": round(net_pct, 3),
                                      "counted": False})
        return entry
    success = net_pct >= LIVE_NET_TARGET_PCT
    entry["occurrences"].append({"tier": tier, "net": round(net_pct, 3),
                                  "success": success, "counted": True})
    if success:
        entry["streak"] += 1
        entry["streak_successes"].append({"tier": tier,
                                           "net": round(net_pct, 3)})
    else:
        entry["streak"] = 0
        entry["streak_successes"] = []
    if len(entry["occurrences"]) > 100:
        entry["occurrences"] = entry["occurrences"][-100:]
    return entry


def candidate_ready_to_promote(entry):
    if entry.get("promoted"):
        return False
    if entry["streak"] < NEW_FEATURE_PROMOTE_MIN_STREAK:
        return False
    tiers = {s["tier"] for s in entry["streak_successes"]}
    return "mid" in tiers and ("small" in tiers or "micro" in tiers)


# =========================================================================
# EXIT / BOOK / SIZING
# =========================================================================
def check_predict_exit(entry_price, side, current_price, elapsed_sec):
    result = {"should_exit": False, "exit_reason": "HOLD",
              "gross_pnl": 0.0, "net_pnl": 0.0}
    if entry_price <= 0 or current_price <= 0:
        return result
    if side == "SHORT":
        gross = (entry_price - current_price) / entry_price * 100.0
    else:
        gross = (current_price - entry_price) / entry_price * 100.0
    net = gross - FEE_ROUND_TRIP_PCT
    result["gross_pnl"] = gross
    result["net_pnl"] = net
    if elapsed_sec >= PRED_MAX_HOLD_SEC:
        result["should_exit"] = True
        result["exit_reason"] = "TIME_EXIT"
    return result


def evaluate_book(bids, asks, mid_price):
    result = {"is_valid": False, "reason": "INVALID"}
    if mid_price <= 0 or not bids or not asks:
        return result
    bid_floor = mid_price * (1.0 - DEPTH_BAND_PCT)
    d_bid = 0.0
    for p, q in bids:
        pf = _f(p)
        if pf >= bid_floor:
            d_bid += pf * _f(q)
    if d_bid < MIN_SIDE_DEPTH_USD:
        result["reason"] = "THIN_BID"
        return result
    if d_bid > MAX_BID_DEPTH_USD:
        result["reason"] = "WHALE_BID"
        return result
    result["is_valid"] = True
    result["reason"] = "OK"
    return result


def evaluate_book_balance(bids, asks, mid_price):
    result = {"balanced": False, "depth_ratio": 0.0, "d_bid": 0.0, "d_ask": 0.0}
    if mid_price <= 0 or not bids or not asks:
        return result
    bid_floor = mid_price * (1.0 - DEPTH_BAND_PCT)
    ask_ceil = mid_price * (1.0 + DEPTH_BAND_PCT)
    d_bid = d_ask = 0.0
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
    result["balanced"] = (0.7 <= result["depth_ratio"] <= 1.3)
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
