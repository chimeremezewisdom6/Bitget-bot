"""
market_math.py
==============
PREDICT strategy math — paper + live, feature ranking, live ban system.
v2026.12.10
"""
import math

__version__ = "2026.12.10"

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

# ---- Behaviour sampling ----
BEHAVIOUR_MIN_TICKS = 20
WHALE_ORDER_USD = 50_000.0
AGGRESSIVE_TAKER_USD = 20_000.0
QUIET_VOLUME_RATIO = 0.5
PANIC_VOLUME_RATIO = 2.0
STALL_PRICE_PCT = 0.05

# ---- Feature follow-through ----
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

# ---- Live ban system ----
LIVE_FAIL_WINDOW = 5
LIVE_FAIL_MIN_NET_SUM = 0.10
LIVE_BAN_INITIAL_SEC = 7200
LIVE_BAN_MAX_SEC = 86400
LIVE_BAN_CLEAN_RESET_SEC = 86400

# ---- New feature discovery ----
UNEXPLAINED_MOVE_MIN_PCT = 1.1
UNEXPLAINED_MAX_DURATION_SEC = 120
NEW_FEATURE_MAX_CANDIDATES = 40
NEW_FEATURE_PROMOTE_MIN_OCCURRENCES = 5
NEW_FEATURE_PROMOTE_MIN_STREAK = 5
NEW_FEATURE_MAX_DESCRIPTION_WORDS = 200

# ---- Market cap tiers (proxy: 24h volume USD) ----
MARKET_CAP_TIERS = (
    ("micro",  0,            5_000_000),
    ("small",  5_000_000,    20_000_000),
    ("mid",    20_000_000,   100_000_000),
    ("large",  100_000_000,  1_000_000_000),
    ("mega",   1_000_000_000, 1e18),
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
    out = {
        "valid": False, "reason": "NO_DATA",
        "fluct_per_min": 0.0, "recent_abs_pct": 0.0,
        "recent_rate_pct_per_min": 0.0, "prior_move_pct": 0.0,
        "prior_rate_pct_per_min": 0.0, "acceleration": 0.0,
        "distance_from_extreme_pct": 0.0, "direction": None,
        "volume_24h_usd": volume_24h_usd,
        "high_24h": high_24h, "low_24h": low_24h,
    }
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
            "whale_buys": 0, "whale_sells": 0,
        })
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
        out.append({
            "minute": m,
            "open": b["prices"][0], "close": b["prices"][-1],
            "high": max(b["prices"]), "low": min(b["prices"]),
            "vol_usd": b["vol_usd"], "buy_usd": b["buy_usd"],
            "sell_usd": b["sell_usd"], "trades": b["trades"],
            "whale_buys": b["whale_buys"], "whale_sells": b["whale_sells"],
        })
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
        move = abs(b["close"] - b["open"]) / max(b["open"], 1e-9) * 100.0
        buy, sell, vol = b["buy_usd"], b["sell_usd"], b["vol_usd"]
        buy_dom = buy > sell * 1.4 and buy > 0
        sell_dom = sell > buy * 1.4 and sell > 0
        vol_high = vol > med * 1.5
        vol_low = vol < med * 0.5

        if buy_dom and vol_high:
            tags.append({"tag": "aggressive_buy_with_volume", "minute": b["minute"]})
        if sell_dom and vol_high:
            tags.append({"tag": "aggressive_sell_with_volume", "minute": b["minute"]})
        if buy_dom and vol_low:
            tags.append({"tag": "aggressive_buy_no_volume", "minute": b["minute"]})
        if sell_dom and vol_low:
            tags.append({"tag": "aggressive_sell_no_volume", "minute": b["minute"]})

        if b["trades"] > 0 and buy < b["trades"] * 100 and sell < b["trades"] * 100:
            if vol_low and move < STALL_PRICE_PCT:
                if buy > sell:
                    tags.append({"tag": "weak_buy_limits", "minute": b["minute"]})
                elif sell > buy:
                    tags.append({"tag": "weak_sell_limits", "minute": b["minute"]})

        if b["whale_buys"] >= 1:
            tags.append({"tag": "whale_buy_taker", "minute": b["minute"]})
        if b["whale_sells"] >= 1:
            tags.append({"tag": "whale_sell_taker", "minute": b["minute"]})

        if vol_high and move > 0.3 and buy > sell:
            tags.append({"tag": "large_volume_buy", "minute": b["minute"]})
        if vol_high and move < -0.3 and sell > buy:
            tags.append({"tag": "large_volume_sell", "minute": b["minute"]})

        if vol > med * 2.0 and buy_dom:
            tags.append({"tag": "panic_buy", "minute": b["minute"]})
        if vol > med * 2.0 and sell_dom:
            tags.append({"tag": "panic_sell", "minute": b["minute"]})

        if vol_high and move < STALL_PRICE_PCT:
            tags.append({"tag": "stall_under_volume", "minute": b["minute"]})

        if sell_dom and move < STALL_PRICE_PCT:
            tags.append({"tag": "aggressive_sell_quiet_buy", "minute": b["minute"]})
        if buy_dom and move < STALL_PRICE_PCT:
            tags.append({"tag": "aggressive_buy_quiet_sell", "minute": b["minute"]})

    return tags


