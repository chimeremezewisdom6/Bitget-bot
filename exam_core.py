"""
exam_core.py — full setup:
  - Scans all USDT-FUTURES for 4h volume >= 300k (Bitget approximation)
  - Deep 24h behaviour scan: 1m candle patterns, order-book imbalance,
    taker CVD exhaustion, whale-sell footprint, basis convergence
  - Only trades when every condition aligns
  - 8-streak gate, healer, paper/live switch, UTA-ready
"""

import os, json, time, hmac, hashlib, base64, logging
from datetime import datetime, timezone
from collections import defaultdict

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

GLOBAL_4H_TARGET = 300_000
MIN_BITGET_4H = 15_000
R_DEFAULT = 12.0
RATE_LIMIT_S = 0.25

# Deep-scan thresholds (tunable)
MIN_CANDLE_MATCH = 0.60        # 60% of last 10 candles same colour
MIN_ORDERBOOK_RATIO = 1.8      # bid/ask or ask/bid >= 1.8
MIN_CVD_DIVERGENCE = 0.15      # |CVD|/total >= 15% divergence
MIN_WHALE_SELL_COUNT = 2       # at least 2 large sell fills
BASIS_CONVERGE_THRESHOLD = 0.0015  # 0.15% gap counts as converged

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
                r = requests.get(url, params=params, headers=_headers(ts, sig), timeout=15)
            else:
                r = requests.post(url, data=body_str, headers=_headers(ts, sig), timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "00000":
                log.warning(f"API non-success: {data}")
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


# ==================== 24h candle fetcher ====================
def fetch_24h_1m(symbol):
    """Paginate 1m candles backwards until 24h collected (max 1440)."""
    all_c = []
    end = None
    for _ in range(8):  # 8 × 200 = 1600 max
        batch = get_history_candles(symbol, "1m", 200, end_time=end)
        if not batch:
            break
        all_c.extend(batch)
        end = int(batch[0][0]) - 1
        if len(all_c) >= 1440:
            break
        time.sleep(RATE_LIMIT_S)
    return all_c[:1440]


# ==================== Analysis helpers ====================
def candle_pattern_score(candles):
    """Return (score, pattern_name, direction). Last 10 candles."""
    if len(candles) < 10:
        return 0.0, "short", None
    last10 = candles[-10:]
    greens = 0
    for c in last10:
        try:
            o, cl = float(c[1]), float(c[4])
        except (ValueError, IndexError):
            continue
        if cl > o:
            greens += 1
    ratio = greens / 10.0
    if ratio >= 0.8:
        return ratio, "9g1r_or_more", "buy"
    if ratio <= 0.2:
        return (1 - ratio), "9r1g_or_more", "sell"
    return ratio, "mixed", None


def forward_continuation(candles):
    """
    Find all 9g1r-like windows in 24h and measure next 10m green ratio.
    Returns (avg_next_ratio, sample_count).
    """
    wins, outcomes = 0, []
    for i in range(10, len(candles) - 10):
        window = candles[i-10:i]
        g = sum(1 for c in window if float(c[4]) > float(c[1]))
        if g >= 9:
            nxt = candles[i:i+10]
            if len(nxt) < 10:
                continue
            ng = sum(1 for c in nxt if float(c[4]) > float(c[1]))
            outcomes.append(ng / 10.0)
    if not outcomes:
        return 0.0, 0
    return sum(outcomes) / len(outcomes), len(outcomes)


def orderbook_imbalance(ob):
    """Return (ratio, tightness, side). Higher ratio = one side much deeper."""
    try:
        bids = ob.get("bids", [])
        asks = ob.get("asks", [])
        if not bids or not asks:
            return 0.0, 0.0, None
        bid_vol = sum(float(b[1]) for b in bids[:20])
        ask_vol = sum(float(a[1]) for a in asks[:20])
        if ask_vol <= 0 or bid_vol <= 0:
            return 0.0, 0.0, None
        if bid_vol > ask_vol:
            return bid_vol / ask_vol, min(bid_vol, ask_vol) / max(bid_vol, ask_vol), "bid"
        return ask_vol / bid_vol, min(bid_vol, ask_vol) / max(bid_vol, ask_vol), "ask"
    except Exception:
        return 0.0, 0.0, None


def cvd_from_fills(fills):
    """Return (cvd_pct, buy_vol, sell_vol, whale_sells)."""
    buy = sell = 0.0
    sizes = []
    whale = 0
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
    if sizes:
        cutoff = sorted(sizes)[int(len(sizes) * 0.9)]
        whale = sum(1 for f in fills
                    if f.get("side") == "sell" and float(f.get("size", 0)) >= cutoff)
    return (buy - sell) / total, buy, sell, whale


def basis_snapshot(ticker):
    """Return (basis_pct, direction) of last vs index."""
    try:
        last = float(ticker.get("lastPr", 0))
        idx = float(ticker.get("indexPrice", last)) or last
        b = (last - idx) / idx
        return abs(b), ("premium" if b > 0 else "discount")
    except Exception:
        return 0.0, None


# ==================== Deep setup detector ====================
def detect_setup(symbol, ticker):
    """
    Returns dict with score + details if setup passes all filters, else None.
    """
    candles = fetch_24h_1m(symbol)
    if len(candles) < 30:
        return None

    c_score, c_name, c_dir = candle_pattern_score(candles)
    if c_score < MIN_CANDLE_MATCH or c_dir is None:
        return None

    cont_ratio, cont_samples = forward_continuation(candles)
    if cont_samples < 3 or cont_ratio < 0.65:
        return None  # not enough historical continuation

    ob = get_orderbook(symbol, 50)
    ob_ratio, tightness, ob_side = orderbook_imbalance(ob)
    if ob_ratio < MIN_ORDERBOOK_RATIO:
        return None
    if tightness < 0.35:
        return None  # book too balanced

    fills = get_recent_fills(symbol, 100)
    cvd, bvol, svol, whales = cvd_from_fills(fills)
    if abs(cvd) < MIN_CVD_DIVERGENCE:
        return None
    if whales < MIN_WHALE_SELL_COUNT:
        return None

    basis_pct, basis_dir = basis_snapshot(ticker)
    if basis_pct > BASIS_CONVERGE_THRESHOLD:
        return None  # not converged enough

    # Direction: if crowd is long (funding positive) and price failing -> sell
    funding = float(ticker.get("fundingRate", 0))
    crowd_side = "long" if funding > 0 else "short"
    trade_side = "sell" if crowd_side == "long" else "buy"

    # Confirm disagreement: pattern direction vs crowd
    if crowd_side == "long" and c_dir != "sell":
        return None
    if crowd_side == "short" and c_dir != "buy":
        return None

    score = (c_score * 0.25 + (1 - abs(cvd)) * 0.15 +
             (ob_ratio / 3.0) * 0.25 + (1 - basis_pct) * 0.15 +
             min(whales / 5.0, 1.0) * 0.10 + cont_ratio * 0.10)

    return {
        "symbol": symbol,
        "side": trade_side,
        "score": round(score, 4),
        "candle_pattern": c_name,
        "ob_ratio": round(ob_ratio, 2),
        "tightness": round(tightness, 2),
        "cvd": round(cvd, 4),
        "whale_sells": whales,
        "basis_pct": round(basis_pct, 6),
        "cont_ratio": round(cont_ratio, 3),
        "cont_samples": cont_samples,
        "funding": funding,
    }


# ==================== Market scanner ====================
def scan_market(top_n=25):
    """
    1. All tickers -> filter 4h volume >= MIN_BITGET_4H (approx via 24h/6)
    2. Estimate global 4h >= 300k
    3. Sort by estimated global volume, return top_n
    """
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
        global_est = bitget_4h * r
        if global_est >= GLOBAL_4H_TARGET * 0.67:
            scored.append({**t, "_global_est": global_est})
        time.sleep(RATE_LIMIT_S * 0.5)

    scored.sort(key=lambda x: x["_global_est"], reverse=True)
    log.info(f"volume-qualified: {len(scored)} — returning top {top_n}")
    return scored[:top_n]


def find_best_setup():
    """Run deep scan on top liquid candidates, return highest-scoring setup."""
    candidates = scan_market(top_n=25)
    if not candidates:
        return None
    results = []
    for c in candidates:
        sym = c["symbol"]
        try:
            s = detect_setup(sym, c)
            if s:
                results.append(s)
                log.info(f"SETUP {sym} score={s['score']} side={s['side']} "
                         f"pattern={s['candle_pattern']} ob={s['ob_ratio']} "
                         f"cvd={s['cvd']} whales={s['whale_sells']}")
        except Exception as e:
            log.warning(f"deep scan {sym} failed: {e}")
        time.sleep(RATE_LIMIT_S)
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
    "40762": ("min size / balance", "shrink notional", "reduce"),
    "40034": ("symbol unavailable", "quarantine", "skip"),
    "400171": ("param error", "retry clean", "retry"),
    "40109": ("balance low", "pause 5m", "pause"),
    "43012": ("no position", "resync", "resync"),
    "429": ("rate limit", "backoff 30s", "backoff"),
    "50001": ("venue down", "backoff 30s", "backoff"),
    "50011": ("IP blocked", "pause 5m", "pause"),
    "40085": ("UTA gate — use v3", "switch endpoints", "pause"),
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
        e = ERROR_BOOK.get(code)
        if not e:
            self._cool(5)
            return "generic"
        _, _, action = e
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
        code = "50001" if ("timeout" in d or "connection" in d) else \
               "429" if "429" in d else \
               "50011" if ("401" in d or "auth" in d) else "unknown"
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
        self._restore()

    def _restore(self):
        s = _load(STATE_FILE, {})
        self.validator.streak = s.get("streak", 0)
        self.validator.accepted = s.get("accepted", False)
        self.validator.history = s.get("history", [])
        self.usdt_notional = s.get("usdt_notional", 2.0)

    def _persist(self):
        s = _load(STATE_FILE, {})
        s.update({"streak": self.validator.streak, "accepted": self.validator.accepted,
                  "history": self.validator.history, "usdt_notional": self.usdt_notional})
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
                    "orderType": "market", "reduceOnly": "YES" if reduce == "yes" else "NO",
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
        self.position = {"symbol": sym, "side": side, "qty": qty, "entry": price, "ts": time.time()}
        log.info(f"OPEN {side} {sym} qty={qty} @ {price}")
        self._persist()

    def close(self, price):
        if not self.position:
            return None
        p = self.position
        cs = "sell" if p["side"] == "buy" else "buy"
        self._place(p["symbol"], cs, p["qty"], "yes")
        pnl = (price - p["entry"]) / p["entry"] if p["side"] == "buy" else (p["entry"] - price) / p["entry"]
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

        if not self.validator.can_trade():
            log.info("streak not accepted — scanning only")
            find_best_setup()
            return

        setup = find_best_setup()
        if not setup:
            log.info("no aligned setup this cycle")
            return

        log.info(f"TRADE {setup['symbol']} {setup['side']} score={setup['score']}")
        self.open(setup["symbol"], setup["side"])
