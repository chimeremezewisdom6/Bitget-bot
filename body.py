# body.py
# Executor. WebSocket trades → OFI windows → Brain (+ Lead-Lag) → Setup ledger.
# Exposes MARKET_STATE (with trade_buffer) for Learner and Scanner.

import asyncio
import json
import os
import time
import logging
from collections import deque
from pathlib import Path

import ccxt.pro as ccxtpro
import aiohttp

from brain import OfiWindow, decide_entry
from lead_lag import LEADERS, PriceCache, snapshot_prices, compute_lag

log = logging.getLogger("body")

SETUP_URL = os.environ.get("SETUP_URL", "http://localhost:8000")
EXECUTION_VENUE = os.environ.get("EXECUTION_VENUE", "bitget")
PAPER_MODE = os.environ.get("PAPER_MODE", "true").lower() == "true"
LEVERAGE = int(os.environ.get("LEVERAGE", "3"))
RISK_PCT = float(os.environ.get("RISK_PCT", "0.90"))
MAX_SLIPPAGE_PCT = float(os.environ.get("MAX_SLIPPAGE", "0.05"))
TRAILING_STOP_PCT = float(os.environ.get("TRAILING_STOP_PCT", "1.0"))
CONTINUATION_REQUIRED = int(os.environ.get("CONTINUATION_REQUIRED", "4"))

# Retention: 2× 1h = 7200s required for the 1h scanner timeframe.
# Buffer cap prevents runaway memory on high-volume pairs.
TRADE_BUFFER_MAXLEN = 200_000
TRADE_BUFFER_RETENTION_S = 7500

MARKET_STATE: dict[str, dict] = {}

def _load_params() -> dict:
    default = {
        "ofi_1m_orders_min": 1.5, "ofi_1m_volume_min": 2.0,
        "ofi_3m_orders_min": 2.0, "ofi_3m_volume_min": 3.0,
        "ofi_10m_volume_min": 1.5, "continuation_required": 4,
        "lag_gap_min": 0.5,
    }
    path = Path(os.environ.get("BEST_PARAMS", "/tmp/best_params.json"))
    if path.exists():
        try:
            data = json.loads(path.read_text())
            clean = {k: v for k, v in data.items() if not k.startswith("_")}
            return {**default, **clean}
        except Exception:
            pass
    return default

PARAMS = _load_params()

# ============================================================
# CLIENTS
# ============================================================

def public_ws(exchange_id: str):
    return getattr(ccxtpro, exchange_id)({"enableRateLimit": True, "newUpdates": True})

