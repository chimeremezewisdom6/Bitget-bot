"""
market_math.py
==============
PREDICT strategy math — paper + live, feature ranking, reason classification,
economic live gate, and 8-wins-since-ban unban system.
v2026.12.14
"""
import math

__version__ = "2026.12.14"

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
LIVE_TAG_TIMEOUT_SEC = 180.0

# ---- Feature ranking ----
FEATURE_LEADERBOARD_MIN_SAMPLES = 5

# ---- Tier gates ----
GATE_WINDOW = 5
TIER_GATES = {
    "mega":  {"paper": {"majority_floor": 0.40, "majority_count": 3},
              "live":  {"majority_floor": 0.40, "majority_count": 3,
                        "min_avg": 0.45}},
    "large": {"paper": {"majority_floor": 0.40, "majority_count": 3},
              "live":  {"majority_floor": 0.40, "majority_count": 3,
                        "min_avg": 0.45}},
    "mid":   {"paper": {"majority_floor": 0.40, "majority_count": 3},
              "live":  {"min_avg": 0.45}},
    "small": {"paper": {"majority_floor": 0.40, "majority_count": 3},
              "live":  {"majority_floor": 0.40, "majority_count": 3,
                        "min_avg": 0.45}},
    "micro": {"paper": {"majority_floor": 0.40, "majority_count": 3},
              "live":  {"majority_floor": 0.40, "majority_count": 3,
                        "min_avg": 0.45}},
    "unknown": {"paper": {"majority_floor": 0.40, "majority_count": 3},
                "live":  {"majority_floor": 0.40, "majority_count": 3,
                          "min_avg": 0.45}},
}

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

# ---- Feature effect thresholds ----
FEATURE_EFFECT_MIN_MOVE_PCT = 0.20
WINNER_MOVE_WINDOW_MIN_PCT = 1.0

# ---- Market cap tiers ----
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


# =========================================================================
# MARKET CAP TIER
# =========================================================================
def market_cap_tier_from_volume(vol_24h_usd):
    if vol_24h_usd is None or vol_24h_usd <= 0:
        return "unknown"
    for name, lo, hi in MARKET_CAP_TIERS:
        if lo <= vol_24h_usd < hi:
            return name
    return "unknown"


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
    out.update({
        "peak_price": peak_price, "low_price": low_price, "low_ts": low_ts,
        "current_price": current_price, "dump_pct": dump_pct,
        "dump_rate_pct_per_min":
            dump_pct / duration_min if duration_min > 0 else 0.0,
        "recovery_pct": recovery_pct,
    })
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
# FEATURES FOR PROFILE MATCHING
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


def features_match_profile(features, profile, tol=PRED_PROFILE_MATCH_TOL):
    if not features or not features.get("valid"):
        return False
    if features.get("direction") != profile.get("direction"):
        return False
    for k in ("fluct_per_min", "recent_abs_pct", "prior_move_pct",
              "acceleration", "distance_from_extreme_pct"):
        fv = features.get(k, 0.0)
        pv = profile.get(k, 0.0)
        ratio = fv / max(pv, 0.01)
        if not (1.0 - tol <= ratio <= 1.0 + tol):
            return False
    return True


