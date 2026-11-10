"""
exam_core.py — Production-ready Bitget UTA trading engine.
Version: v6.0

Implements the "exam" method: Bitget data is treated as a system of noisy
equations that over-determine the global market state. Trade the disagreement
between local signals and price action.

All endpoints and field names verified against Bitget V3 documentation.
"""

import os
import sys
import json
import time
import math
import hmac
import base64
import hashlib
import logging
import threading
from datetime import datetime, timezone
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

# ============================================================================
# Version
# ============================================================================
VERSION = "v6.0"

# ============================================================================
# Logging
# ============================================================================
log = logging.getLogger("exam")
log.setLevel(logging.INFO)
if not log.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    log.addHandler(handler)

log.info(f"===== exam_core {VERSION} loading =====")

# ============================================================================
# Configuration
# ============================================================================
BASE_URL = "https://api.bitget.com"
DEMO_HEADER = {"paptrading": "1"}
CATEGORY = "USDT-FUTURES"

API_KEY = os.environ["API_KEY"]
SECRET_KEY = os.environ["SECRET_KEY"]
PASSPHRASE = os.environ["PASSPHRASE"]

PAPER = os.environ.get("PAPER", "true").lower() == "true"
LEVERAGE = os.environ.get("LEVERAGE", "5")
INTERVAL_S = int(os.environ.get("INTERVAL_S", "30"))
MARGIN_MODE = os.environ.get("MARGIN_MODE", "crossed")

WIN_THRESHOLD = float(os.environ.get("WIN_THRESHOLD", "0.0042"))
REQUIRED_STREAK = int(os.environ.get("REQUIRED_STREAK", "8"))

MIN_BITGET_4H_USDT = float(os.environ.get("MIN_BITGET_4H_USDT", "50000"))
MIN_4H_GROWTH = float(os.environ.get("MIN_4H_GROWTH", "1.0"))
MAX_OI_TO_4H_RATIO = float(os.environ.get("MAX_OI_TO_4H_RATIO", "500"))

MAX_MC_TO_4H_RATIO = float(os.environ.get("MAX_MC_TO_4H_RATIO", "40.0"))
STRICT_MC_FILTER = os.environ.get("STRICT_MC_FILTER", "false").lower() == "true"
MC_CACHE_TTL_S = float(os.environ.get("MC_CACHE_TTL_S", "600"))
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_MIN_INTERVAL_S = float(os.environ.get("COINGECKO_MIN_INTERVAL_S", "2.5"))

SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.50"))
DYING_SCORE_THRESHOLD = float(os.environ.get("DYING_SCORE_THRESHOLD", "0.60"))
TOP_N_CANDIDATES = int(os.environ.get("TOP_N_CANDIDATES", "20"))
WEAKEST_SCAN_INTERVAL_S = int(os.environ.get("WEAKEST_SCAN_INTERVAL_S", "600"))

WIN_1M = 10
WIN_5M = 6
WIN_15M = 4

CANDLE_PAGE_LIMIT = 100
ORDERBOOK_LEVELS = 50
FILLS_LIMIT = 100

RATE_LIMIT_S = float(os.environ.get("RATE_LIMIT_S", "0.20"))
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
HEALTH_FILE = os.environ.get("HEALTH_FILE", "health.json")

# ============================================================================
# CoinGecko symbol map
# ============================================================================
CG_ID_MAP = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "SOLUSDT": "solana",
    "ADAUSDT": "cardano",
    "AKEUSDT": "akedo",
    "JCTUSDT": "janction",
    "MUBARAKUSDT": "mubarak",
    "BTWUSDT": "bitway",
}

# ============================================================================
# Logging helpers
# ============================================================================
def log_candle_request(symbol, interval, page, end_time):
    log.info(f"[CANDLE] {VERSION} {symbol} {interval} limit={CANDLE_PAGE_LIMIT} page={page} endTime={end_time}")

def log_setup(setup):
    log.info(f"SETUP {setup['symbol']} score={setup['score']} side={setup['side']} vol={setup.get('vol_ratio', '?')} stab={setup.get('stability', '?')}")

def log_dying(entry, accepted):
    tag = "ACCEPTED" if accepted else "REJECTED"
    log.info(f"DYING {entry['symbol']} {entry['dying_side']}→{entry['trade_side']} decay={entry['decay']} global={entry['global_score']} [{tag}]")

# ============================================================================
# API layer
# ============================================================================
def timestamp_ms():
    return str(int(time.time() * 1000))