# =========================================================================
# FOLLOW-THROUGH MEASUREMENT
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


def live_window_fails(recent_net):
    if len(recent_net) < LIVE_FAIL_WINDOW:
        return False, {"reason": f"{len(recent_net)}/{LIVE_FAIL_WINDOW} trades"}
    win = recent_net[-LIVE_FAIL_WINDOW:]
    total = sum(win)
    if total < LIVE_FAIL_MIN_NET_SUM:
        return True, {"reason": f"net sum {total:+.3f}% < {LIVE_FAIL_MIN_NET_SUM:+.2f}%",
                      "window": win, "total": round(total, 3)}
    return False, {"reason": f"net sum {total:+.3f}% — okay",
                   "window": win, "total": round(total, 3)}


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
# FEATURE RANKING
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
            lh = (live_history.get(tag) or {}).get(tier) or {}
            recent_net = lh.get("recent_net", [])
            recent_raw = [_raw(v) for v in recent_net]
            live_win = recent_raw[-GATE_WINDOW:]
            live_avg = (sum(live_win) / len(live_win)) if live_win else 0.0
            live_maj = sum(1 for v in live_win if v >= 0.40) if live_win else 0
            p_ok, p_diag = tier_paper_eligible(tier, samples)
            tier_stats[tier] = {
                "samples": len(vals),
                "hits_at_040": sum(1 for v in vals if v >= 0.40),
                "hits_at_050": sum(1 for v in vals if v >= 0.50),
                "mean_raw_pct": round(sum(vals) / len(vals), 3),
                "median_abs_pct": round(sorted(abs(v) for v in vals)[len(vals) // 2], 3),
                "median_followthrough_pct": round(sorted(vals)[len(vals) // 2], 3),
                "paper_pass": p_ok,
                "paper_window": p_diag.get("window", []),
                "paper_avg": p_diag.get("avg"),
                "paper_majority": p_diag.get("majority_count"),
                "paper_reason": p_diag.get("reason"),
                "live_trades": len(recent_net),
                "live_window": live_win,
                "live_avg_raw": round(live_avg, 3),
                "live_majority": live_maj,
            }
        ranked.append({
            "tag": tag,
            "description": tag_descriptions.get(tag, ""),
            "is_new_feature": tag in new_features,
            "samples": n,
            "hit_rate": round(hit_rate, 3),
            "median_followthrough_pct": round(median_signed, 3),
            "median_abs_pct": round(median_abs, 3),
            "tiers": tier_stats,
        })
    ranked.sort(key=lambda x: (x["hit_rate"], x["median_abs_pct"]), reverse=True)
    return ranked


def build_live_feature_rules(global_tag_stats, tag_descriptions=None,
                             live_history=None, new_features=None):
    tag_descriptions = tag_descriptions or {}
    rules = {}
    for r in rank_features(global_tag_stats, tag_descriptions,
                            live_history, new_features):
        tag = r["tag"]
        samples = global_tag_stats.get(tag, [])
        usable = {}
        for tier, ts in r["tiers"].items():
            if not tier_fully_eligible(tier, [], samples):
                continue
            direction = "LONG" if ts["median_followthrough_pct"] > 0 else "SHORT"
            usable[tier] = {
                "direction": direction,
                "target_pct": LIVE_NET_TARGET_PCT,
                "timeout_sec": LIVE_TAG_TIMEOUT_SEC,
                "samples": ts["samples"],
                "mean_raw_pct": ts["mean_raw_pct"],
                "paper_window": ts["paper_window"],
                "paper_avg": ts["paper_avg"],
                "paper_majority": ts["paper_majority"],
                "live_window": ts["live_window"],
                "live_avg_raw": ts["live_avg_raw"],
                "live_majority": ts["live_majority"],
            }
        if usable:
            rules[tag] = {
                "samples": r["samples"],
                "hit_rate": r["hit_rate"],
                "median_abs_pct": r["median_abs_pct"],
                "description": r["description"],
                "tiers": usable,
            }
    return rules


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
        parts.append(f"Taker {dom} volume dominated ({abs(taker_imb)*100:.0f}% imbalance).")
    else:
        parts.append("Taker flow was balanced.")
    if b.get("whale_buys", 0) > b.get("whale_sells", 0):
        parts.append("Whale buy cluster fired.")
    elif b.get("whale_sells", 0) > b.get("whale_buys", 0):
        parts.append("Whale sell cluster fired.")
    parts.append(f"Average trade size ${avg_size:.0f}.")
    parts.append(f"Total volume ${vol:.0f}.")
    if tags_fired:
        parts.append("Registered tags: " + ", ".join(t["tag"] for t in tags_fired) + ".")
    else:
        parts.append("No registered tags fired.")
    desc = " ".join(parts)
    words = desc.split()
    if len(words) > NEW_FEATURE_MAX_DESCRIPTION_WORDS:
        desc = " ".join(words[:NEW_FEATURE_MAX_DESCRIPTION_WORDS])
    return desc


def update_candidate_streak(candidates, tag, tier, net_pct):
    entry = candidates.setdefault(tag, {
        "occurrences": [], "streak": 0,
        "streak_successes": [], "promoted": False,
    })
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
    vols = [b["vol_usd"] for b in minute_buckets if b["vol_usd"] > 0]
    median_vol = (sorted(vols)[len(vols) // 2]) if vols else 0.0
    tags_fired = tag_behaviour_events(minute_buckets)
    sentences = []

    first3 = minute_buckets[:3]
    first_vol = sum(b["vol_usd"] for b in first3)
    first_buy = sum(b["buy_usd"] for b in first3)
    first_sell = sum(b["sell_usd"] for b in first3)
    if median_vol > 0 and first_vol / max(1, len(first3)) > median_vol * PANIC_VOLUME_RATIO:
        if first_buy > first_sell:
            sentences.append("Right out of the gate buyers swarmed on heavy volume.")
        else:
            sentences.append("Right out of the gate sellers hit hard on heavy volume.")
    elif first_buy > first_sell * 1.3:
        sentences.append("Early minutes tilted toward calm buying.")
    elif first_sell > first_buy * 1.3:
        sentences.append("Early minutes tilted toward calm selling.")

    for b in minute_buckets:
        if b["whale_sells"] >= 2 and b["vol_usd"] > median_vol * 1.5:
            d = "down" if b["close"] < b["open"] else "up"
            sentences.append(f"At minute {b['minute']+1}-{b['minute']+2} whales "
                             f"dumped heavily and price still moved {d}.")
            break
        if b["whale_buys"] >= 2 and b["vol_usd"] > median_vol * 1.5:
            d = "up" if b["close"] > b["open"] else "down"
            sentences.append(f"At minute {b['minute']+1}-{b['minute']+2} whales "
                             f"bought aggressively and price moved {d}.")
            break

    for b in minute_buckets[3:10]:
        move = abs(b["close"] - b["open"]) / max(b["open"], 1e-9) * 100.0
        if b["vol_usd"] > median_vol * 1.5 and move < STALL_PRICE_PCT:
            sentences.append(f"Minutes {b['minute']+1}-{b['minute']+2} saw heavy "
                             f"volume but price barely wiggled — that much flow "
                             f"didn't move price.")
            break

    for b in minute_buckets:
        sell_dom = b["sell_usd"] > b["buy_usd"] * 1.5
        buy_dom = b["buy_usd"] > b["sell_usd"] * 1.5
        move = abs(b["close"] - b["open"]) / max(b["open"], 1e-9) * 100.0
        if sell_dom and move < STALL_PRICE_PCT and b["vol_usd"] > 0:
            sentences.append(f"Minute {b['minute']+1} sellers were aggressive "
                             f"takers, buyers quiet — the aggression didn't move price.")
            break
        if buy_dom and move < STALL_PRICE_PCT and b["vol_usd"] > 0:
            sentences.append(f"Minute {b['minute']+1} buyers were aggressive "
                             f"takers, sellers used limits — the aggression "
                             f"didn't move price.")
            break

    tail = minute_buckets[-10:]
    for b in tail:
        buy_dom = b["buy_usd"] > b["sell_usd"] * 1.5
        sell_dom = b["sell_usd"] > b["buy_usd"] * 1.5
        move = (b["close"] - b["open"]) / max(b["open"], 1e-9) * 100.0
        if buy_dom and b["vol_usd"] > median_vol and move > 0.3:
            sentences.append(f"Minutes {b['minute']+1}-{b['minute']+2} buyers hit "
                             f"large taker volume while sellers sat on limits — "
                             f"moved price up {move:.2f}%.")
            break
        if sell_dom and b["vol_usd"] > median_vol and move < -0.3:
            sentences.append(f"Minutes {b['minute']+1}-{b['minute']+2} sellers hit "
                             f"large taker volume while buyers sat on limits — "
                             f"moved price down {abs(move):.2f}%.")
            break

    peak_minute = trough_minute = None
    pk_ref, tr_ref = -1e18, 1e18
    for t in ticks:
        if t["price"] > pk_ref:
            pk_ref = t["price"]
            peak_minute = int((t["ts"] - start_ts) // 60)
        if t["price"] < tr_ref:
            tr_ref = t["price"]
            trough_minute = int((t["ts"] - start_ts) // 60)

    peak_note = (f"Peak at minute {peak_minute+1} (+{peak_pct:.2f}%). "
                 if peak_minute is not None and peak_pct > 0.5 else "")
    trough_note = (f"Trough at minute {trough_minute+1} ({trough_pct:.2f}%). "
                   if trough_minute is not None and trough_pct < -0.5 else "")
    sentences.append(f"Net over 30 minutes: {net_pct:+.2f}% "
                     f"(peak {peak_pct:+.2f}%, trough {trough_pct:+.2f}%). "
                     f"{peak_note}{trough_note}")

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
            "peak_minute": peak_minute, "trough_minute": trough_minute,
            "verdict": verdict, "peak_price": peak, "trough_price": trough,
            "tags": tags_fired}


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
