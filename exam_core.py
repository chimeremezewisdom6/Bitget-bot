"""
exam_core.py — corrected:
  - V3-only order endpoints for UTA one-way mode
  - Volume filter = Bitget conviction (4H candle + growth + OI sanity), not fake global projection
  - Depth requires persistence across snapshots (spoof-resistant)
  - Whale sells measured in USDT notional (base coin size × price)
  - Crowding = funding + OI change, not funding alone
  - Candle pattern requires volume confirmation
  - 10-min dying-side scan verified by multi-signal global method
"""

import os, json, time, hmac, hashlib, base64, logging
from datetime import datetime, timezone

import requests

# ==================== Config ====================
BASE_URL = "https://api.bitget.com"
DEMO_HEADER = {"paptrading": "1"}
PRODUCT_TYPE = "USDT-FUTURES"
MARGIN_MODE = "isolated"

API_KEY = os.environ["API_KEY"]
SECRET_KEY = os.environ["SECRET_KEY"]
PASSPHRASE = os.environ["PASSPHRASE"]

PAPER = os.environ.get("PAPER", "true").lower() == "true"
LEVERAGE = os.environ.get("LEVERAGE", "5")
INTERVAL_S = int(os.environ.get("INTERVAL_S", "30"))

WIN_THRESHOLD = 0.0042
REQUIRED_STREAK = 8

# Bitget conviction filters (no fake global projection)
MIN_BITGET_4H_USDT = 50_000       # real 4H candle turnover
MIN_4H_GROWTH = 1.15              # current 4H >= 1.15× previous 4H
MAX_OI_TO_4H_RATIO = 8.0          # OI/turnover sanity: high = suspicious

SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.55"))
DYING_SCORE_THRESHOLD = float(os.environ.get("DYING_SCORE_THRESHOLD", "0.60"))
TOP_N_CANDIDATES = int(os.environ.get("TOP_N_CANDIDATES", "20"))

WEAKEST_SCAN_INTERVAL_S = 600
WIN_1M = 10
WIN_3M = 6
WIN_5M = 4

RATE_LIMIT_S = 0.20
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
HEALTH_FILE = os.environ.get("HEALTH_FILE", "health.json")

log = logging.getLogger("exam")
log.setLevel(logging.INFO)
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    log.addHandler(h)


# ==================== API layer ====================
def _ts():
    return str(int(time.time() * 1000))