def private_client():
    if EXECUTION_VENUE == "bitget":
        ex = ccxtpro.bitget({
            "apiKey": os.environ["BITGET_API_KEY"],
            "secret": os.environ["BITGET_SECRET_KEY"],
            "password": os.environ["BITGET_PASSPHRASE"],
            "enableRateLimit": True,
            "options": {"defaultType": "swap", "uta": True},
        })
    elif EXECUTION_VENUE == "mexc":
        ex = ccxtpro.mexc({
            "apiKey": os.environ["MEXC_API_KEY"],
            "secret": os.environ["MEXC_SECRET_KEY"],
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
    else:
        raise ValueError(f"unknown EXECUTION_VENUE: {EXECUTION_VENUE}")
    if PAPER_MODE:
        ex.set_sandbox_mode(True)
    return ex

# ============================================================
# SLIPPAGE
# ============================================================

def compute_slippage_from_levels(levels: list, side: str, notional_usd: float) -> float:
    if not levels:
        return 999.0
    best = levels[0][0]
    remaining = notional_usd
    spent = 0.0
    filled_qty = 0.0
    for price, qty in levels:
        level_notional = price * qty
        take = min(level_notional, remaining)
        filled_qty += take / price
        spent += take
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        return 999.0
    avg = spent / filled_qty
    return abs(avg - best) / best * 100.0

async def estimate_slippage(ex, symbol: str, side: str, notional_usd: float) -> float:
    try:
        ob = await ex.fetch_order_book(symbol, limit=50)
    except Exception as e:
        log.warning("order book fetch failed: %s", e)
        return 999.0
    levels = ob["asks"] if side == "buy" else ob["bids"]
    return compute_slippage_from_levels(levels, side, notional_usd)

# ============================================================
# ORDER PLACEMENT
# ============================================================

async def place_order(ex, symbol: str, side: str, notional_usd: float, price: float):
    qty = notional_usd / price
    if EXECUTION_VENUE == "bitget":
        return await ex.create_order(symbol, "market", side, qty, None,
                                     {"uta": True, "reduceOnly": "NO"})
    elif EXECUTION_VENUE == "mexc":
        return await ex.create_order(symbol, "market", side, qty, None)
    raise ValueError(EXECUTION_VENUE)

async def close_position(ex, symbol: str, open_side: str, qty: float):
    close_side = "sell" if open_side == "buy" else "buy"
    if EXECUTION_VENUE == "bitget":
        params = {"uta": True, "reduceOnly": "YES"}
    else:
        params = {}
    order = await ex.create_order(symbol, "market", close_side, qty, None, params)
    if EXECUTION_VENUE == "bitget":
        try:
            positions = await ex.fetch_positions([symbol], {"uta": True})
            still_open = [p for p in positions if abs(float(p.get("contracts", 0) or 0)) > 0]
            if still_open:
                log.error("reduceOnly did not close %s — manual check needed", symbol)
        except Exception as e:
            log.warning("position verify failed: %s", e)
    return order

# ============================================================
# PAPER LEDGER
# ============================================================

class PaperLedger:
    def __init__(self):
        self.open: dict[str, dict] = {}

    def open_pos(self, symbol, side, price, qty, ts):
        self.open[symbol] = {"side": side, "entry": price, "qty": qty,
                             "ts_open": ts, "peak": price, "trough": price}

    def update_peak(self, symbol, price):
        if symbol in self.open:
            p = self.open[symbol]
            p["peak"] = max(p["peak"], price)
            p["trough"] = min(p["trough"], price)

    def close_pos(self, symbol, price, ts):
        p = self.open.pop(symbol, None)
        if not p:
            return None
        return {**p, "exit": price, "ts_close": ts}

# ============================================================
# EXIT HELPER
# ============================================================

async def _exit(http, private, ledger: PaperLedger, symbol: str, price: float, now: float, reason: str):
    closed = ledger.close_pos(symbol, price, now)
    if not closed:
        return
    if not PAPER_MODE:
        try:
            await close_position(private, symbol, closed["side"], closed["qty"])
        except Exception as e:
            log.error("close failed %s: %s", symbol, e)
    payload = {
        "symbol": symbol, "side": closed["side"],
        "entry_price": closed["entry"], "exit_price": closed["exit"],
        "ts_open": closed["ts_open"], "is_paper": PAPER_MODE,
    }
    try:
        async with http.post(f"{SETUP_URL}/trade/close", json=payload) as resp:
            res = await resp.json()
            log.info("%s %s → setup: %s", symbol, reason, res)
    except Exception as e:
        log.warning("setup post failed: %s", e)

# ============================================================
# PER-SYMBOL RUNNER
# ============================================================

async def run_symbol(symbol: str, private):
    ws = public_ws("bitget")
    win_1m = OfiWindow(60)
    win_3m = OfiWindow(180)
    win_10m = OfiWindow(600)
    minute_volumes = deque(maxlen=5)
    price_series = deque(maxlen=300)
    trade_buffer = deque(maxlen=TRADE_BUFFER_MAXLEN)   # (ts, side, price, qty)
    last_minute_bucket = None
    minute_volume_acc = 0.0

    leader_caches = {ex_id: PriceCache(600) for ex_id in LEADERS}
    lagger_cache = PriceCache(600)

    ledger = PaperLedger()
    warmup_until = time.time() + 185

    async def fetch_leaders_prices():
        while True:
            ts = time.time()
            for ex_id in LEADERS:
                p = await snapshot_prices(ex_id, symbol)
                if p:
                    leader_caches[ex_id].add(ts, p)
            p = await snapshot_prices(EXECUTION_VENUE, symbol)
            if p:
                lagger_cache.add(ts, p)
            await asyncio.sleep(5)

    leader_task = asyncio.create_task(fetch_leaders_prices())

    try:
        async with aiohttp.ClientSession() as http:
            while True:
                try:
                    trades = await ws.watch_trades(symbol)
                except Exception as e:
                    log.warning("ws error %s: %s", symbol, type(e).__name__)
                    await asyncio.sleep(2)
                    continue

                now = time.time()
                for t in trades:
                    side = "buy" if t.get("side") == "buy" else "sell"
                    px = float(t["price"])
                    qty = float(t["amount"])
                    ts = t["timestamp"] / 1000.0
                    win_1m.add(ts, side, px, qty)
                    win_3m.add(ts, side, px, qty)
                    win_10m.add(ts, side, px, qty)
                    trade_buffer.append((ts, side, px, qty))
                    price_series.append(px)
                    minute_volume_acc += px * qty

                # Retain enough history for the 1h scanner window (2× 1h = 7200s)
                cutoff = now - TRADE_BUFFER_RETENTION_S
                while trade_buffer and trade_buffer[0][0] < cutoff:
                    trade_buffer.popleft()

                minute_bucket = int(now // 60)
                if last_minute_bucket is None:
                    last_minute_bucket = minute_bucket
                elif minute_bucket != last_minute_bucket:
                    minute_volumes.append(minute_volume_acc)
                    minute_volume_acc = 0.0
                    last_minute_bucket = minute_bucket

                if symbol in ledger.open and trades:
                    ledger.update_peak(symbol, float(trades[-1]["price"]))

                MARKET_STATE[symbol] = {
                    "win_1m": win_1m, "win_3m": win_3m, "win_10m": win_10m,
                    "minute_volumes": minute_volumes, "price_series": price_series,
                    "current_price": float(trades[-1]["price"]) if trades else 0.0,
                    "last_updated": now,
                    "lag_gap_pct": MARKET_STATE.get(symbol, {}).get("lag_gap_pct", 0.0),
                    "trade_buffer": trade_buffer,
                }

                if now < warmup_until:
                    continue

                # === EXIT LOGIC ===
                if symbol in ledger.open:
                    pos = ledger.open[symbol]
                    cur = float(trades[-1]["price"]) if trades else pos["entry"]
                    age = now - pos["ts_open"]

                    if age >= 180:
                        if pos["side"] == "buy":
                            drawdown = (pos["peak"] - cur) / pos["peak"] * 100.0
                        else:
                            drawdown = (cur - pos["trough"]) / pos["trough"] * 100.0

                        if drawdown >= TRAILING_STOP_PCT:
                            await _exit(http, private, ledger, symbol, cur, now, "trailing_stop")
                            continue

                        m3 = list(minute_volumes)[-1] if minute_volumes else 0
                        peak_vol = max(minute_volumes) if minute_volumes else 1
                        flying = (peak_vol > 0 and m3 >= peak_vol and
                                  ((pos["side"] == "buy" and cur >= pos["entry"] * 1.015) or
                                   (pos["side"] == "sell" and cur <= pos["entry"] * 0.985)))
                        if not flying:
                            await _exit(http, private, ledger, symbol, cur, now, "time_stop")
                            continue
                    continue

                # === ENTRY LOGIC ===
                share_result = {"passed": True}
                signal = decide_entry(symbol, share_result, win_1m, win_3m, win_10m,
                                      list(minute_volumes), list(price_series),
                                      required_score=PARAMS.get("continuation_required", 4),
                                      params=PARAMS)
                if signal is None:
                    continue

                lag = await compute_lag(symbol, EXECUTION_VENUE, leader_caches, lagger_cache)
                if lag is None:
                    continue
                if (signal.side == "buy" and lag.direction != "buy") or \
                   (signal.side == "sell" and lag.direction != "sell"):
                    continue
                MARKET_STATE[symbol]["lag_gap_pct"] = lag.gap_pct

                entry_px = float(trades[-1]["price"]) if trades else 0.0
                if entry_px <= 0:
                    continue

                balance = float(os.environ.get("START_BALANCE", "1.58"))
                notional = balance * RISK_PCT * LEVERAGE
                if not PAPER_MODE:
                    slip = await estimate_slippage(private, symbol, signal.side, notional)
                    if slip > MAX_SLIPPAGE_PCT:
                        log.info("%s SKIP: slippage %.3f%% > %.3f%%", symbol, slip, MAX_SLIPPAGE_PCT)
                        continue

                qty = notional / entry_px
                if PAPER_MODE:
                    ledger.open_pos(symbol, signal.side, entry_px, qty, now)
                    log.info("PAPER OPEN %s %s @ %.6f qty=%.6f", symbol, signal.side, entry_px, qty)
                else:
                    await place_order(private, symbol, signal.side, notional, entry_px)
                    ledger.open_pos(symbol, signal.side, entry_px, qty, now)
    finally:
        leader_task.cancel()
        try:
            await leader_task
        except asyncio.CancelledError:
            pass
        await ws.close()

# ============================================================
# ENTRY
# ============================================================

async def run(symbols: list[str], params: dict | None = None):
    global PARAMS
    if params:
        PARAMS = {**PARAMS, **params}
    private = None if PAPER_MODE else private_client()
    await asyncio.gather(*(run_symbol(s, private) for s in symbols))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    syms = os.environ.get("SYMBOLS", "BTC/USDT:USDT").split(",")
    asyncio.run(run(syms))