def sign(timestamp, method, path, body_str=""):
    prehash = timestamp + method + path + body_str
    return base64.b64encode(hmac.new(SECRET_KEY.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()).decode("utf-8")

def headers(timestamp, signature):
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

def request(method, path, params=None, body=None):
    last_error = None
    for attempt in range(3):
        try:
            ts = timestamp_ms()
            body_str = json.dumps(body) if body else ""
            sig = sign(ts, method, path, body_str)
            url = BASE_URL + path
            if method.upper() == "GET":
                response = requests.get(url, params=params, headers=headers(ts, sig), timeout=12)
            else:
                response = requests.post(url, data=body_str, headers=headers(ts, sig), timeout=12)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != "00000":
                log.warning(f"API non-success {path}: {payload}")
            return payload
        except Exception as exc:
            last_error = exc
            log.error(f"request {method} {path} attempt {attempt + 1} failed: {exc}")
            time.sleep(1.2)
    return {"code": "unknown", "msg": str(last_error) if last_error else "request_failed", "data": None}

# ============================================================================
# V3 Market Data
# ============================================================================
def get_all_tickers():
    payload = request("GET", "/api/v3/market/tickers", params={"category": CATEGORY})
    return payload.get("data") or []

def get_ticker(symbol):
    for ticker in get_all_tickers():
        if ticker.get("symbol") == symbol:
            return ticker
    return None

def get_history_candles(symbol, interval="1m", total_needed=200):
    all_candles = []
    end_time = None
    page = 0
    while len(all_candles) < total_needed:
        page += 1
        log_candle_request(symbol, interval, page, end_time)
        params = {
            "category": CATEGORY,
            "symbol": symbol,
            "interval": interval,
            "limit": str(CANDLE_PAGE_LIMIT),
        }
        if end_time is not None:
            params["endTime"] = str(end_time)
        payload = request("GET", "/api/v3/market/history-candles", params=params)
        batch = payload.get("data") or []
        if not batch:
            break
        all_candles.extend(batch)
        if len(batch) < CANDLE_PAGE_LIMIT:
            break
        try:
            earliest_ts = int(batch[0][0])
        except (IndexError, ValueError, TypeError):
            break
        end_time = earliest_ts - 1
        time.sleep(RATE_LIMIT_S)
    return all_candles[:total_needed]

def get_orderbook(symbol, limit=ORDERBOOK_LEVELS):
    payload = request("GET", "/api/v3/market/orderbook", params={"category": CATEGORY, "symbol": symbol, "limit": str(limit)})
    return payload.get("data") or {}

def get_recent_fills(symbol, limit=FILLS_LIMIT):
    payload = request("GET", "/api/v3/market/fills", params={"category": CATEGORY, "symbol": symbol, "limit": str(limit)})
    return payload.get("data") or []

def get_open_interest_value(symbol):
    payload = request("GET", "/api/v3/market/open-interest", params={"category": CATEGORY, "symbol": symbol})
    data = payload.get("data") or {}
    lst = data.get("list") or []
    if not lst:
        return 0.0
    try:
        return float(lst[0].get("openInterest", 0))
    except (ValueError, TypeError):
        return 0.0

# ============================================================================
# CoinGecko
# ============================================================================
class CoinGeckoRateLimiter:
    def __init__(self, min_interval_s):
        self.min_interval_s = min_interval_s
        self._last_call_ts = 0.0
        self._lock = threading.Lock()
    def wait(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call_ts
            if elapsed < self.min_interval_s:
                time.sleep(self.min_interval_s - elapsed)
            self._last_call_ts = time.time()

_cg_limiter = CoinGeckoRateLimiter(COINGECKO_MIN_INTERVAL_S)

def get_market_cap(symbol):
    cg_id = CG_ID_MAP.get(symbol)
    if not cg_id:
        return None
    _cg_limiter.wait()
    try:
        response = requests.get(f"{COINGECKO_BASE}/coins/markets", params={"vs_currency": "usd", "ids": cg_id}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return float(data[0].get("market_cap") or 0.0)
    except Exception as exc:
        log.warning(f"coingecko {symbol} ({cg_id}) failed: {exc}")
    return None

_mc_cache = {}

def get_market_cap_cached(symbol):
    now = time.time()
    cached = _mc_cache.get(symbol)
    if cached and (now - cached[1]) < MC_CACHE_TTL_S:
        return cached[0]
    mc = get_market_cap(symbol)
    _mc_cache[symbol] = (mc, now)
    return mc

def passes_market_cap_filter(symbol, four_hour_turnover_usdt):
    if four_hour_turnover_usdt <= 0:
        return False
    market_cap = get_market_cap_cached(symbol)
    if market_cap is None or market_cap <= 0:
        if STRICT_MC_FILTER:
            log.info(f"{symbol}: no market cap available — skip (strict mode)")
            return False
        log.warning(f"{symbol}: market cap unknown — passing unchecked")
        return True
    ratio = market_cap / four_hour_turnover_usdt
    if ratio >= MAX_MC_TO_4H_RATIO:
        log.info(f"{symbol}: MC/4H ratio {ratio:.1f} >= {MAX_MC_TO_4H_RATIO} — skip (MC={market_cap:.0f}, 4H={four_hour_turnover_usdt:.0f})")
        return False
    return True

# ============================================================================
# 4H volume and conviction
# ============================================================================
def get_real_4h_volumes(symbol):
    candles = get_history_candles(symbol, "4H", total_needed=2)
    if not candles:
        return 0.0, 0.0
    try:
        current = float(candles[-1][6])
    except (IndexError, ValueError, TypeError):
        current = 0.0
    if len(candles) >= 2:
        try:
            previous = float(candles[-2][6])
        except (IndexError, ValueError, TypeError):
            previous = current
    else:
        previous = current
    return current, previous

def bitget_conviction(symbol, ticker, current_4h, previous_4h):
    if current_4h < MIN_BITGET_4H_USDT:
        return None
    if previous_4h > 0 and current_4h < previous_4h * MIN_4H_GROWTH:
        return None
    oi_coin = get_open_interest_value(symbol)
    try:
        last_price = float(ticker.get("lastPrice", 0))
        oi_usdt = oi_coin * last_price
    except (ValueError, TypeError):
        oi_usdt = 0.0
    oi_ratio = oi_usdt / current_4h if current_4h > 0 else 0.0
    if oi_ratio > MAX_OI_TO_4H_RATIO:
        log.info(f"{symbol}: OI/4H ratio {oi_ratio:.1f} suspicious — skip (threshold {MAX_OI_TO_4H_RATIO})")
        return None
    return {
        "4h_turnover": current_4h,
        "4h_prev": previous_4h,
        "4h_growth": round(current_4h / previous_4h, 2) if previous_4h > 0 else 1.0,
        "oi_usdt": round(oi_usdt, 2),
        "oi_ratio": round(oi_ratio, 2),
    }

# ============================================================================
# Spoof-resistant order book
# ============================================================================
def snapshot_depth(symbol, samples=3, gap_seconds=2.0):
    snapshots = []
    for i in range(samples):
        ob = get_orderbook(symbol, ORDERBOOK_LEVELS)
        try:
            bids = {b[0]: float(b[1]) for b in ob.get("b", [])[:20]}
            asks = {a[0]: float(a[1]) for a in ob.get("a", [])[:20]}
        except (ValueError, IndexError, TypeError):
            bids, asks = {}, {}
        snapshots.append((bids, asks))
        if i < samples - 1:
            time.sleep(gap_seconds)
    if not snapshots:
        return 0.0, 0.0, None, 0.0
    bid_keys = set(snapshots[0][0])
    ask_keys = set(snapshots[0][1])
    for bids, asks in snapshots[1:]:
        bid_keys &= set(bids)
        ask_keys &= set(asks)
    if not bid_keys or not ask_keys:
        return 0.0, 0.0, None, 0.0
    persistent_bid = sum(min(s[0][k] for s in snapshots) for k in bid_keys)
    persistent_ask = sum(min(s[1][k] for s in snapshots) for k in ask_keys)
    if persistent_bid <= 0 or persistent_ask <= 0:
        return 0.0, 0.0, None, 0.0
    ratio = max(persistent_bid, persistent_ask) / min(persistent_bid, persistent_ask)
    tightness = min(persistent_bid, persistent_ask) / max(persistent_bid, persistent_ask)
    side = "bid" if persistent_bid > persistent_ask else "ask"
    raw_bid = sum(sum(b.values()) for b, _ in snapshots) / len(snapshots)
    raw_ask = sum(sum(a.values()) for _, a in snapshots) / len(snapshots)
    raw_total = raw_bid + raw_ask
    stability = (persistent_bid + persistent_ask) / raw_total if raw_total > 0 else 0.0
    return ratio, tightness, side, stability

# ============================================================================
# CVD and whales
# ============================================================================
def cvd_usdt(fills):
    buy = 0.0
    sell = 0.0
    notionals = []
    for fill in fills:
        try:
            size = float(fill["size"])
            price = float(fill["price"])
            side = fill["side"].lower()
        except (KeyError, ValueError, TypeError):
            continue
        notional = size * price
        notionals.append(notional)
        if side == "buy":
            buy += notional
        else:
            sell += notional
    total = buy + sell
    if total <= 0:
        return 0.0, 0.0, 0.0, 0, 0.0
    cvd_pct = (buy - sell) / total
    cutoff = 0.0
    if notionals:
        sorted_notionals = sorted(notionals)
        cutoff = sorted_notionals[int(len(sorted_notionals) * 0.9)]
    whale_sell_count = 0
    whale_sell_usdt = 0.0
    for fill in fills:
        try:
            notional = float(fill["size"]) * float(fill["price"])
        except (KeyError, ValueError, TypeError):
            continue
        if fill.get("side") == "sell" and notional >= cutoff and notional >= 5000:
            whale_sell_count += 1
            whale_sell_usdt += notional
    return cvd_pct, buy, sell, whale_sell_count, whale_sell_usdt

# ============================================================================
# Candle patterns (volume-confirmed)
# ============================================================================
def candle_pattern_vol(candles, window, label):
    if len(candles) < window:
        return 0.0, f"{label}_short", None, 1.0
    last = candles[-window:]
    greens = []
    reds = []
    for candle in last:
        try:
            open_px = float(candle[1])
            close_px = float(candle[4])
            volume = float(candle[5])
        except (ValueError, IndexError, TypeError):
            continue
        if close_px > open_px:
            greens.append(volume)
        elif close_px < open_px:
            reds.append(volume)
    green_ratio = len(greens) / window
    avg_green_vol = sum(greens) / len(greens) if greens else 0.0
    avg_red_vol = sum(reds) / len(reds) if reds else 0.0
    if green_ratio >= 0.8:
        vol_ratio = avg_green_vol / avg_red_vol if avg_red_vol > 0 else (10.0 if avg_green_vol > 0 else 1.0)
        return green_ratio, f"{label}_up", "buy", vol_ratio
    if green_ratio <= 0.2:
        vol_ratio = avg_red_vol / avg_green_vol if avg_green_vol > 0 else (10.0 if avg_red_vol > 0 else 1.0)
        return 1 - green_ratio, f"{label}_down", "sell", vol_ratio
    return abs(green_ratio - 0.5) * 2, f"{label}_mixed", None, 1.0

def forward_continuation(candles, window=WIN_1M):
    if len(candles) < window * 2:
        return 0.0, 0
    outcomes = []
    for i in range(window, len(candles) - window):
        prior = candles[i - window:i]
        try:
            green_count = sum(1 for c in prior if float(c[4]) > float(c[1]))
        except (ValueError, IndexError, TypeError):
            continue
        if green_count >= 8:
            direction = "up"
        elif green_count <= 2:
            direction = "down"
        else:
            continue
        next_bars = candles[i:i + window]
        try:
            if direction == "up":
                continuation = sum(1 for c in next_bars if float(c[4]) > float(c[1]))
            else:
                continuation = sum(1 for c in next_bars if float(c[4]) < float(c[1]))
        except (ValueError, IndexError, TypeError):
            continue
        outcomes.append(continuation / window)
    if not outcomes:
        return 0.0, 0
    return sum(outcomes) / len(outcomes), len(outcomes)

def three_min_after(candles):
    if len(candles) < WIN_1M + 3:
        return 0.0, 0
    outcomes = []
    for i in range(WIN_1M, len(candles) - 3):
        prior = candles[i - WIN_1M:i]
        try:
            green_count = sum(1 for c in prior if float(c[4]) > float(c[1]))
        except (ValueError, IndexError, TypeError):
            continue
        if green_count >= 8:
            direction = "up"
        elif green_count <= 2:
            direction = "down"
        else:
            continue
        next_bars = candles[i:i + 3]
        try:
            if direction == "up":
                continuation = sum(1 for c in next_bars if float(c[4]) > float(c[1]))
            else:
                continuation = sum(1 for c in next_bars if float(c[4]) < float(c[1]))
        except (ValueError, IndexError, TypeError):
            continue
        outcomes.append(continuation / 3.0)
    if not outcomes:
        return 0.0, 0
    return sum(outcomes) / len(outcomes), len(outcomes)

def basis_snapshot(ticker):
    try:
        last = float(ticker.get("lastPrice", 0))
        index = float(ticker.get("indexPrice", last)) or last
        basis = (last - index) / index
        direction = "premium" if basis > 0 else "discount"
        return abs(basis), direction, basis
    except (ValueError, TypeError):
        return 0.0, None, 0.0

# ============================================================================
# Crowding
# ============================================================================
def crowding_state(symbol, ticker):
    try:
        funding = float(ticker.get("fundingRate", 0))
    except (ValueError, TypeError):
        funding = 0.0
    try:
        oi_coin_ticker = float(ticker.get("openInterest", 0))
        last_price = float(ticker.get("lastPrice", 0))
        oi_usdt_ticker = oi_coin_ticker * last_price
    except (ValueError, TypeError):
        oi_usdt_ticker = 0.0
    oi_coin_endpoint = get_open_interest_value(symbol)
    try:
        oi_usdt_endpoint = oi_coin_endpoint * float(ticker.get("lastPrice", 0))
    except (ValueError, TypeError):
        oi_usdt_endpoint = 0.0
    if oi_usdt_ticker > 0 and oi_usdt_endpoint > 0:
        oi_change = (oi_usdt_endpoint - oi_usdt_ticker) / oi_usdt_ticker
    else:
        oi_change = 0.0
    crowd = "long" if funding > 0 else "short"
    return {
        "funding": funding,
        "crowd": crowd,
        "oi_change": round(oi_change, 4),
        "oi_usdt": round(oi_usdt_ticker, 2),
    }

# ============================================================================
# Dying side
# ============================================================================
def detect_dying_side(candles):
    if len(candles) < 20:
        return None, 0.0
    recent = candles[-10:]
    earlier = candles[-20:-10]

    def fuel(bars, want_green):
        total = 0.0
        for candle in bars:
            try:
                open_px = float(candle[1])
                close_px = float(candle[4])
                volume = float(candle[5])
            except (ValueError, IndexError, TypeError):
                continue
            if want_green and close_px > open_px:
                total += (close_px - open_px) * volume
            elif not want_green and close_px < open_px:
                total += (open_px - close_px) * volume
        return total

    recent_green = fuel(recent, True)
    recent_red = fuel(recent, False)
    earlier_green = fuel(earlier, True)
    earlier_red = fuel(earlier, False)

    def decay(recent_fuel, earlier_fuel):
        if earlier_fuel <= 0:
            return 0.0
        value = (earlier_fuel - recent_fuel) / earlier_fuel
        return max(-1.0, min(1.0, value))

    green_decay = decay(recent_green, earlier_green)
    red_decay = decay(recent_red, earlier_red)

    if green_decay > red_decay and green_decay > 0.25:
        return "buy", green_decay
    if red_decay > green_decay and red_decay > 0.25:
        return "sell", red_decay
    return None, max(green_decay, red_decay)

def verify_global_dying(symbol, ticker, dying_side):
    checks = {}
    score = 0.0

    basis_pct, basis_dir, _ = basis_snapshot(ticker)
    wanted_dir = "discount" if dying_side == "buy" else "premium"
    if basis_dir == wanted_dir:
        checks["basis"] = 1.0
        score += 0.25
    elif basis_pct < 0.0008:
        checks["basis"] = 0.5
        score += 0.12
    else:
        checks["basis"] = 0.0

    crowding = crowding_state(symbol, ticker)
    wanted_crowd = "long" if dying_side == "buy" else "short"
    if crowding["crowd"] == wanted_crowd and abs(crowding["funding"]) > 0.00005 and crowding["oi_change"] > -0.02:
        checks["crowd_oi"] = 1.0
        score += 0.25
    else:
        checks["crowd_oi"] = 0.0

    c1 = get_history_candles(symbol, "1m", total_needed=15)
    velocity_ok = False
    if len(c1) >= 10:
        try:
            first_close = float(c1[0][4])
            last_close = float(c1[-1][4])
            move = (last_close - first_close) / first_close
            if dying_side == "buy" and move <= 0.001:
                velocity_ok = True
            elif dying_side == "sell" and move >= -0.001:
                velocity_ok = True
        except (ValueError, IndexError, TypeError):
            pass
    checks["index_velocity"] = 1.0 if velocity_ok else 0.0
    if velocity_ok:
        score += 0.20

    ob_ratio, _, ob_side, stability = snapshot_depth(symbol, samples=3, gap_seconds=2.0)
    wanted_ob_side = "ask" if dying_side == "buy" else "bid"
    if ob_side == wanted_ob_side and ob_ratio >= 1.5 and stability >= 0.5:
        checks["orderbook"] = min(ob_ratio / 2.5, 1.0)
        score += 0.15 * checks["orderbook"]
    else:
        checks["orderbook"] = 0.0

    cvd, _, _, _, _ = cvd_usdt(get_recent_fills(symbol, FILLS_LIMIT))
    wanted_cvd_negative = dying_side == "buy"
    if (wanted_cvd_negative and cvd < -0.10) or (not wanted_cvd_negative and cvd > 0.10):
        checks["cvd"] = min(abs(cvd) / 0.30, 1.0)
        score += 0.15 * checks["cvd"]
    else:
        checks["cvd"] = 0.0

    return round(score, 4), checks

# ============================================================================
# Regular MTF setup
# ============================================================================
def detect_setup(symbol, ticker):
    c1 = get_history_candles(symbol, "1m", total_needed=200)
    c5 = get_history_candles(symbol, "5m", total_needed=288)
    c15 = get_history_candles(symbol, "15m", total_needed=200)

    if len(c1) < WIN_1M or len(c5) < WIN_5M or len(c15) < WIN_15M:
        return None

    s1, n1, d1, v1 = candle_pattern_vol(c1, WIN_1M, "1m")
    if d1 is None or v1 < 1.2:
        return None

    s5, n5, d5, _ = candle_pattern_vol(c5, WIN_5M, "5m")
    s15, n15, d15, _ = candle_pattern_vol(c15, WIN_15M, "15m")

    if d5 is not None and d5 != d1:
        return None
    if d15 is not None and d15 != d1:
        return None

    cont, cont_n = forward_continuation(c1)
    three, three_n = three_min_after(c1)

    ob_ratio, tightness, _, stability = snapshot_depth(symbol, samples=3, gap_seconds=2.0)
    if stability < 0.5:
        return None

    cvd, _, _, whales, whale_usdt = cvd_usdt(get_recent_fills(symbol, FILLS_LIMIT))
    crowding = crowding_state(symbol, ticker)

    if crowding["crowd"] == "long" and d1 != "sell":
        return None
    if crowding["crowd"] == "short" and d1 != "buy":
        return None

    basis_pct, _, _ = basis_snapshot(ticker)

    score = (
        s1 * 0.20 +
        (s5 if d5 == d1 else 0.0) * 0.10 +
        (s15 if d15 == d1 else 0.0) * 0.08 +
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
        "symbol": symbol,
        "side": "sell" if crowding["crowd"] == "long" else "buy",
        "score": round(score, 4),
        "p1m": n1,
        "p5m": n5,
        "p15m": n15,
        "ob_ratio": round(ob_ratio, 2),
        "tightness": round(tightness, 2),
        "stability": round(stability, 2),
        "cvd": round(cvd, 4),
        "whales": whales,
        "whale_usdt": round(whale_usdt, 2),
        "basis_pct": round(basis_pct, 6),
        "vol_ratio": round(v1, 2),
        "cont_10m": round(cont, 3),
        "cont_n": cont_n,
        "three_min": round(three, 3),
        "three_n": three_n,
        "funding": crowding["funding"],
        "crowd": crowding["crowd"],
    }

# ============================================================================
# Scanner
# ============================================================================
def scan_market(top_n=TOP_N_CANDIDATES):
    tickers = get_all_tickers()
    if not tickers:
        return []

    candidates = []

    for ticker in tickers:
        symbol = ticker.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue

        current_4h, previous_4h = get_real_4h_volumes(symbol)
        if current_4h < MIN_BITGET_4H_USDT:
            continue

        conviction = bitget_conviction(symbol, ticker, current_4h, previous_4h)
        if not conviction:
            continue

        candidates.append({**ticker, "conviction": conviction})

    candidates.sort(key=lambda x: x["conviction"]["4h_turnover"], reverse=True)

    filtered = []
    for candidate in candidates[:top_n]:
        if passes_market_cap_filter(candidate["symbol"], candidate["conviction"]["4h_turnover"]):
            filtered.append(candidate)

    log.info(f"conviction-qualified: {len(candidates)} — after MC filter: {len(filtered)}")
    return filtered

def find_best_setup(candidates):
    start = time.time()
    results = []

    for candidate in candidates:
        symbol = candidate["symbol"]
        try:
            setup = detect_setup(symbol, candidate)
            if setup:
                results.append(setup)
                log_setup(setup)
        except Exception as exc:
            log.warning(f"deep scan {symbol} failed: {exc}")

    elapsed = time.time() - start
    log.info(f"cycle: {len(candidates)} symbols in {elapsed:.1f}s")

    if not results:
        return None
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[0]

def find_weakest_dying(candidates):
    verified = []
    for candidate in candidates:
        symbol = candidate["symbol"]
        try:
            c1 = get_history_candles(symbol, "1m", total_needed=30)
            dying_side, decay = detect_dying_side(c1)
            if dying_side is None or decay < 0.30:
                continue

            global_score, checks = verify_global_dying(symbol, candidate, dying_side)
            trade_side = "sell" if dying_side == "buy" else "buy"

            entry = {
                "symbol": symbol,
                "dying_side": dying_side,
                "trade_side": trade_side,
                "decay": round(decay, 3),
                "global_score": global_score,
                "checks": checks,
            }

            accepted = global_score >= 0.50
            log_dying(entry, accepted)

            if accepted:
                verified.append(entry)
        except Exception as exc:
            log.warning(f"dying {symbol} failed: {exc}")

    if not verified:
        return None
    verified.sort(key=lambda x: x["global_score"], reverse=True)
    return verified[0]

# ============================================================================
# State + health
# ============================================================================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        log.warning(f"{path} load failed: {exc}")
        return default

def save_json(path, payload):
    try:
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(temporary, path)
    except Exception as exc:
        log.error(f"{path} save failed: {exc}")

def mark_ok():
    health = load_json(HEALTH_FILE, {"score": 100})
    health["last_ok"] = datetime.now(timezone.utc).isoformat()
    health["score"] = min(100, health.get("score", 100) + 1)
    save_json(HEALTH_FILE, health)

def mark_error(code, detail=""):
    health = load_json(HEALTH_FILE, {"score": 100})
    health["score"] = max(0, health.get("score", 100) - 5)
    health["last_error"] = {"code": code, "detail": detail}
    save_json(HEALTH_FILE, health)

def is_healthy():
    return load_json(HEALTH_FILE, {"score": 100}).get("score", 100) > 40

# ============================================================================
# Healer
# ============================================================================
ERROR_BOOK = {
    "40762": ("order size > max open size", "shrink notional", "reduce"),
    "40034": ("symbol unavailable", "quarantine symbol", "skip"),
    "400171": ("parameter error", "retry clean", "retry"),
    "40109": ("balance low", "pause 5 minutes", "pause"),
    "43012": ("no position to close", "resync local position", "resync"),
    "429": ("rate limit", "backoff 30 seconds", "backoff"),
    "50001": ("venue unavailable", "backoff 30 seconds", "backoff"),
    "50011": ("IP blocked", "pause 5 minutes", "pause"),
    "40085": ("UTA gate", "check V3 payload", "pause"),
}

class Healer:
    def __init__(self, trader):
        self.trader = trader
        self.cooldown_until = 0.0

    def cool(self, seconds):
        self.cooldown_until = time.time() + seconds
        log.info(f"cooldown {seconds}s")

    def cooling(self):
        return time.time() < self.cooldown_until

    def treat(self, payload):
        if self.cooling():
            return "cooling"

        code = str(payload.get("code", "")).strip()
        message = str(payload.get("msg", "")) or str(payload.get("detail", ""))
        log.warning(f"symptom {code}: {message}")
        mark_error(code, message)

        entry = ERROR_BOOK.get(code)
        if entry is None:
            log.info("unknown symptom — generic backoff 5s")
            self.cool(5)
            return "generic"

        _, _, action = entry

        if action == "reduce":
            self.trader.usdt_notional = max(0.5, round(self.trader.usdt_notional * 0.75, 3))
            log.info(f"usdt_notional -> {self.trader.usdt_notional}")
            self.cool(10)
        elif action == "skip":
            symbol = self.trader.position.get("symbol") if self.trader.position else None
            if symbol:
                state = load_json(STATE_FILE, {})
                skipped = state.setdefault("skipped", [])
                if symbol not in skipped:
                    skipped.append(symbol)
                save_json(STATE_FILE, state)
                log.info(f"symbol quarantined: {symbol}")
            self.trader.position = None
            self.cool(5)
        elif action == "retry":
            time.sleep(1.5)
        elif action == "pause":
            log.error("PAUSE — human attention needed")
            self.cool(300)
        elif action == "backoff":
            self.cool(30)
        elif action == "resync":
            self.trader.position = None
            log.info("local position cleared — will resync next tick")
            self.cool(5)

        return action

    def check_response(self, response):
        if not response:
            return None
        if str(response.get("code")) == "00000":
            mark_ok()
            return None
        return self.treat(response)

    def check_exception(self, exc):
        detail = str(exc).lower()
        if "timeout" in detail or "connection" in detail:
            code = "50001"
        elif "429" in detail:
            code = "429"
        elif "401" in detail or "auth" in detail:
            code = "50011"
        else:
            code = "unknown"
        return self.treat({"code": code, "msg": str(exc)})

# ============================================================================
# Streak validator
# ============================================================================
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

# ============================================================================
# Trading engine
# ============================================================================
class ExamTrader:
    def __init__(self):
        self.validator = StreakValidator()
        self.position = None
        self.usdt_notional = 2.0
        self.healer = Healer(self)
        self.last_dying_scan = 0.0
        self.restore()

    def restore(self):
        state = load_json(STATE_FILE, {})
        self.validator.streak = state.get("streak", 0)
        self.validator.accepted = self.validator.streak >= REQUIRED_STREAK
        self.validator.history = state.get("history", [])
        self.usdt_notional = state.get("usdt_notional", 2.0)
        self.last_dying_scan = state.get("last_dying_scan", 0.0)
        log.info(f"restored streak={self.validator.streak} accepted={self.validator.accepted} notional={self.usdt_notional}")

    def persist(self):
        state = load_json(STATE_FILE, {})
        state.update({
            "streak": self.validator.streak,
            "accepted": self.validator.accepted,
            "history": self.validator.history,
            "usdt_notional": self.usdt_notional,
            "last_dying_scan": self.last_dying_scan,
        })
        save_json(STATE_FILE, state)

    def ensure_leverage(self, symbol):
        body = {
            "category": CATEGORY,
            "symbol": symbol,
            "leverage": LEVERAGE,
            "marginMode": MARGIN_MODE,
        }
        if MARGIN_MODE == "isolated":
            body["posSide"] = "long"
        response = request("POST", "/api/v3/account/set-leverage", body=body)
        self.healer.check_response(response)
        time.sleep(RATE_LIMIT_S)

    def place_v3(self, symbol, side, quantity, reduce_only="no"):
        body = {
            "category": CATEGORY,
            "symbol": symbol,
            "qty": str(quantity),
            "side": side,
            "orderType": "market",
            "reduceOnly": reduce_only,
            "clientOid": f"ex{int(time.time() * 1000)}",
        }
        response = request("POST", "/api/v3/trade/place-order", body=body)
        self.healer.check_response(response)
        return response

    def open(self, symbol, side):
        ticker = get_ticker(symbol)
        if not ticker:
            return
        try:
            price = float(ticker["lastPrice"])
        except (KeyError, ValueError, TypeError):
            return
        quantity = round(self.usdt_notional / price, 6)
        if quantity <= 0:
            return
        self.ensure_leverage(symbol)
        self.place_v3(symbol, side, quantity, reduce_only="no")
        self.position = {
            "symbol": symbol,
            "side": side,
            "qty": quantity,
            "entry": price,
            "ts": time.time(),
        }
        log.info(f"OPEN {side} {symbol} qty={quantity} @ {price}")
        self.persist()

    def close(self, current_price):
        if not self.position:
            return None
        position = self.position
        close_side = "sell" if position["side"] == "buy" else "buy"
        response = self.place_v3(position["symbol"], close_side, position["qty"], reduce_only="yes")
        if response and str(response.get("code")) == "00000":
            data = response.get("data") or {}
            if isinstance(data, dict) and data.get("orderId") is None:
                log.warning("reduceOnly returned null orderId — verify manually")
        entry = position["entry"]
        if position["side"] == "buy":
            pnl = (current_price - entry) / entry
        else:
            pnl = (entry - current_price) / entry
        self.validator.record(pnl)
        self.position = None
        self.persist()
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
            try:
                price = float(ticker["lastPrice"])
            except (KeyError, ValueError, TypeError):
                return
            entry = self.position["entry"]
            if self.position["side"] == "buy":
                change = (price - entry) / entry
            else:
                change = (entry - price) / entry
            if change >= WIN_THRESHOLD or change <= -WIN_THRESHOLD:
                pnl = self.close(price)
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
            self.persist()

        if dying_setup and dying_setup["global_score"] >= DYING_SCORE_THRESHOLD:
            setup = {
                "symbol": dying_setup["symbol"],
                "side": dying_setup["trade_side"],
                "score": dying_setup["global_score"],
                "source": "dying",
            }
        else:
            regular_setup = find_best_setup(candidates)
            if not regular_setup:
                log.info("no aligned setup this cycle")
                return
            setup = {**regular_setup, "source": "mtf"}

        if not self.validator.can_trade():
            log.info(f"would trade {setup['symbol']} {setup['side']} score={setup['score']} src={setup['source']} — streak {self.validator.streak}/{REQUIRED_STREAK}, paper-only")
            return

        log.info(f"TRADE {setup['symbol']} {setup['side']} score={setup['score']} src={setup['source']}")
        self.open(setup["symbol"], setup["side"])

# ============================================================================
# Keep-alive server
# ============================================================================
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass

def start_keepalive():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    log.info(f"keep-alive listening on :{port}")
    server.serve_forever()

# ============================================================================
# Entry point
# ============================================================================
def main():
    log.info(f"===== exam_core {VERSION} starting =====")
    log.info(f"paper={PAPER} leverage={LEVERAGE}x margin={MARGIN_MODE} streak={REQUIRED_STREAK} win={WIN_THRESHOLD:.4f} interval={INTERVAL_S}s candle_limit={CANDLE_PAGE_LIMIT}")
    trader = ExamTrader()
    while True:
        try:
            trader.step()
        except Exception as exc:
            log.error(f"step error: {exc}", exc_info=True)
            trader.healer.check_exception(exc)
        time.sleep(INTERVAL_S)

if __name__ == "__main__":
    threading.Thread(target=start_keepalive, daemon=True).start()
    main()