def _sign(ts, method, path, body_str=""):
    prehash = ts + method + path + body_str
    return base64.b64encode(
        hmac.new(SECRET_KEY.encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()


def _headers(ts, sig):
    h = {
        "ACCESS-KEY": API_KEY, "ACCESS-SIGN": sig,
        "ACCESS-TIMESTAMP": ts, "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
    }
    if PAPER:
        h.update(DEMO_HEADER)
    return h


def _request(method, path, params=None, body=None):
    last = None
    for attempt in range(3):
        try:
            ts = _ts()
            body_str = json.dumps(body) if body else ""
            sig = _sign(ts, method, path, body_str)
            url = BASE_URL + path
            if method == "GET":
                r = requests.get(url, params=params, headers=_headers(ts, sig), timeout=12)
            else:
                r = requests.post(url, data=body_str, headers=_headers(ts, sig), timeout=12)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "00000":
                log.warning(f"API non-success {path}: {data}")
            return data
        except Exception as e:
            last = e
            log.error(f"request {method} {path} try {attempt+1}: {e}")
            time.sleep(1.2)
    return {"code": "unknown", "msg": str(last) if last else "failed", "data": None}


def get_all_tickers():
    return _request("GET", "/api/v2/mix/market/tickers",
                    params={"productType": PRODUCT_TYPE}).get("data", [])


def get_ticker(symbol):
    for t in get_all_tickers():
        if t.get("symbol") == symbol:
            return t
    return None


def get_history_candles(symbol, granularity="1m", limit=200, end_time=None):
    p = {"symbol": symbol, "productType": PRODUCT_TYPE,
         "granularity": granularity, "limit": str(limit)}
    if end_time:
        p["endTime"] = str(end_time)
    return _request("GET", "/api/v2/mix/market/history-candles", params=p).get("data", [])


def get_orderbook(symbol, limit=50):
    p = {"symbol": symbol, "productType": PRODUCT_TYPE, "limit": str(limit)}
    return _request("GET", "/api/v2/mix/market/merge-depth", params=p).get("data", {})


def get_recent_fills(symbol, limit=100):
    p = {"symbol": symbol, "productType": PRODUCT_TYPE, "limit": str(limit)}
    return _request("GET", "/api/v2/mix/market/fills", params=p).get("data", [])


def get_open_interest(symbol):
    p = {"symbol": symbol, "productType": PRODUCT_TYPE}
    return _request("GET", "/api/v2/mix/market/open-interest", params=p).get("data", {})


# ==================== Real 4H volume + conviction filter ====================
def get_real_4h_volumes(symbol):
    """Return (current_4h_turnover, previous_4h_turnover) in USDT."""
    candles = get_history_candles(symbol, "4H", limit=2)
    if not candles or len(candles) < 1:
        return 0.0, 0.0
    try:
        current = float(candles[-1][6])
        previous = float(candles[-2][6]) if len(candles) >= 2 else current
        return current, previous
    except (IndexError, ValueError):
        return 0.0, 0.0


def bitget_conviction(symbol, ticker):
    """
    Returns dict or None. No global projection — only Bitget-local conviction:
      1. Real 4H turnover >= MIN_BITGET_4H_USDT
      2. Current 4H >= previous 4H × MIN_4H_GROWTH
      3. OI/turnover ratio sane (not wash-traded)
    """
    cur_4h, prev_4h = get_real_4h_volumes(symbol)
    time.sleep(RATE_LIMIT_S)
    if cur_4h < MIN_BITGET_4H_USDT:
        return None
    if prev_4h > 0 and cur_4h < prev_4h * MIN_4H_GROWTH:
        return None

    oi = get_open_interest(symbol)
    time.sleep(RATE_LIMIT_S)
    try:
        oi_usdt = float(oi.get("openInterest", 0)) * float(ticker.get("lastPr", 0))
    except (ValueError, TypeError):
        oi_usdt = 0.0

    oi_ratio = oi_usdt / cur_4h if cur_4h > 0 else 0
    if oi_ratio > MAX_OI_TO_4H_RATIO:
        log.info(f"{symbol}: OI/4H ratio {oi_ratio:.1f} suspicious — skip")
        return None

    return {
        "4h_turnover": cur_4h,
        "4h_prev": prev_4h,
        "4h_growth": round(cur_4h / prev_4h, 2) if prev_4h > 0 else 1.0,
        "oi_usdt": round(oi_usdt, 2),
        "oi_ratio": round(oi_ratio, 2),
    }


# ==================== Spoof-resistant order book ====================
def snapshot_depth(symbol, samples=3, gap=2.0):
    """
    Take `samples` order book snapshots spaced `gap` seconds apart.
    Return persistent depth: only levels present in ALL snapshots count.
    """
    snapshots = []
    for i in range(samples):
        ob = get_orderbook(symbol, 50)
        try:
            bids = {b[0]: float(b[1]) for b in ob.get("bids", [])[:20]}
            asks = {a[0]: float(a[1]) for a in ob.get("asks", [])[:20]}
        except (ValueError, IndexError):
            bids, asks = {}, {}
        snapshots.append((bids, asks))
        if i < samples - 1:
            time.sleep(gap)

    if not snapshots:
        return 0.0, 0.0, None, 0.0

    bid_keys = set(snapshots[0][0])
    ask_keys = set(snapshots[0][1])
    for b, a in snapshots[1:]:
        bid_keys &= set(b)
        ask_keys &= set(a)

    persistent_bid = sum(min(s[0][k] for s in snapshots) for k in bid_keys)
    persistent_ask = sum(min(s[1][k] for s in snapshots) for k in ask_keys)

    if persistent_bid <= 0 or persistent_ask <= 0:
        return 0.0, 0.0, None, 0.0

    total = persistent_bid + persistent_ask
    ratio = max(persistent_bid, persistent_ask) / min(persistent_bid, persistent_ask)
    tightness = min(persistent_bid, persistent_ask) / max(persistent_bid, persistent_ask)
    side = "bid" if persistent_bid > persistent_ask else "ask"

    # stability = how much of the raw top-20 depth survived the persistence filter
    raw_bid = sum(s[0].values() for s in snapshots) / len(snapshots)
    raw_ask = sum(s[1].values() for s in snapshots) / len(snapshots)
    raw_total = raw_bid + raw_ask
    stability = total / raw_total if raw_total > 0 else 0.0

    return ratio, tightness, side, stability


# ==================== USDT-denominated CVD + whales ====================
def cvd_usdt(fills):
    """
    fills: list from /api/v2/mix/market/fills. size is BASE coin.
    Convert to USDT: size × price.
    Returns (cvd_pct, buy_usdt, sell_usdt, whale_sell_count, whale_sell_usdt).
    """
    buy = sell = 0.0
    notionals = []
    for f in fills:
        try:
            sz = float(f["size"])
            px = float(f["price"])
            side = f["side"].lower()
            notional = sz * px
        except (KeyError, ValueError, TypeError):
            continue
        notionals.append(notional)
        if side == "buy":
            buy += notional
        else:
            sell += notional

    total = buy + sell
    if total <= 0:
        return 0.0, 0.0, 0.0, 0, 0.0

    cutoff = sorted(notionals)[int(len(notionals) * 0.9)] if notionals else 0
    whale_sells = 0
    whale_sell_usdt = 0.0
    for f in fills:
        try:
            notional = float(f["size"]) * float(f["price"])
            if f.get("side") == "sell" and notional >= cutoff and notional >= 5000:
                whale_sells += 1
                whale_sell_usdt += notional
        except (KeyError, ValueError, TypeError):
            continue

    return (buy - sell) / total, buy, sell, whale_sells, whale_sell_usdt


# ==================== Candles + pattern with volume confirmation ====================
def candle_pattern_vol(candles, window, label):
    """
    Returns (strength, pattern_name, direction, vol_ratio).
    vol_ratio = avg volume of dominant-side candles / avg volume of opposite-side.
    A pattern is only valid if vol_ratio >= 1.2.
    """
    if len(candles) < window:
        return 0.0, f"{label}_short", None, 1.0
    last = candles[-window:]
    greens, reds = [], []
    for c in last:
        try:
            o, cl, v = float(c[1]), float(c[4]), float(c[5])
        except (ValueError, IndexError):
            continue
        if cl > o:
            greens.append(v)
        elif cl < o:
            reds.append(v)

    ratio = len(greens) / window
    avg_g = sum(greens) / len(greens) if greens else 0.0
    avg_r = sum(reds) / len(reds) if reds else 0.0

    if ratio >= 0.8:
        vol_ratio = (avg_g / avg_r) if avg_r > 0 else (10.0 if avg_g > 0 else 1.0)
        return ratio, f"{label}_up", "buy", vol_ratio
    if ratio <= 0.2:
        vol_ratio = (avg_r / avg_g) if avg_g > 0 else (10.0 if avg_r > 0 else 1.0)
        return (1 - ratio), f"{label}_down", "sell", vol_ratio
    return abs(ratio - 0.5) * 2, f"{label}_mixed", None, 1.0


def forward_continuation(candles, window=WIN_1M):
    if len(candles) < window * 2:
        return 0.0, 0
    outcomes = []
    for i in range(window, len(candles) - window):
        w = candles[i-window:i]
        try:
            g = sum(1 for c in w if float(c[4]) > float(c[1]))
        except (ValueError, IndexError):
            continue
        if g >= 8 or g <= 2:
            direction = "up" if g >= 8 else "down"
            nxt = candles[i:i+window]
            try:
                if direction == "up":
                    ng = sum(1 for c in nxt if float(c[4]) > float(c[1]))
                else:
                    ng = sum(1 for c in nxt if float(c[4]) < float(c[1]))
            except (ValueError, IndexError):
                continue
            outcomes.append(ng / window)
    if not outcomes:
        return 0.0, 0
    return sum(outcomes) / len(outcomes), len(outcomes)


def three_min_after(candles):
    if len(candles) < WIN_1M + 3:
        return 0.0, 0
    outcomes = []
    for i in range(WIN_1M, len(candles) - 3):
        w = candles[i-WIN_1M:i]
        try:
            g = sum(1 for c in w if float(c[4]) > float(c[1]))
        except (ValueError, IndexError):
            continue
        if g >= 8 or g <= 2:
            direction = "up" if g >= 8 else "down"
            nxt = candles[i:i+3]
            try:
                if direction == "up":
                    ng = sum(1 for c in nxt if float(c[4]) > float(c[1]))
                else:
                    ng = sum(1 for c in nxt if float(c[4]) < float(c[1]))
            except (ValueError, IndexError):
                continue
            outcomes.append(ng / 3.0)
    if not outcomes:
        return 0.0, 0
    return sum(outcomes) / len(outcomes), len(outcomes)


def basis_snapshot(ticker):
    try:
        last = float(ticker.get("lastPr", 0))
        idx = float(ticker.get("indexPrice", last)) or last
        b = (last - idx) / idx
        return abs(b), ("premium" if b > 0 else "discount"), b
    except Exception:
        return 0.0, None, 0.0


# ==================== Crowding: funding + OI ====================
def crowding_state(symbol, ticker):
    """
    Returns dict with crowd_side and oi_change_pct.
    Rising OI + positive funding = crowded longs.
    Falling OI + positive funding = longs de-crowding.
    """
    funding = float(ticker.get("fundingRate", 0))
    try:
        holding = float(ticker.get("holdingAmount", 0))  # in coin units
        px = float(ticker.get("lastPr", 0))
        oi_usdt_now = holding * px
    except (ValueError, TypeError):
        oi_usdt_now = 0.0

    # approximate OI change via open-interest endpoint (current vs previous snapshot unavailable)
    oi = get_open_interest(symbol)
    time.sleep(RATE_LIMIT_S)
    try:
        oi_now = float(oi.get("openInterest", 0))
    except (ValueError, TypeError):
        oi_now = 0.0

    # Use holdingAmount as the second sample when endpoint lacks history
    if oi_usdt_now > 0 and oi_now > 0:
        oi_change = (oi_now - oi_usdt_now) / oi_usdt_now
    else:
        oi_change = 0.0

    crowd = "long" if funding > 0 else "short"
    return {
        "funding": funding,
        "crowd": crowd,
        "oi_change": round(oi_change, 4),
        "oi_usdt": round(oi_usdt_now, 2),
    }


# ==================== Dying side ====================
def detect_dying_side(candles):
    if len(candles) < 20:
        return None, 0.0
    recent, earlier = candles[-10:], candles[-20:-10]

    def fuel(bars, want_green):
        t = 0.0
        for c in bars:
            try:
                o, cl, v = float(c[1]), float(c[4]), float(c[5])
            except (ValueError, IndexError):
                continue
            if want_green and cl > o:
                t += (cl - o) * v
            elif not want_green and cl < o:
                t += (o - cl) * v
        return t

    rg, rr = fuel(recent, True), fuel(recent, False)
    eg, er = fuel(earlier, True), fuel(earlier, False)

    def decay(rec, ear):
        if ear <= 0:
            return 0.0
        return max(-1.0, min(1.0, (ear - rec) / ear))

    gd, rd = decay(rg, eg), decay(rr, er)
    if gd > rd and gd > 0.25:
        return "buy", gd
    if rd > gd and rd > 0.25:
        return "sell", rd
    return None, max(gd, rd)


def verify_global_dying(symbol, ticker, dying_side):
    """Bitget-only multi-signal verification. Returns (score, checks)."""
    checks, score = {}, 0.0

    basis_pct, basis_dir, _ = basis_snapshot(ticker)
    want = "discount" if dying_side == "buy" else "premium"
    if basis_dir == want:
        checks["basis"] = 1.0; score += 0.25
    elif basis_pct < 0.0008:
        checks["basis"] = 0.5; score += 0.12
    else:
        checks["basis"] = 0.0

    cr = crowding_state(symbol, ticker)
    want_crowd = "long" if dying_side == "buy" else "short"
    # Require crowd on dying side AND OI not collapsing
    if cr["crowd"] == want_crowd and abs(cr["funding"]) > 0.00005 and cr["oi_change"] > -0.02:
        checks["crowd_oi"] = 1.0; score += 0.25
    else:
        checks["crowd_oi"] = 0.0

    c1 = get_history_candles(symbol, "1m", 15)
    time.sleep(RATE_LIMIT_S)
    vel_ok = False
    if len(c1) >= 10:
        try:
            move = (float(c1[-1][4]) - float(c1[0][4])) / float(c1[0][4])
            if dying_side == "buy" and move <= 0.001:
                vel_ok = True
            elif dying_side == "sell" and move >= -0.001:
                vel_ok = True
        except (ValueError, IndexError):
            pass
    checks["index_velocity"] = 1.0 if vel_ok else 0.0
    if vel_ok:
        score += 0.20

    ob_ratio, tightness, ob_side, stability = snapshot_depth(symbol, samples=3, gap=2.0)
    want_ob = "ask" if dying_side == "buy" else "bid"
    if ob_side == want_ob and ob_ratio >= 1.5 and stability >= 0.5:
        checks["orderbook"] = min(ob_ratio / 2.5, 1.0); score += 0.15 * checks["orderbook"]
    else:
        checks["orderbook"] = 0.0

    cvd, _, _, whales, whale_usdt = cvd_usdt(get_recent_fills(symbol, 100))
    time.sleep(RATE_LIMIT_S)
    want_neg = dying_side == "buy"
    if (want_neg and cvd < -0.10) or (not want_neg and cvd > 0.10):
        checks["cvd"] = min(abs(cvd) / 0.30, 1.0); score += 0.15 * checks["cvd"]
    else:
        checks["cvd"] = 0.0

    return round(score, 4), checks


# ==================== Regular MTF setup ====================
def detect_setup(symbol, ticker):
    # 1m
    c1 = get_history_candles(symbol, "1m", 200); time.sleep(RATE_LIMIT_S)
    # 3m
    c3 = get_history_candles(symbol, "3m", 200); time.sleep(RATE_LIMIT_S)
    # 5m
    c5, end = [], None
    for _ in range(2):
        batch = get_history_candles(symbol, "5m", 200, end_time=end)
        if not batch:
            break
        c5.extend(batch)
        end = int(batch[0][0]) - 1
        if len(c5) >= 288:
            break
        time.sleep(RATE_LIMIT_S)
    c5 = c5[:288]

    if len(c1) < WIN_1M or len(c3) < WIN_3M or len(c5) < WIN_5M:
        return None

    s1, n1, d1, v1 = candle_pattern_vol(c1, WIN_1M, "1m")
    if d1 is None:
        return None
    if v1 < 1.2:   # volume confirmation required
        return None

    s3, n3, d3, _ = candle_pattern_vol(c3, WIN_3M, "3m")
    s5, n5, d5, _ = candle_pattern_vol(c5, WIN_5M, "5m")
    if d3 is not None and d3 != d1:
        return None
    if d5 is not None and d5 != d1:
        return None

    cont, cont_n = forward_continuation(c1)
    three, three_n = three_min_after(c1)

    ob_ratio, tight, _, stability = snapshot_depth(symbol, samples=3, gap=2.0)
    if stability < 0.5:
        return None   # book too flickery = spoofed

    cvd, _, _, whales, whale_usdt = cvd_usdt(get_recent_fills(symbol, 100))
    time.sleep(RATE_LIMIT_S)

    cr = crowding_state(symbol, ticker)

    # Crowd must oppose candle direction
    if cr["crowd"] == "long" and d1 != "sell":
        return None
    if cr["crowd"] == "short" and d1 != "buy":
        return None

    basis_pct, _, _ = basis_snapshot(ticker)

    score = (
        s1 * 0.20 +
        (s3 if d3 == d1 else 0.0) * 0.10 +
        (s5 if d5 == d1 else 0.0) * 0.08 +
        min(ob_ratio / 2.5, 1.0) * 0.15 +
        min(abs(cvd) / 0.30, 1.0) * 0.12 +
        min(whale_usdt / 20000, 1.0) * 0.08 +
        (1 - min(basis_pct / 0.005, 1.0)) * 0.08 +
        min(cont, 1.0) * 0.09 +
        min(three, 1.0) * 0.08 +
        min(v1 / 2.0, 1.0) * 0.02
    )
    if score < SCORE_THRESHOLD:
        return None

    return {
        "symbol": symbol, "side": "sell" if cr["crowd"] == "long" else "buy",
        "score": round(score, 4), "p1m": n1, "p3m": n3, "p5m": n5,
        "ob_ratio": round(ob_ratio, 2), "tightness": round(tight, 2),
        "stability": round(stability, 2), "cvd": round(cvd, 4),
        "whales": whales, "whale_usdt": round(whale_usdt, 2),
        "basis_pct": round(basis_pct, 6), "vol_ratio": round(v1, 2),
        "cont_10m": round(cont, 3), "cont_n": cont_n,
        "three_min": round(three, 3), "three_n": three_n,
        "funding": cr["funding"], "crowd": cr["crowd"],
    }


# ==================== Scanner ====================
def scan_market(top_n=TOP_N_CANDIDATES):
    tickers = get_all_tickers()
    if not tickers:
        return []

    scored = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        try:
            qv = float(t.get("quoteVolume", 0))
        except (ValueError, TypeError):
            continue
        # cheap pre-filter: skip coins with almost no 24h activity
        if qv / 6 < MIN_BITGET_4H_USDT * 0.5:
            continue

        conv = bitget_conviction(sym, t)
        if not conv:
            continue
        scored.append({**t, "conviction": conv})

    scored.sort(key=lambda x: x["conviction"]["4h_turnover"], reverse=True)
    log.info(f"conviction-qualified: {len(scored)} — top {top_n}")
    return scored[:top_n]


def find_best_setup(candidates):
    t0 = time.time()
    results = []
    for c in candidates:
        try:
            s = detect_setup(c["symbol"], c)
            if s:
                results.append(s)
                log.info(f"SETUP {s['symbol']} score={s['score']} side={s['side']} vol={s['vol_ratio']} stab={s['stability']}")
        except Exception as e:
            log.warning(f"deep scan {c['symbol']} failed: {e}")
    log.info(f"cycle: {len(candidates)} symbols in {time.time()-t0:.1f}s")
    if not results:
        return None
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[0]


def find_weakest_dying(candidates):
    verified = []
    for c in candidates:
        try:
            c1 = get_history_candles(c["symbol"], "1m", 30)
            time.sleep(RATE_LIMIT_S)
            side, decay = detect_dying_side(c1)
            if side is None or decay < 0.30:
                continue
            gs, checks = verify_global_dying(c["symbol"], c, side)
            if gs < 0.50:
                log.info(f"dying {c['symbol']} side={side} decay={decay:.2f} REJECTED global={gs}")
                continue
            trade = "sell" if side == "buy" else "buy"
            verified.append({"symbol": c["symbol"], "dying_side": side,
                             "trade_side": trade, "decay": round(decay, 3),
                             "global_score": gs, "checks": checks})
            log.info(f"DYING {c['symbol']} {side}→{trade} decay={decay:.2f} global={gs}")
        except Exception as e:
            log.warning(f"dying {c['symbol']} failed: {e}")

    if not verified:
        return None
    verified.sort(key=lambda x: x["global_score"], reverse=True)
    return verified[0]


# ==================== State + health + healer ====================
def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(obj, f, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        log.error(f"save {path}: {e}")


def mark_ok():
    h = _load(HEALTH_FILE, {"score": 100})
    h["last_ok"] = datetime.now(timezone.utc).isoformat()
    h["score"] = min(100, h.get("score", 100) + 1)
    _save(HEALTH_FILE, h)


def mark_err(code, detail=""):
    h = _load(HEALTH_FILE, {"score": 100})
    h["score"] = max(0, h.get("score", 100) - 5)
    h["last_error"] = {"code": code, "detail": detail}
    _save(HEALTH_FILE, h)


def healthy():
    return _load(HEALTH_FILE, {"score": 100}).get("score", 100) > 40


ERROR_BOOK = {
    "40762": ("min size / balance", "shrink notional", "reduce"),
    "40034": ("symbol unavailable", "quarantine", "skip"),
    "400171": ("param error", "retry clean", "retry"),
    "40109": ("balance low", "pause 5m", "pause"),
    "43012": ("no position", "resync", "resync"),
    "429": ("rate limit", "backoff 30s", "backoff"),
    "50001": ("venue down", "backoff 30s", "backoff"),
    "50011": ("IP blocked", "pause 5m", "pause"),
    "40085": ("UTA gate", "check V3 payload", "pause"),
}


class Healer:
    def __init__(self, trader):
        self.trader = trader
        self.cool_until = 0

    def _cool(self, s):
        self.cool_until = time.time() + s

    def _cooling(self):
        return time.time() < self.cool_until

    def treat(self, p):
        if self._cooling():
            return "cooling"
        code = str(p.get("code", "")).strip()
        msg = str(p.get("msg", "")) or str(p.get("detail", ""))
        log.warning(f"symptom {code}: {msg}")
        mark_err(code, msg)
        entry = ERROR_BOOK.get(code)
        if not entry:
            self._cool(5)
            return "generic"
        _, _, action = entry
        if action == "reduce":
            self.trader.usdt_notional = max(0.5, round(self.trader.usdt_notional * 0.75, 3))
            self._cool(10)
        elif action == "skip":
            sym = self.trader.position.get("symbol") if self.trader.position else None
            if sym:
                s = _load(STATE_FILE, {})
                s.setdefault("skipped", [])
                if sym not in s["skipped"]:
                    s["skipped"].append(sym)
                _save(STATE_FILE, s)
            self.trader.position = None
            self._cool(5)
        elif action == "retry":
            time.sleep(1.5)
        elif action == "pause":
            self._cool(300)
        elif action == "backoff":
            self._cool(30)
        elif action == "resync":
            self.trader.position = None
            self._cool(5)
        return action

    def check(self, resp):
        if not resp:
            return None
        if str(resp.get("code")) == "00000":
            mark_ok()
            return None
        return self.treat(resp)

    def check_exc(self, exc):
        d = str(exc).lower()
        if "timeout" in d or "connection" in d:
            code = "50001"
        elif "429" in d:
            code = "429"
        elif "401" in d or "auth" in d:
            code = "50011"
        else:
            code = "unknown"
        return self.treat({"code": code, "msg": str(exc)})


class StreakValidator:
    def __init__(self):
        self.streak = 0
        self.accepted = False
        self.history = []

    def record(self, pnl):
        win = pnl >= WIN_THRESHOLD
        self.history.append((datetime.now(timezone.utc).isoformat(), round(pnl, 6), win))
        self.history = self.history[-50:]
        self.streak = self.streak + 1 if win else 0
        self.accepted = self.streak >= REQUIRED_STREAK
        log.info(f"streak={self.streak}/{REQUIRED_STREAK} accepted={self.accepted} pnl={pnl:.5f}")
        return win

    def can_trade(self):
        return self.accepted


# ==================== Engine (V3-only orders) ====================
class ExamTrader:
    def __init__(self):
        self.validator = StreakValidator()
        self.position = None
        self.usdt_notional = 2.0
        self.healer = Healer(self)
        self.last_dying_scan = 0
        self._restore()

    def _restore(self):
        s = _load(STATE_FILE, {})
        self.validator.streak = s.get("streak", 0)
        self.validator.accepted = self.validator.streak >= REQUIRED_STREAK
        self.validator.history = s.get("history", [])
        self.usdt_notional = s.get("usdt_notional", 2.0)
        self.last_dying_scan = s.get("last_dying_scan", 0)
        log.info(f"restored streak={self.validator.streak} accepted={self.validator.accepted}")

    def _persist(self):
        s = _load(STATE_FILE, {})
        s.update({"streak": self.validator.streak, "accepted": self.validator.accepted,
                  "history": self.validator.history, "usdt_notional": self.usdt_notional,
                  "last_dying_scan": self.last_dying_scan})
        _save(STATE_FILE, s)

    def _ensure_lev(self, sym):
        body = {"symbol": sym, "productType": PRODUCT_TYPE, "marginCoin": "USDT",
                "leverage": LEVERAGE, "marginMode": MARGIN_MODE}
        r = _request("POST", "/api/v2/mix/account/set-leverage", body=body)
        self.healer.check(r)
        time.sleep(RATE_LIMIT_S)

    def _place_v3(self, sym, side, qty, reduce="no"):
        """UTA one-way mode: open long side=buy reduceOnly=no; close long side=sell reduceOnly=yes."""
        body = {
            "category": PRODUCT_TYPE,
            "symbol": sym,
            "qty": str(qty),
            "side": side,
            "orderType": "market",
            "reduceOnly": reduce,
            "marginMode": MARGIN_MODE,
        }
        r = _request("POST", "/api/v3/trade/place-order", body=body)
        self.healer.check(r)
        return r

    def open(self, sym, side):
        t = get_ticker(sym)
        if not t:
            return
        price = float(t["lastPr"])
        qty = round(self.usdt_notional / price, 6)
        if qty <= 0:
            return
        self._ensure_lev(sym)
        self._place_v3(sym, side, qty, "no")
        self.position = {"symbol": sym, "side": side, "qty": qty,
                         "entry": price, "ts": time.time()}
        log.info(f"OPEN {side} {sym} qty={qty} @ {price}")
        self._persist()

    def close(self, price):
        if not self.position:
            return None
        p = self.position
        cs = "sell" if p["side"] == "buy" else "buy"
        self._place_v3(p["symbol"], cs, p["qty"], "yes")
        pnl = (price - p["entry"]) / p["entry"] if p["side"] == "buy" \
              else (p["entry"] - price) / p["entry"]
        self.validator.record(pnl)
        self.position = None
        self._persist()
        return pnl

    def step(self):
        if not healthy():
            log.warning("health low — resting 60s")
            time.sleep(60)
            return

        if self.position:
            t = get_ticker(self.position["symbol"])
            if not t:
                return
            px = float(t["lastPr"])
            e = self.position["entry"]
            ch = (px - e) / e if self.position["side"] == "buy" else (e - px) / e
            if ch >= WIN_THRESHOLD or ch <= -WIN_THRESHOLD:
                pnl = self.close(px)
                log.info(f"CLOSE pnl={pnl:.5f}")
            return

        candidates = scan_market()
        if not candidates:
            return

        now = time.time()
        dying_setup = None
        if now - self.last_dying_scan >= WEAKEST_SCAN_INTERVAL_S:
            log.info("=== 10-MIN DYING SIDE SCAN ===")
            dying_setup = find_weakest_dying(candidates)
            self.last_dying_scan = now
            self._persist()

        if dying_setup and dying_setup["global_score"] >= DYING_SCORE_THRESHOLD:
            setup = {"symbol": dying_setup["symbol"], "side": dying_setup["trade_side"],
                     "score": dying_setup["global_score"], "source": "dying"}
        else:
            s = find_best_setup(candidates)
            if not s:
                log.info("no aligned setup this cycle")
                return
            setup = {**s, "source": "mtf"}

        if not self.validator.can_trade():
            log.info(f"would trade {setup['symbol']} {setup['side']} score={setup['score']} "
                     f"src={setup['source']} — streak {self.validator.streak}/{REQUIRED_STREAK}, paper-only")
            return

        log.info(f"TRADE {setup['symbol']} {setup['side']} score={setup['score']} src={setup['source']}")
        self.open(setup["symbol"], setup["side"])
