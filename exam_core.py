"""
exam_core.py — everything the bot needs:
  - Bitget UTA API client (signed, rate-limited, retried)
  - Global 4h volume estimator (Bitget-only)
  - 8-streak validator (>= 0.42% per trade)
  - Self-healing layer (diagnosis + medicine + health score)
  - State persistence (streak survives restarts)
  - Trading engine (paper/live, one-way, 5x isolated, reduceOnly closes)
"""

import os
import json
import time
import hmac
import hashlib
import base64
import logging
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

R_DEFAULT = 12.0
GLOBAL_4H_TARGET = 300_000
RATE_LIMIT_S = 0.25

STATE_FILE = os.environ.get("STATE_FILE", "state.json")
HEALTH_FILE = os.environ.get("HEALTH_FILE", "health.json")

# Injected at runtime via env R_BASE_MAP (JSON)
R_BASE_MAP = {}

# ==================== Logging ====================
log = logging.getLogger("exam")
log.setLevel(logging.INFO)
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    log.addHandler(h)


# ==================== API ====================
def _ts():
    return str(int(time.time() * 1000))


def _sign(timestamp, method, path, body_str=""):
    prehash = timestamp + method + path + body_str
    return base64.b64encode(
        hmac.new(SECRET_KEY.encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()


def _headers(timestamp, signature):
    h = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
    }
    if PAPER:
        h.update(DEMO_HEADER)
    return h


def _request(method, path, params=None, body=None):
    last_err = None
    for attempt in range(3):
        try:
            ts = _ts()
            body_str = json.dumps(body) if body else ""
            sig = _sign(ts, method, path, body_str)
            url = BASE_URL + path
            if method == "GET":
                resp = requests.get(url, params=params, headers=_headers(ts, sig), timeout=15)
            else:
                resp = requests.post(url, data=body_str, headers=_headers(ts, sig), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "00000":
                log.warning(f"API non-success: {data}")
            return data
        except Exception as e:
            last_err = e
            log.error(f"request {method} {path} attempt {attempt+1} failed: {e}")
            time.sleep(1.5)
    return {"code": "unknown", "msg": str(last_err) if last_err else "request_failed", "data": None}


# ==================== Market data ====================
def get_all_tickers():
    return _request("GET", "/api/v2/mix/market/tickers", params={"productType": PRODUCT_TYPE}).get("data", [])


def get_candles(symbol, granularity="4H", limit=2):
    params = {"symbol": symbol, "productType": PRODUCT_TYPE, "granularity": granularity, "limit": str(limit)}
    return _request("GET", "/api/v2/mix/market/candles", params=params).get("data", [])


def get_ticker(symbol):
    for t in get_all_tickers():
        if t.get("symbol") == symbol:
            return t
    return None


# ==================== Global estimator ====================
def estimate_global_4h_volume(symbol, ticker=None):
    candles = get_candles(symbol, "4H", limit=1)
    if not candles:
        return None
    try:
        bitget_4h = float(candles[0][6])
    except (IndexError, TypeError, ValueError):
        return None
    if bitget_4h <= 0:
        return None

    if ticker is None:
        ticker = get_ticker(symbol)
    if not ticker:
        return None

    last = float(ticker.get("lastPr", 0))
    index = float(ticker.get("indexPrice", last)) or last
    funding = float(ticker.get("fundingRate", 0))
    oi = float(ticker.get("holdingAmount", 0))

    basis_pct = abs(last - index) / index if index else 0
    basis_factor = 1.0 + min(basis_pct * 50, 0.3)
    funding_factor = 1.0 + min(abs(funding) * 200, 0.15)
    oi_ratio = (oi * last) / bitget_4h
    oi_factor = 1.0 + min(oi_ratio * 0.1, 0.1)

    r_base = R_BASE_MAP.get(symbol, R_DEFAULT)
    r_adj = r_base * basis_factor * funding_factor * oi_factor
    return bitget_4h * r_adj, {"bitget_4h": bitget_4h, "r_adj": r_adj}


def rank_candidates(min_bitget_4h=15_000):
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
        except (TypeError, ValueError):
            continue
        if qv / 6 < min_bitget_4h:
            continue
        coarse.append(t)

    log.info(f"coarse candidates: {len(coarse)}")

    scored = []
    for t in coarse:
        est = estimate_global_4h_volume(t["symbol"], ticker=t)
        if est is None:
            continue
        global_est, meta = est
        if global_est >= GLOBAL_4H_TARGET * 0.67:
            scored.append({"symbol": t["symbol"], "global_est": global_est, **meta})
        time.sleep(RATE_LIMIT_S)

    scored.sort(key=lambda x: x["global_est"], reverse=True)
    confident = [s for s in scored if s["global_est"] >= GLOBAL_4H_TARGET * 1.5]
    uncertain = [s for s in scored if GLOBAL_4H_TARGET * 0.67 <= s["global_est"] < GLOBAL_4H_TARGET * 1.5]
    log.info(f"confident={len(confident)} uncertain={len(uncertain)}")
    return confident + uncertain


# ==================== State + health ====================
def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"{path} load failed: {e}")
        return default


def _save_json(path, obj):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(obj, f, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        log.error(f"{path} save failed: {e}")


def mark_ok():
    h = _load_json(HEALTH_FILE, {"score": 100})
    h["last_ok_ts"] = datetime.now(timezone.utc).isoformat()
    h["score"] = min(100, h.get("score", 100) + 1)
    _save_json(HEALTH_FILE, h)


def mark_error(code, detail=""):
    h = _load_json(HEALTH_FILE, {"score": 100})
    h["score"] = max(0, h.get("score", 100) - 5)
    h["last_error"] = {"code": code, "detail": detail, "ts": datetime.now(timezone.utc).isoformat()}
    _save_json(HEALTH_FILE, h)


def is_healthy():
    return _load_json(HEALTH_FILE, {"score": 100}).get("score", 100) > 40


# ==================== Healer ====================
ERROR_BOOK = {
    "40762":   ("size below min or balance too small", "shrink notional 25%", "reduce_notional"),
    "40034":   ("symbol not tradable", "quarantine symbol", "skip_symbol"),
    "400171":  ("parameter error (posSide leak)", "retry clean", "retry"),
    "40109":   ("insufficient balance", "pause 5 min", "pause"),
    "43012":   ("no position to close", "resync local position", "resync"),
    "429":     ("rate limit", "backoff 30s", "backoff"),
    "50001":   ("exchange unavailable", "backoff 30s", "backoff"),
    "50011":   ("IP not whitelisted", "pause 5 min", "pause"),
    "30001":   ("order not found", "resync local position", "resync"),
}


class Healer:
    def __init__(self, trader):
        self.trader = trader
        self.cooldown_until = 0

    def _cool(self, seconds):
        self.cooldown_until = time.time() + seconds
        log.info(f"cooldown {seconds}s")

    def _in_cooldown(self):
        return time.time() < self.cooldown_until

    def treat(self, payload):
        if self._in_cooldown():
            return "cooldown"

        code = str(payload.get("code", "")).strip()
        msg = str(payload.get("msg", "")) or str(payload.get("detail", ""))
        log.warning(f"symptom code={code} msg={msg}")
        mark_error(code, msg)

        entry = ERROR_BOOK.get(code)
        if entry is None:
            log.info("unknown symptom — generic backoff 5s")
            self._cool(5)
            return "generic"

        diagnosis, medicine, action = entry
        log.info(f"diagnosis: {diagnosis} | medicine: {medicine}")

        if action == "reduce_notional":
            cur = self.trader.usdt_notional
            self.trader.usdt_notional = max(0.5, round(cur * 0.75, 3))
            log.info(f"usdt_notional {cur} -> {self.trader.usdt_notional}")
            self._cool(10)
        elif action == "skip_symbol":
            sym = self.trader.position.get("symbol") if self.trader.position else None
            if sym:
                s = _load_json(STATE_FILE, {})
                s.setdefault("skipped_symbols", [])
                if sym not in s["skipped_symbols"]:
                    s["skipped_symbols"].append(sym)
                _save_json(STATE_FILE, s)
                log.info(f"symbol quarantined: {sym}")
            self.trader.position = None
            self._cool(5)
        elif action == "retry":
            time.sleep(1.5)
        elif action == "pause":
            log.error("PAUSE — human needed")
            self._cool(300)
        elif action == "backoff":
            self._cool(30)
        elif action == "resync":
            self.trader.position = None
            self._cool(5)
        return action

    def check_response(self, resp):
        if not resp:
            return None
        code = str(resp.get("code", "00000"))
        if code == "00000":
            mark_ok()
            return None
        return self.treat(resp)

    def check_exception(self, exc):
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


# ==================== Streak validator ====================
class StreakValidator:
    def __init__(self):
        self.streak = 0
        self.accepted = False
        self.history = []

    def record(self, pnl_pct):
        win = pnl_pct >= WIN_THRESHOLD
        self.history.append((datetime.now(timezone.utc).isoformat(), round(pnl_pct, 6), win))
        self.history = self.history[-50:]
        if win:
            self.streak += 1
        else:
            self.streak = 0
            self.accepted = False
        if self.streak >= REQUIRED_STREAK:
            self.accepted = True
        log.info(f"streak={self.streak}/{REQUIRED_STREAK} accepted={self.accepted} pnl={pnl_pct:.5f}")
        return win

    def can_trade(self):
        return self.accepted


# ==================== Trading engine ====================
class ExamTrader:
    def __init__(self):
        self.validator = StreakValidator()
        self.position = None
        self.usdt_notional = 2.0
        self.healer = Healer(self)
        self._restore()

    def _restore(self):
        s = _load_json(STATE_FILE, {})
        self.validator.streak = s.get("streak", 0)
        self.validator.accepted = s.get("accepted", False)
        self.validator.history = s.get("history", [])
        self.usdt_notional = s.get("usdt_notional", 2.0)
        log.info(f"restored streak={self.validator.streak} accepted={self.validator.accepted}")

    def _persist(self):
        s = _load_json(STATE_FILE, {})
        s["streak"] = self.validator.streak
        s["accepted"] = self.validator.accepted
        s["history"] = self.validator.history
        s["usdt_notional"] = self.usdt_notional
        _save_json(STATE_FILE, s)

    def _ensure_leverage(self, symbol):
        body = {"symbol": symbol, "productType": PRODUCT_TYPE, "marginCoin": "USDT",
                "leverage": LEVERAGE, "marginMode": MARGIN_MODE}
        resp = _request("POST", "/api/v2/mix/account/set-leverage", body=body)
        self.healer.check_response(resp)
        time.sleep(RATE_LIMIT_S)

    def _place_order(self, symbol, side, qty, reduce_only="no"):
        body = {
            "symbol": symbol, "productType": PRODUCT_TYPE, "marginMode": MARGIN_MODE,
            "marginCoin": "USDT", "size": str(qty), "side": side, "orderType": "market",
            "reduceOnly": "YES" if reduce_only == "yes" else "NO",
            "clientOid": f"exam{int(time.time()*1000)}",
        }
        resp = _request("POST", "/api/v2/mix/order/place-order", body=body)
        log.info(f"order resp: {resp}")
        self.healer.check_response(resp)
        return resp

    def open_position(self, symbol, side):
        ticker = get_ticker(symbol)
        if not ticker:
            return None
        price = float(ticker["lastPr"])
        qty = round(self.usdt_notional / price, 6)
        if qty <= 0:
            return None
        self._ensure_leverage(symbol)
        self._place_order(symbol, side, qty, reduce_only="no")
        self.position = {"symbol": symbol, "side": side, "qty": qty, "entry": price, "opened_at": time.time()}
        log.info(f"OPENED {side} {symbol} qty={qty} @ {price}")
        self._persist()

    def close_position(self, current_price):
        if not self.position:
            return None
        sym = self.position["symbol"]
        close_side = "sell" if self.position["side"] == "buy" else "buy"
        self._place_order(sym, close_side, self.position["qty"], reduce_only="yes")
        entry = self.position["entry"]
        pnl = (current_price - entry) / entry if self.position["side"] == "buy" else (entry - current_price) / entry
        self.validator.record(pnl)
        self.position = None
        self._persist()
        return pnl

    def step(self):
        if not is_healthy():
            log.warning("health low — resting 60s")
            time.sleep(60)
            return

        if self.position:
            ticker = get_ticker(self.position["symbol"])
            if not ticker:
                return
            price = float(ticker["lastPr"])
            entry = self.position["entry"]
            ch = (price - entry) / entry if self.position["side"] == "buy" else (entry - price) / entry
            if ch >= WIN_THRESHOLD or ch <= -WIN_THRESHOLD:
                pnl = self.close_position(price)
                log.info(f"CLOSED pnl={pnl:.5f}")
            return

        if not self.validator.can_trade():
            log.info("streak not accepted — scanning only")
            rank_candidates()  # keeps estimator warm, logs candidates
            return

        cands = rank_candidates()
        if not cands:
            return
        target = cands[0]
        log.info(f"top candidate: {target['symbol']} est_global_4h={target['global_est']:.0f}")
        self.open_position(target["symbol"], "buy")