def features_resemble_profile(features, profile, tol=PRED_PROFILE_RESEMBLE_TOL):
    if not features or not features.get("valid"):
        return False
    if features.get("direction") != profile.get("direction"):
        return False
    for k in ("fluct_per_min", "recent_abs_pct", "prior_move_pct",
              "acceleration", "distance_from_extreme_pct"):
        fv = features.get(k, 0.0)
        pv = profile.get(k, 0.0)
        ratio = fv / max(pv, 0.01)
        if not (1.0 - tol <= ratio <= 1.0 + tol):
            return False
    return True


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
            "whale_buys": 0, "whale_sells": 0})
        b["prices"].append(t["price"])
        b["vol_usd"] += t.get("vol_usd", 0.0)
        b["buy_usd"] += t.get("taker_buy_usd", 0.0)
        b["sell_usd"] += t.get("taker_sell_usd", 0.0)
        b["trades"] += t.get("trades", 0)
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
# FEATURE RATING
# =========================================================================
def compute_feature_rating(hit_rate, avg_magnitude):
    return min(100.0, hit_rate * 60 + min(40.0, avg_magnitude * 20))


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
# CYCLE-LEVEL FEATURE RANKING
# =========================================================================
def rank_cycle_features(watch_ticks, winner_sym, start_ts, tier_map=None):
    tier_map = tier_map or {}
    all_obs = {}
    for sym, ticks in watch_ticks.items():
        if not ticks or len(ticks) < 5:
            continue
        minute_buckets = summarize_minute_window(ticks, start_ts, start_ts + 1800)
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
            for t in tags:
                side = _feature_side_of_tag(t["tag"])
                opp_state = classify_opposite_side(b, side) if side else "unknown"
                cat = classify_reason_category(
                    opp_state, vol_class, tier_weight, moved)
                reason = infer_move_reason(
                    cat, opp_state, vol_class, tier_weight, net)
                all_obs.setdefault(t["tag"], []).append({
                    "coin": sym, "minute": b["minute"] + 1,
                    "net_pct": net, "moved": moved,
                    "immediate_move_pct": measurement["immediate_move_pct"],
                    "peak_move_pct": measurement["peak_move_pct"],
                    "peak_net_pct": measurement["peak_net_pct"],
                    "peak_minute": measurement["peak_minute"],
                    "opposite_state": opp_state,
                    "volume_class": vol_class,
                    "tier": tier, "tier_weight": tier_weight,
                    "reason_category": cat, "reason": reason,
                    "was_best_mover": sym == winner_sym,
                })
    result = {}
    for tag, obs in all_obs.items():
        moved_obs = [o for o in obs if o["moved"]]
        winner_inst = next((o for o in obs if o["coin"] == winner_sym), None)
        best = max(moved_obs, key=lambda o: abs(o["peak_net_pct"])) if moved_obs else None
        better = []
        if winner_inst and winner_inst["moved"]:
            w_abs = abs(winner_inst["peak_net_pct"])
            better = [o for o in moved_obs
                      if o["coin"] != winner_sym
                      and abs(o["peak_net_pct"]) > w_abs + 0.10]
        hit_rate = len(moved_obs) / len(obs) if obs else 0.0
        avg_moved = (sum(abs(o["peak_net_pct"]) for o in moved_obs) / len(moved_obs)
                     if moved_obs else 0.0)
        rating = compute_feature_rating(hit_rate, avg_moved)
        reasons = {c: 0 for c in REASON_CATEGORIES}
        for o in obs:
            reasons[o["reason_category"]] += 1
        result[tag] = {"fired": len(obs), "moved_count": len(moved_obs),
                       "hit_rate": round(hit_rate, 3),
                       "avg_moved": round(avg_moved, 3),
                       "rating": round(rating, 1),
                       "winner_instance": winner_inst,
                       "best": best, "better": better,
                       "reasons": reasons, "raw_obs": obs}
    return result


# =========================================================================
# TIER GATE HELPERS
# =========================================================================
def _best_horizon_raw(sample):
    vals = [sample.get(k) for k in ("60", "120", "180")
            if sample.get(k) is not None]
    if not vals:
        return None
    return _raw(max(vals, key=abs))


def _window_check(raw_values, gate):
    if len(raw_values) < GATE_WINDOW:
        return {"pass": False, "reason": f"need {GATE_WINDOW} samples",
                "window": raw_values[-GATE_WINDOW:] if raw_values else []}
    win = raw_values[-GATE_WINDOW:]
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
    gate = (TIER_GATES.get(tier) or {}).get("paper")
    if not gate:
        return False, {"reason": "no paper gate"}
    raws = []
    for s in samples:
        if s.get("tier") != tier:
            continue
        r = _best_horizon_raw(s)
        if r is not None:
            raws.append(r)
    return _window_check(raws, gate)["pass"], _window_check(raws, gate)


def tier_live_eligible(tier, recent_net):
    gate = (TIER_GATES.get(tier) or {}).get("live")
    if not gate:
        return True, {"reason": "no live gate"}
    raws = [_raw(v) for v in recent_net]
    if len(raws) < GATE_WINDOW:
        return True, {"reason": f"{len(raws)}/{GATE_WINDOW} live trades",
                      "window": raws}
    return _window_check(raws, gate)["pass"], _window_check(raws, gate)


def tier_fully_eligible(tier, recent_net, samples):
    p_ok, _ = tier_paper_eligible(tier, samples)
    return p_ok


def diagnose_tier(tier, recent_net, samples):
    p_ok, p_diag = tier_paper_eligible(tier, samples)
    l_ok, l_diag = tier_live_eligible(tier, recent_net)
    return {"paper_pass": p_ok, "paper": p_diag,
            "live_pass": l_ok, "live": l_diag,
            "eligible": p_ok and l_ok}


# =========================================================================
# ECONOMIC LIVE GATE
# =========================================================================
def feature_tier_live_ready(tag, tier, live_history):
    """Live gate uses paper evidence only: 20 obs, 15+ wins, avg net >= 0.15%."""
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


