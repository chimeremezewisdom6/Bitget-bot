"""
exam_core.py — full setup v4:
  - Threshold now $200k global 4h (was $300k)
  - Every 10 minutes: scan for the weakest dying side across market,
    verify it against global information using our method
    (basis convergence, funding crowd, index velocity, orderbook imbalance)
  - Regular cycle: 1m/3m/5m multi-timeframe setup detection
  - 8-streak gate, healer, paper/live switch, state persistence
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
USE_V3_ORDERS = os.environ.get("USE_V3_ORDERS", "false").lower() == "true"

WIN_THRESHOLD = 0.0042
REQUIRED_STREAK = 8

GLOBAL_4H_TARGET = 200_000        # changed: was 300k
MIN_BITGET_4H = 10_000
R_DEFAULT = 12.0
RATE_LIMIT_S = 0.20

SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.55"))
DYING_SCORE_THRESHOLD = float(os.environ.get("DYING_SCORE_THRESHOLD", "0.60"))
TOP_N_CANDIDATES = int(os.environ.get("TOP_N_CANDIDATES", "20"))

WEAKEST_SCAN_INTERVAL_S = 600     # 10 minutes
WIN_1M = 10
WIN_3M = 6
WIN_5M = 4

STATE_FILE = os.environ.get("STATE_FILE", "state.json")
HEALTH_FILE = os.environ.get("HEALTH_FILE", "health.json")
R_BASE_MAP = {}

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


# ==================== Multi-timeframe fetch ====================
def fetch_multi_tf(symbol):
    out = {}
    out["1m"] = get_history_candles(symbol, "1m", 200)
    time.sleep(RATE_LIMIT_S)
    out["3m"] = get_history_candles(symbol, "3m", 200)
    time.sleep(RATE_LIMIT_S)
    hist5, end = [], None
    for _ in range(2):
        batch = get_history_candles(symbol, "5m", 200, end_time=end)
        if not batch:
            break
        hist5.extend(batch)
        end = int(batch[0][0]) - 1
        if len(hist5) >= 288:
            break
        time.sleep(RATE_LIMIT_S)
    out["5m"] = hist5[:288]
    return out


# ==================== Candle analysis ====================
def candle_pattern(candles, window, label):
    if len(candles) < window:
        return 0.0, f"{label}_short", None
    last = candles[-window:]
    greens = 0
    for c in last:
        try:
            o, cl = float(c[1]), float(c[4])
        except (ValueError, IndexError):
            continue
        if cl > o:
            greens += 1
    ratio = greens / window
    if ratio >= 0.8:
        return ratio, f"{label}_up", "buy"
    if ratio <= 0.2:
        return (1 - ratio), f"{label}_down", "sell"
    return abs(ratio - 0.5) * 2, f"{label}_mixed", None


def detect_dying_side(candles_1m):
    """
    Look at the SEQUENCE of last 20 one-minute candles.
    Compare fuel (move × volume) of green candles vs red candles
    in the last 10 vs the 10 before.
    Whichever side lost more fuel is the dying side.
    Returns (dying_side, decay_score) where dying_side is "buy"|"sell"|None.
    """
    if len(candles_1m) < 20:
        return None, 0.0

    recent = candles_1m[-10:]
    earlier = candles_1m[-20:-10]

    def side_fuel(bars, want_green):
        fuel = 0.0
        for c in bars:
            try:
                o, cl, vol = float(c[1]), float(c[4]), float(c[5])
            except (ValueError, IndexError):
                continue
            if want_green and cl > o:
                fuel += (cl - o) * vol
            elif not want_green and cl < o:
                fuel += (o - cl) * vol
        return fuel

    rg = side_fuel(recent, True)
    rr = side_fuel(recent, False)
    eg = side_fuel(earlier, True)
    er = side_fuel(earlier, False)

    def decay(recent_fuel, earlier_fuel):
        if earlier_fuel <= 0:
            return 0.0
        return max(-1.0, min(1.0, (earlier_fuel - recent_fuel) / earlier_fuel))

    green_decay = decay(rg, eg)
    red_decay = decay(rr, er)

    if green_decay > red_decay and green_decay > 0.25:
        return "buy", green_decay     # buy side dying → we trade sell
    if red_decay > green_decay and red_decay > 0.25:
        return "sell", red_decay      # sell side dying → we trade buy
    return None, max(green_decay, red_decay)


def forward_continuation_1m(candles_1m):
    if len(candles_1m) < WIN_1M * 2:
        return 0.0, 0
    outcomes = []
    for i in range(WIN_1M, len(candles_1m) - WIN_1M):
        w = candles_1m[i-WIN_1M:i]
        try:
            g = sum(1 for c in w if float(c[4]) > float(c[1]))
        except (ValueError, IndexError):
            continue
        if g >= 8:
            nxt = candles_1m[i:i+WIN_1M]
            try:
                ng = sum(1 for c in nxt if float(c[4]) > float(c[1]))
            except (ValueError, IndexError):
                continue
            outcomes.append(ng / WIN_1M)
        elif g <= 2:
            nxt = candles_1m[i:i+WIN_1M]
            try:
                nr = sum(1 for c in nxt if float(c[4]) < float(c[1]))
            except (ValueError, IndexError):
                continue
            outcomes.append(nr / WIN_1M)
    if not outcomes:
        return 0.0, 0
    return sum(outcomes) / len(outcomes), len(outcomes)


def three_min_after_1m(candles_1m):
    if len(candles_1m) < WIN_1M + 3:
        return 0.0, 0
    outcomes = []
    for i in range(WIN_1M, len(candles_1m) - 3):
        w = candles_1m[i-WIN_1M:i]
        try:
            g = sum(1 for c in w if float(c[4]) > float(c[1]))
        except (ValueError, IndexError):
            continue
        if g >= 8:
            nxt = candles_1m[i:i+3]
            try:
                ng = sum(1 for c in nxt if float(c[4]) > float(c[1]))
            except (ValueError, IndexError):
                continue
            outcomes.append(ng / 3.0)
        elif g <= 2:
            nxt = candles_1m[i:i+3]
            try:
                nr = sum(1 for c in nxt if float(c[4]) < float(c[1]))
            except (ValueError, IndexError):
                continue
            outcomes.append(nr / 3.0)
    if not outcomes:
        return 0.0, 0
    return sum(outcomes) / len(outcomes), len(outcomes)


def orderbook_imbalance(ob):
    try:
        bids = ob.get("bids", [])
        asks = ob.get("asks", [])
        if not bids or not asks:
            return 0.0, 0.0, None
        bid_vol = sum(float(b[1]) for b in bids[:20])
        ask_vol = sum(float(a[1]) for a in asks[:20])
        if ask_vol <= 0 or bid_vol <= 0:
            return 0.0, 0.0, None
        tight = min(bid_vol, ask_vol) / max(bid_vol, ask_vol)
        if bid_vol > ask_vol:
            return bid_vol / ask_vol, tight, "bid"
        return ask_vol / bid_vol, tight, "ask"
    except Exception:
        return 0.0, 0.0, None


def cvd_from_fills(fills):
    buy = sell = 0.0
    sizes = []
    for f in fills:
        try:
            sz = float(f["size"])
            side = f["side"].lower()
        except (KeyError, ValueError):
            continue
        sizes.append(sz)
        if side == "buy":
            buy += sz
        else:
            sell += sz
    total = buy + sell
    if total <= 0:
        return 0.0, 0.0, 0.0, 0
    cutoff = sorted(sizes)[int(len(sizes) * 0.9)] if sizes else 0
    whale_sells = 0
    for f in fills:
        try:
            if f.get("side") == "sell" and float(f.get("size", 0)) >= cutoff:
                whale_sells += 1
        except (ValueError, TypeError):
            continue
    return (buy - sell) / total, buy, sell, whale_sells


def basis_snapshot(ticker):
    try:
        last = float(ticker.get("lastPr", 0))
        idx = float(ticker.get("indexPrice", last)) or last
        b = (last - idx) / idx
        return abs(b), ("premium" if b > 0 else "discount"), (last - idx) / idx
    except Exception:
        return 0.0, None, 0.0


# ==================== GLOBAL VERIFICATION ====================
def verify_global_dying(symbol, ticker, dying_side):
    """
    Use Bitget-only global method to confirm the local dying side is real globally:
      1. Basis convergence toward the dying side (arbitrage flow agreeing)
      2. Funding crowd is on the dying side (they are trapped)
      3. Index velocity favors the winning side over the last 10 min
      4. Order book imbalance on the winning side
      5. CVD agrees
    Returns dict of confirmations + a confidence score 0-1.
    """
    checks = {}
    score = 0.0

    # 1. Basis
    basis_pct, basis_dir, basis_signed = basis_snapshot(ticker)
    # If buy side dying → we want basis to be negative or converging to negative (global sell pressure)
    want_dir = "discount" if dying_side == "buy" else "premium"
    if basis_dir == want_dir:
        checks["basis"] = 1.0
        score += 0.25
    elif basis_pct < 0.0008:  # converged near neutral, acceptable
        checks["basis"] = 0.5
        score += 0.12
    else:
        checks["basis"] = 0.0

    # 2. Funding crowd
    funding = float(ticker.get("fundingRate", 0))
    crowd = "long" if funding > 0 else "short"
    want_crowd = "long" if dying_side == "buy" else "short"
    if crowd == want_crowd and abs(funding) > 0.00005:
        checks["crowd"] = 1.0
        score += 0.25
    else:
        checks["crowd"] = 0.0

    # 3. Index velocity over last 10 min (approximate via 1m candles vs index)
    candles = get_history_candles(symbol, "1m", 15)
    time.sleep(RATE_LIMIT_S)
    idx_velocity_ok = False
    if len(candles) >= 10:
        try:
            first_close = float(candles[0][4])
            last_close = float(candles[-1][4])
            bitget_move = (last_close - first_close) / first_close
            # If buy dying → Bitget price should be flat/down. If sell dying → flat/up.
            if dying_side == "buy" and bitget_move <= 0.001:
                idx_velocity_ok = True
            elif dying_side == "sell" and bitget_move >= -0.001:
                idx_velocity_ok = True
        except (ValueError, IndexError):
            pass
    if idx_velocity_ok:
        checks["index_velocity"] = 1.0
        score += 0.20
    else:
        checks["index_velocity"] = 0.0

    # 4. Order book
    ob_ratio, tightness, ob_side = orderbook_imbalance(get_orderbook(symbol, 50))
    time.sleep(RATE_LIMIT_S)
    want_ob_side = "ask" if dying_side == "buy" else "bid"  # asks heavy = sellers, bids heavy = buyers winning
    if ob_side == want_ob_side and ob_ratio >= 1.5:
        checks["orderbook"] = min(ob_ratio / 2.5, 1.0)
        score += 0.15 * checks["orderbook"]
    else:
        checks["orderbook"] = 0.0

    # 5. CVD
    cvd, _, _, whales = cvd_from_fills(get_recent_fills(symbol, 100))
    time.sleep(RATE_LIMIT_S)
    want_cvd_neg = dying_side == "buy"
    if (want_cvd_neg and cvd < -0.10) or (not want_cvd_neg and cvd > 0.10):
        checks["cvd"] = min(abs(cvd) / 0.30, 1.0)
        score += 0.15 * checks["cvd"]
    else:
        checks["cvd"] = 0.0

    return {
        "score": round(score, 4),
        "checks": checks,
        "basis_pct": round(basis_pct, 6),
        "funding": funding,
        "crowd": crowd,
        "cvd": round(cvd, 4),
        "whales": whales,
        "ob_ratio": round(ob_ratio, 2),
    }


# ==================== DYING SIDE SCAN (every 10 min) ====================
def find_weakest_dying_setup(candidates):
    """
    For each candidate, detect dying side from candle sequence.
    If found, verify with global method.
    Return the strongest VERIFIED dying-side setup.
    """
    verified = []
    for c in candidates:
        sym = c["symbol"]
        try:
            c1 = get_history_candles(sym, "1m", 30)
            time.sleep(RATE_LIMIT_S)
            dying_side, decay = detect_dying_side(c1)
            if dying_side is None or decay < 0.30:
                continue
            confirm = verify_global_dying(sym, c, dying_side)
            if confirm["score"] < 0.50:
                log.info(
                    f"dying {sym} side={dying_side} decay={decay:.2f} "
                    f"REJECTED global_score={confirm['score']}"
                )
                continue
            trade_side = "sell" if dying_side == "buy" else "buy"
            verified.append({
                "symbol": sym,
                "dying_side": dying_side,
                "trade_side": trade_side,
                "decay": round(decay, 3),
                "global_score": confirm["score"],
                "checks": confirm["checks"],
                "basis_pct": confirm["basis_pct"],
                "funding": confirm["funding"],
                "cvd": confirm["cvd"],
            })
            log.info(
                f"DYING {sym} side={dying_side}→trade={trade_side} "
                f"decay={decay:.2f} global={confirm['score']} "
                f"checks={confirm['checks']}"
            )
        except Exception as e:
            log.warning(f"dying scan {sym} failed: {e}")

    if not verified:
        log.info("weakest dying scan: none confirmed")
        return None
    verified.sort(key=lambda x: x["global_score"], reverse=True)
    log.info(f"weakest dying winner: {verified[0]['symbol']} {verified[0]['trade_side']} global={verified[0]['global_score']}")
    return verified[0]


# ==================== Regular MTF setup ====================
def detect_setup(symbol, ticker):
    tfs = fetch_multi_tf(symbol)
    c1, c3, c5 = tfs["1m"], tfs["3m"], tfs["5m"]
    if len(c1) < WIN_1M or len(c3) < WIN_3M or len(c5) < WIN_5M:
        return None

    s1, n1, d1 = candle_pattern(c1, WIN_1M, "1m")
    if d1 is None:
        return None
    s3, n3, d3 = candle_pattern(c3, WIN_3M, "3m")
    s5, n5, d5 = candle_pattern(c5, WIN_5M, "5m")
    if d3 is not None and d3 != d1:
        return None
    if d5 is not None and d5 != d1:
        return None

    cont_ratio, cont_samples = forward_continuation_1m(c1)
    three_ratio, three_samples = three_min_after_1m(c1)
    ob_ratio, tightness, _ = orderbook_imbalance(get_orderbook(symbol, 50))
    time.sleep(RATE_LIMIT_S)
    cvd, _, _, whales = cvd_from_fills(get_recent_fills(symbol, 100))
    time.sleep(RATE_LIMIT_S)
    basis_pct, _, _ = basis_snapshot(ticker)

    funding = float(ticker.get("fundingRate", 0))
    crowd = "long" if funding > 0 else "short"
    if crowd == "long" and d1 != "sell":
        return None
    if crowd == "short" and d1 != "buy":
        return None

    score = (
        s1 * 0.22 + (s3 if d3 == d1 else 0.0) * 0.10 + (s5 if d5 == d1 else 0.0) * 0.08 +
        min(ob_ratio / 2.5, 1.0) * 0.15 + min(abs(cvd) / 0.30, 1.0) * 0.12 +
        min(whales / 4.0, 1.0) * 0.08 + (1 - min(basis_pct / 0.005, 1.0)) * 0.08 +
        min(cont_ratio, 1.0) * 0.09 + min(three_ratio, 1.0) * 0.08
    )
    if score < SCORE_THRESHOLD:
        return None

    return {
        "symbol": symbol, "side": "sell" if crowd == "long" else "buy",
        "score": round(score, 4), "p1m": n1, "p3m": n3, "p5m": n5,
        "ob_ratio": round(ob_ratio, 2), "tightness": round(tightness, 2),
        "cvd": round(cvd, 4), "whales": whales, "basis_pct": round(basis_pct, 6),
        "cont_10m": round(cont_ratio, 3), "cont_10m_n": cont_samples,
        "three_min": round(three_ratio, 3), "three_min_n": three_samples,
        "funding": funding, "crowd": crowd,
    }


# ==================== Scanner ====================
def scan_market(top_n=TOP_N_CANDIDATES):
    tickers = get_all_tickers()
    if not tickers:
        return []
    coarse = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        try:
            qv = float(t.get("quoteVolume", 0))
        except (ValueError, TypeError):
            continue
        if qv / 6 < MIN_BITGET_4H:
            continue
        coarse.append(t)
    log.info(f"coarse liquid symbols: {len(coarse)}")

    scored = []
    for t in coarse:
        try:
            bitget_4h = float(t.get("quoteVolume", 0)) / 6
        except (ValueError, TypeError):
            continue
        r = R_BASE_MAP.get(t["symbol"], R_DEFAULT)
        ge = bitget_4h * r
        if ge >= GLOBAL_4H_TARGET * 0.67:      # 200k * 0.67 = 134k uncertain floor
            scored.append({**t, "_global_est": ge})
    scored.sort(key=lambda x: x["_global_est"], reverse=True)
    log.info(f"volume-qualified (>≈$200k global 4h): {len(scored)} — top {top_n}")
    return scored[:top_n]


def find_best_setup(candidates):
    t0 = time.time()
    results = []
    for c in candidates:
        try:
            s = detect_setup(c["symbol"], c)
            if s:
                results.append(s)
                log.info(
                    f"SETUP {s['symbol']} score={s['score']} side={s['side']} "
                    f"1m={s['p1m']} 3m={s['p3m']} 5m={s['p5m']}"
                )
        except Exception as e:
            log.warning(f"deep scan {c['symbol']} failed: {e}")
    log.info(f"scan cycle: {len(candidates)} symbols in {time.time()-t0:.1f}s")
    if not results:
        return None
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[0]


# ==================== State + health ====================
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


# ==================== Healer ====================
ERROR_BOOK = {
    "40762":   ("min size / balance", "shrink notional", "reduce"),
    "40034":   ("symbol unavailable", "quarantine", "skip"),
    "400171":  ("param error", "retry clean", "retry"),
    "40109":   ("balance low", "pause 5m", "pause"),
    "43012":   ("no position", "resync", "resync"),
    "429":     ("rate limit", "backoff 30s", "backoff"),
    "50001":   ("venue down", "backoff 30s", "backoff"),
    "50011":   ("IP blocked", "pause 5m", "pause"),
    "40085":   ("UTA gate", "set USE_V3_ORDERS=true", "pause"),
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


# ==================== Streak ====================
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


# ==================== Engine ====================
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
        log.info(
            f"restored streak={self.validator.streak} "
            f"accepted={self.validator.accepted} "
            f"notional={self.usdt_notional}"
        )

    def _persist(self):
        s = _load(STATE_FILE, {})
        s.update({
            "streak": self.validator.streak,
            "accepted": self.validator.accepted,
            "history": self.validator.history,
            "usdt_notional": self.usdt_notional,
            "last_dying_scan": self.last_dying_scan,
        })
        _save(STATE_FILE, s)

    def _order_path(self):
        return "/api/v3/trade/place-order" if USE_V3_ORDERS else "/api/v2/mix/order/place-order"

    def _ensure_lev(self, sym):
        body = {"symbol": sym, "productType": PRODUCT_TYPE, "marginCoin": "USDT",
                "leverage": LEVERAGE, "marginMode": MARGIN_MODE}
        r = _request("POST", "/api/v2/mix/account/set-leverage", body=body)
        self.healer.check(r)
        time.sleep(RATE_LIMIT_S)

    def _place(self, sym, side, qty, reduce="no"):
        if USE_V3_ORDERS:
            body = {"category": PRODUCT_TYPE, "symbol": sym, "qty": str(qty),
                    "side": side, "orderType": "market",
                    "reduceOnly": reduce, "marginMode": MARGIN_MODE}
        else:
            body = {"symbol": sym, "productType": PRODUCT_TYPE, "marginMode": MARGIN_MODE,
                    "marginCoin": "USDT", "size": str(qty), "side": side,
                    "orderType": "market",
                    "reduceOnly": "YES" if reduce == "yes" else "NO",
                    "clientOid": f"ex{int(time.time()*1000)}"}
        r = _request("POST", self._order_path(), body=body)
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
        self._place(sym, side, qty, "no")
        self.position = {"symbol": sym, "side": side, "qty": qty,
                         "entry": price, "ts": time.time()}
        log.info(f"OPEN {side} {sym} qty={qty} @ {price}")
        self._persist()

    def close(self, price):
        if not self.position:
            return None
        p = self.position
        cs = "sell" if p["side"] == "buy" else "buy"
        self._place(p["symbol"], cs, p["qty"], "yes")
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

        # Manage open position first
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

        # === 10-minute dying-side scan ===
        now = time.time()
        dying_setup = None
        if now - self.last_dying_scan >= WEAKEST_SCAN_INTERVAL_S:
            log.info("=== 10-MIN WEAKEST DYING SIDE SCAN ===")
            dying_setup = find_weakest_dying_setup(candidates)
            self.last_dying_scan = now
            self._persist()

        # Dying setup takes priority if confirmed
        if dying_setup and dying_setup["global_score"] >= DYING_SCORE_THRESHOLD:
            setup = {
                "symbol": dying_setup["symbol"],
                "side": dying_setup["trade_side"],
                "score": dying_setup["global_score"],
                "source": "dying_global",
            }
        else:
            s = find_best_setup(candidates)
            if not s:
                log.info("no aligned setup this cycle")
                return
            setup = {**s, "source": "mtf"}

        if not self.validator.can_trade():
            log.info(
                f"would trade {setup['symbol']} {setup['side']} "
                f"score={setup['score']} src={setup['source']} — "
                f"streak {self.validator.streak}/{REQUIRED_STREAK}, paper-only"
            )
            return

        log.info(
            f"TRADE {setup['symbol']} {setup['side']} "
            f"score={setup['score']} src={setup['source']}"
        )
        self.open(setup["symbol"], setup["side"])