# =========================================================================
# BAN SYSTEM
# =========================================================================
def tier_should_ban(live_trades):
    """Ban when the last 2 live trades are both losses."""
    if len(live_trades) < LIVE_BAN_CONSECUTIVE_LOSSES:
        return False, f"{len(live_trades)}/{LIVE_BAN_CONSECUTIVE_LOSSES} live trades"
    last = live_trades[-LIVE_BAN_CONSECUTIVE_LOSSES:]
    if all(n < 0 for n in last):
        return True, (f"{LIVE_BAN_CONSECUTIVE_LOSSES} consecutive losses: "
                      + ", ".join(f"{n:+.3f}%" for n in last))
    return False, "last 2 not both losses"


def tier_unban_check(observations, banned_at):
    """Unban when the last 8 paper obs AFTER banned_at are all wins with avg >= 0.2%."""
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
# FEATURE LEADERBOARD / RANK (global)
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
        vals_all = []
        for s in samples:
            for k in ("60", "120", "180"):
                v = s.get(k)
                if v is not None:
                    vals_all.append(v)
        if not vals_all:
            continue
        n = len(vals_all)
        hits = sum(1 for v in vals_all if abs(v) >= LIVE_NET_TARGET_PCT)
        hit_rate = hits / n
        median_abs = sorted(abs(v) for v in vals_all)[n // 2]
        median_signed = sorted(vals_all)[n // 2]
        tier_stats = {}
        for tier in set(s.get("tier", "unknown") for s in samples):
            tier_samples = [s for s in samples if s.get("tier") == tier]
            vals = []
            for s in tier_samples:
                r = _best_horizon_raw(s)
                if r is not None:
                    vals.append(r)
            if not vals:
                continue
            p_ok, p_diag = tier_paper_eligible(tier, samples)
            tier_stats[tier] = {"samples": len(vals),
                                "paper_pass": p_ok,
                                "paper_window": p_diag.get("window", []),
                                "paper_avg": p_diag.get("avg"),
                                "paper_majority": p_diag.get("majority_count"),
                                "paper_reason": p_diag.get("reason")}
        ranked.append({"tag": tag,
                       "description": tag_descriptions.get(tag, ""),
                       "is_new_feature": tag in new_features,
                       "samples": n, "hit_rate": round(hit_rate, 3),
                       "median_followthrough_pct": round(median_signed, 3),
                       "median_abs_pct": round(median_abs, 3),
                       "tiers": tier_stats})
    ranked.sort(key=lambda x: (x["hit_rate"], x["median_abs_pct"]), reverse=True)
    return ranked


# =========================================================================
# STORY BUILDER
# =========================================================================
def build_behaviour_story(ticks, start_price, end_price, start_ts):
    empty = {"story": "no data", "peak_pct": 0.0, "trough_pct": 0.0,
             "net_pct": 0.0, "verdict": "NO_DATA",
             "peak_minute": None, "trough_minute": None, "tags": []}
    if not ticks or start_price <= 0:
        return empty
    minute_buckets = summarize_minute_window(
        ticks, start_ts, start_ts + PRED_MAX_HOLD_SEC)
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
    sentences = []
    sentences.append(f"Net over 30 minutes: {net_pct:+.2f}% "
                     f"(peak {peak_pct:+.2f}%, trough {trough_pct:+.2f}%).")
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
    effects, raw = summarize_feature_effects(ticks, start_ts, start_ts + 1800)
    move_window = find_move_window(ticks, start_ts)
    lines = [f"  WINNER: {winner_sym} | net={story['net_pct']:+.2f}% | "
             f"peak={story['peak_pct']:+.2f}% | trough={story['trough_pct']:+.2f}%",
             f"    {story['story']}"]
    if move_window:
        lines.append(f"    BIG MOVE: minutes {move_window['start_minute']}-"
                     f"{move_window['end_minute']} | "
                     f"{move_window['move_pct']:+.2f}% "
                     f"({move_window['direction']})")
    return {"lines": lines, "effects": effects, "raw": raw,
            "move_window": move_window, "story": story}


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
    buy, sell, vol = b.get("buy_usd", 0.0), b.get("sell_usd", 0.0), b.get("vol_usd", 0.0)
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
                                        "streak_successes": [], "promoted": False})
    if entry["promoted"]:
        return entry
    if tier in ("large", "mega", "unknown"):
        entry["occurrences"].append({"tier": tier, "net": round(net_pct, 3), "counted": False})
        return entry
    success = net_pct >= LIVE_NET_TARGET_PCT
    entry["occurrences"].append({"tier": tier, "net": round(net_pct, 3),
                                  "success": success, "counted": True})
    if success:
        entry["streak"] += 1
        entry["streak_successes"].append({"tier": tier, "net": round(net_pct, 3)})
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
# EXIT
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


# =========================================================================
# BOOK / SPREAD / SIZING
# =========================================================================
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
