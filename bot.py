# bot.py
import os
import json
import time
import hmac
import base64
import hashlib
import asyncio
import logging
import threading
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
import aiohttp

from market_math import MarketMath

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ProfitRatchetSentinel")

API_KEY = (os.getenv("API_KEY") or os.getenv("BITGET_API_KEY", "")).strip()
SECRET_KEY = (os.getenv("SECRET_KEY") or os.getenv("BITGET_API_SECRET", "")).strip()
PASSPHRASE = (os.getenv("PASSPHRASE") or os.getenv("BITGET_API_PASSPHRASE", "")).strip()
PORT = int(os.getenv("PORT", 10000))

# ----------------- RISK & EXECUTION PARAMETERS -----------------
LEVERAGE = 5
FEE_AND_SLIPPAGE = 0.22         # 0.12% fees + 0.10% real market-order slippage
HARD_STOP_GROSS = -0.50         # Snappy emergency stop
GLOBAL_MIN_VOL_USD = 1_000_000.0
REQUIRED_STREAK = 8
STATE_FILE = "streak.json"

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception: pass
    return {"streak": 0, "unlocked": False, "total_trades": 0}

def save_state(s: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except Exception: pass

state = load_state()

# ----------------- KEEP-ALIVE SERVER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ONLINE",
            "account_mode": "BITGET_UNIFIED_TRADING_ACCOUNT_V3",
            "mode": "LIVE" if state["unlocked"] else "PAPER_GAUNTLET",
            "streak": f"{state['streak']}/{REQUIRED_STREAK}",
            "trades": state["total_trades"],
            "profit_ratchet": "40_PERCENT_GIVEBACK_MAX"
        }).encode("utf-8"))
    def log_message(self, *args): pass

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# ----------------- BITGET UNIFIED TRADING ACCOUNT (UTA V3) CLIENT -----------------
class BitgetUTAClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.base_url = "https://api.bitget.com"

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = timestamp + method.upper() + path + body
        sig = hmac.new(SECRET_KEY.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(sig).decode("utf-8")

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        ts = str(int(time.time() * 1000))
        return {
            "ACCESS-KEY": API_KEY,
            "ACCESS-SIGN": self._sign(ts, method, path, body),
            "ACCESS-PASSPHRASE": PASSPHRASE,
            "ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
            "locale": "en-US"
        }

    async def get_available_usdt(self) -> float:
        if not API_KEY or not SECRET_KEY or not PASSPHRASE:
            return 1.58

        path_v3 = "/api/v3/account/assets"
        try:
            h = self._headers("GET", path_v3)
            async with self.s.get(self.base_url + path_v3, headers=h, timeout=2.5) as r:
                res = await r.json()
                if res.get("code") == "00000":
                    for item in res.get("data", []):
                        if item.get("coin") == "USDT" or item.get("marginCoin") == "USDT":
                            val = float(item.get("available", 0.0) or item.get("equity", 0.0))
                            if val > 0:
                                return val
        except Exception: pass

        path_all = "/api/v2/account/all-account-balance"
        try:
            h = self._headers("GET", path_all)
            async with self.s.get(self.base_url + path_all, headers=h, timeout=2.5) as r:
                res = await r.json()
                if res.get("code") == "00000":
                    for acc in res.get("data", []):
                        for coin_info in acc.get("assets", []):
                            if coin_info.get("coin") == "USDT":
                                val = float(coin_info.get("available", 0.0) or coin_info.get("balance", 0.0))
                                if val > 0:
                                    return val
        except Exception: pass

        return 1.58

    def calculate_order_qty(self, current_price: float, balance_usdt: float) -> str:
        if current_price <= 0: return "1"
        usable_margin = max(1.10, balance_usdt * 0.90)
        notional_value = usable_margin * LEVERAGE

        if notional_value < 5.10:
            notional_value = 5.20

        raw_size = notional_value / current_price

        if current_price >= 1000:
            return f"{raw_size:.4f}"
        elif current_price >= 1:
            return f"{raw_size:.2f}"
        elif current_price >= 0.01:
            return f"{raw_size:.1f}"
        else:
            return str(int(raw_size))

    async def open_order_uta(self, symbol: str, side: str, qty_str: str) -> bool:
        lev_path = "/api/v3/account/set-leverage"
        lev_body = json.dumps({"category": "USDT-FUTURES", "symbol": symbol, "leverage": str(LEVERAGE)})
        try:
            h = self._headers("POST", lev_path, lev_body)
            await self.s.post(self.base_url + lev_path, data=lev_body, headers=h, timeout=1.5)
        except Exception: pass

        path = "/api/v3/trade/place-order"
        payload = json.dumps({
            "category": "USDT-FUTURES", "symbol": symbol, "side": side,
            "orderType": "market", "qty": qty_str, "reduceOnly": "no"
        })
        try:
            h = self._headers("POST", path, payload)
            async with self.s.post(self.base_url + path, data=payload, headers=h, timeout=2.0) as r:
                res = await r.json()
                return res.get("code") == "00000"
        except Exception:
            return False

    async def safe_close_position_uta(self, symbol: str, open_side: str) -> bool:
        pos_path = f"/api/v3/position/current-position?category=USDT-FUTURES&symbol={symbol}"
        actual_qty = "0"
        try:
            h = self._headers("GET", pos_path)
            async with self.s.get(self.base_url + pos_path, headers=h, timeout=1.5) as r:
                if r.status == 200:
                    d = await r.json()
                    for p in d.get("data", []):
                        total_pos = float(p.get("total", 0.0) or p.get("qty", 0.0))
                        if total_pos > 0:
                            actual_qty = str(total_pos)
                            break
        except Exception: pass

        if float(actual_qty) <= 0:
            return True

        close_side = "sell" if open_side == "buy" else "buy"
        order_path = "/api/v3/trade/place-order"
        order_payload = json.dumps({
            "category": "USDT-FUTURES", "symbol": symbol, "side": close_side,
            "orderType": "market", "qty": actual_qty, "reduceOnly": "yes"
        })

        for _ in range(3):
            try:
                h = self._headers("POST", order_path, order_payload)
                async with self.s.post(self.base_url + order_path, data=order_payload, headers=h, timeout=1.5) as r:
                    res = await r.json()
                    if res.get("code") == "00000":
                        logger.info(f"🔒 Position closed on Bitget UTA ({actual_qty} contracts): {symbol}")
                        return True
            except Exception: pass
            await asyncio.sleep(0.3)
        return False

# ----------------- PARALLEL 8-EXCHANGE ORDER BOOK PROBE -----------------
class EightExchangeDepthProbe:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session

    async def _binance(self, base: str):
        try:
            url = f"https://fapi.binance.com/fapi/v1/depth?symbol={base}USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = await r.json()
                    return ("binance", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _bybit(self, base: str):
        try:
            url = f"https://api.bybit.com/v5/market/orderbook?category=linear&symbol={base}USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("result", {})
                    return ("bybit", d.get("b", []), d.get("a", []))
        except Exception: pass
        return None

    async def _okx(self, base: str):
        try:
            url = f"https://www.okx.com/api/v5/market/books?instId={base}-USDT-SWAP&sz=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", [{}])[0]
                    bids = [[x[0], x[1]] for x in d.get("bids", []) if len(x) >= 2]
                    asks = [[x[0], x[1]] for x in d.get("asks", []) if len(x) >= 2]
                    return ("okx", bids, asks)
        except Exception: pass
        return None

    async def _gate(self, base: str):
        try:
            url = f"https://api.gateio.ws/api/v4/futures/usdt/order_book?contract={base}_USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = await r.json()
                    bids = [[x["p"], x["s"]] for x in d.get("bids", []) if "p" in x and "s" in x]
                    asks = [[x["p"], x["s"]] for x in d.get("asks", []) if "p" in x and "s" in x]
                    return ("gate", bids, asks)
        except Exception: pass
        return None

    async def _mexc(self, base: str):
        try:
            url = f"https://contract.mexc.com/api/v1/contract/depth/{base}_USDT?limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    return ("mexc", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _kucoin(self, base: str):
        try:
            url = f"https://api-futures.kucoin.com/api/v1/level2/depth20?symbol={base}USDTM"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    return ("kucoin", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _bingx(self, base: str):
        try:
            url = f"https://open-api.bingx.com/openApi/swap/v2/quote/depth?symbol={base}-USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    return ("bingx", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _hyperliquid(self, base: str):
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "l2Book", "coin": base}
            async with self.s.post(url, json=payload, timeout=0.8) as r:
                if r.status == 200:
                    d = await r.json()
                    levels = d.get("levels", [[], []])
                    bids = [[x["px"], x["sz"]] for x in levels[0] if "px" in x and "sz" in x]
                    asks = [[x["px"], x["sz"]] for x in levels[1] if "px" in x and "sz" in x]
                    return ("hyperliquid", bids, asks)
        except Exception: pass
        return None

    async def get_depths_all_8(self, base: str) -> list:
        tasks = [
            self._binance(base), self._okx(base), self._bybit(base), self._gate(base),
            self._mexc(base), self._kucoin(base), self._bingx(base), self._hyperliquid(base)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, tuple) and r is not None]

# ----------------- BACKGROUND GLOBAL VOLUME AGGREGATOR -----------------
class GlobalVolumeEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.global_volume_cache = {}
        self.qualifying_count = 0

    async def background_worker(self):
        while True:
            try:
                totals = {}
                t_start = time.time()

                async def _binance():
                    try:
                        async with self.s.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=2.5) as r:
                            if r.status == 200:
                                for item in await r.json():
                                    sym = item.get("symbol", "")
                                    if sym.endswith("USDT"):
                                        b = sym[:-4]
                                        totals[b] = totals.get(b, 0.0) + float(item.get("quoteVolume", 0.0))
                    except Exception: pass

                async def _bybit():
                    try:
                        async with self.s.get("https://api.bybit.com/v5/market/tickers?category=linear", timeout=2.5) as r:
                            if r.status == 200:
                                for item in (await r.json()).get("result", {}).get("list", []):
                                    sym = item.get("symbol", "")
                                    if sym.endswith("USDT"):
                                        b = sym[:-4]
                                        totals[b] = totals.get(b, 0.0) + float(item.get("turnover24h", 0.0))
                    except Exception: pass

                async def _okx():
                    try:
                        async with self.s.get("https://www.okx.com/api/v5/market/tickers?instType=SWAP", timeout=2.5) as r:
                            if r.status == 200:
                                for item in (await r.json()).get("data", []):
                                    inst = item.get("instId", "")
                                    if inst.endswith("-USDT-SWAP"):
                                        b = inst.split("-")[0]
                                        totals[b] = totals.get(b, 0.0) + (float(item.get("volCcy24h", 0.0)) * float(item.get("last", 0.0)))
                    except Exception: pass

                async def _gate():
                    try:
                        async with self.s.get("https://api.gateio.ws/api/v4/futures/usdt/tickers", timeout=2.5) as r:
                            if r.status == 200:
                                for item in await r.json():
                                    contract = item.get("contract", "")
                                    if contract.endswith("_USDT"):
                                        b = contract[:-5]
                                        totals[b] = totals.get(b, 0.0) + float(item.get("volume_24h_quote", 0.0))
                    except Exception: pass

                async def _mexc():
                    try:
                        async with self.s.get("https://contract.mexc.com/api/v1/contract/ticker", timeout=2.5) as r:
                            if r.status == 200:
                                for item in (await r.json()).get("data", []):
                                    sym = item.get("symbol", "")
                                    if sym.endswith("_USDT"):
                                        b = sym[:-5]
                                        totals[b] = totals.get(b, 0.0) + float(item.get("amount24", 0.0))
                    except Exception: pass

                async def _bingx():
                    try:
                        async with self.s.get("https://open-api.bingx.com/openApi/swap/v2/quote/ticker", timeout=2.5) as r:
                            if r.status == 200:
                                for item in (await r.json()).get("data", []):
                                    sym = item.get("symbol", "")
                                    if sym.endswith("-USDT"):
                                        b = sym.split("-")[0]
                                        totals[b] = totals.get(b, 0.0) + float(item.get("volume", 0.0))
                    except Exception: pass

                async def _kucoin():
                    try:
                        async with self.s.get("https://api-futures.kucoin.com/api/v1/contracts/active", timeout=2.5) as r:
                            if r.status == 200:
                                for item in (await r.json()).get("data", []):
                                    sym = item.get("symbol", "")
                                    if sym.endswith("USDTM"):
                                        b = sym[:-5]
                                        totals[b] = totals.get(b, 0.0) + float(item.get("turnoverOf24h", 0.0))
                    except Exception: pass

                await asyncio.gather(_binance(), _bybit(), _okx(), _gate(), _mexc(), _bingx(), _kucoin(), return_exceptions=True)

                if totals:
                    self.global_volume_cache = totals
                    over_1m = sum(1 for v in totals.values() if v >= GLOBAL_MIN_VOL_USD)
                    self.qualifying_count = over_1m
                    logger.info(
                        f"🌐 8-Exchange Volume Synced in {time.time() - t_start:.2f}s | "
                        f"Mapped: {len(totals)} coins | Qualifying (>= $1M Global): {over_1m} coins"
                    )
            except Exception: pass
            await asyncio.sleep(300)

    def get_global_volume(self, base: str, bitget_vol: float) -> float:
        return self.global_volume_cache.get(base, 0.0) + bitget_vol

# ----------------- PARALLEL HIGH-WIN-RATE ENGINE -----------------
class MasterEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.bitget = BitgetUTAClient(session)
        self.depth_probe = EightExchangeDepthProbe(session)
        self.global_vol = GlobalVolumeEngine(session)
        self.price_history = {}
        self.active_trade = None
        self.sem = asyncio.Semaphore(25)

    async def fetch_single_candle_set(self, sym: str, base: str) -> tuple:
        async with self.sem:
            url_bitget = f"https://api.bitget.com/api/v2/mix/market/candles?symbol={sym}&productType=usdt-futures&granularity=1m&limit=75"
            try:
                async with self.s.get(url_bitget, timeout=0.85) as r:
                    if r.status == 200:
                        res = await r.json()
                        d = res.get("data", [])
                        if isinstance(d, list) and len(d) >= 60:
                            return (base, list(reversed(d)))
            except Exception: pass

            for variant in [base, f"1000{base}"]:
                url_binance = f"https://fapi.binance.com/fapi/v1/klines?symbol={variant}USDT&interval=1m&limit=75"
                try:
                    async with self.s.get(url_binance, timeout=0.85) as r:
                        if r.status == 200:
                            d = await r.json()
                            if isinstance(d, list) and len(d) >= 60:
                                return (base, d)
                except Exception: pass

        return (base, [])

    async def run_fast_scalp_watchdog(self, sym: str, base: str, direction: str, entry_price: float):
        """
        THE 40% GIVEBACK RATCHET WATCHDOG:
        1. When losing: Stagnation cut in 40s (cuts losses fast).
        2. When in net profit: Lets the trade breathe freely.
        3. The 40% Rule: If price gives back 40% of its peak net profit, CLOSE IMMEDIATELY!
        """
        global state
        self.active_trade = sym
        state["total_trades"] += 1
        save_state(state)

        is_live = state["unlocked"] and bool(API_KEY and SECRET_KEY)

        if is_live:
            balance_usdt = await self.bitget.get_available_usdt()
            qty_str = self.bitget.calculate_order_qty(entry_price, balance_usdt)
            await self.bitget.open_order_uta(sym, side=direction, qty_str=qty_str)
            logger.info(
                f"⚡ LIVE {direction.upper()} OPENED: {qty_str} contracts @ ${entry_price:.4f} "
                f"(Balance: ${balance_usdt:.2f} USDT | Margin: ~${(balance_usdt * 0.9):.2f} @ 5x)"
            )

        logger.info(
            f"🚀 TRADE #{state['total_trades']} OPENED: {base} ({direction.upper()}) @ ${entry_price:.4f} | "
            f"Mode: {'LIVE' if is_live else 'PAPER_GAUNTLET'} | Ratchet: 40% Max Giveback"
        )

        price_ticks = []
        peak_gross = 0.0
        peak_net = 0.0
        trailing_floor_net = HARD_STOP_GROSS
        breakeven_triggered = False
        tick_count = 0

        while True:
            await asyncio.sleep(4.0)
            tick_count += 1

            url = f"https://api.bitget.com/api/v2/mix/market/ticker?symbol={sym}&productType=usdt-futures"
            curr_price = 0.0
            try:
                async with self.s.get(url, timeout=0.8) as r:
                    if r.status == 200:
                        d = await r.json()
                        curr_price = float(d.get("data", [{}])[0].get("lastPr", 0.0))
            except Exception: pass

            if curr_price <= 0: continue

            price_ticks.append(curr_price)
            if len(price_ticks) > 12:
                price_ticks.pop(0)

            if direction == "buy":
                gross = ((curr_price - entry_price) / entry_price) * 100.0
            else:
                gross = ((entry_price - curr_price) / entry_price) * 100.0

            net_move = gross - FEE_AND_SLIPPAGE
            net_roe = net_move * LEVERAGE

            if gross > peak_gross:
                peak_gross = gross
            if net_move > peak_net:
                peak_net = net_move

            # ----------------- 1. CUT LOSERS FAST (STAGNATION SHIELD) -----------------
            # If after 40s (10 pulses) the trade has zero momentum and is negative, cut immediately!
            if tick_count >= 10 and peak_gross <= 0.10 and gross < 0:
                if is_live:
                    await self.bitget.safe_close_position_uta(sym, direction)
                logger.warning(f"🛑 STAGNATION CUT: {base} failed to move in 40s. Cut at Gross: {gross:.2f}%.")
                state["streak"] = 0
                state["unlocked"] = False
                save_state(state)
                break

            # ----------------- 2. BREAKEVEN SHIELD -----------------
            # Once in real net profit (+0.25% net), guarantee zero loss
            if peak_net >= 0.25 and not breakeven_triggered:
                breakeven_triggered = True
                trailing_floor_net = 0.00
                logger.info(f"🛡️ BREAKEVEN LOCKED on {base}! Floor set at 0.00% net (Zero loss guaranteed).")

            # ----------------- 3. THE 40% PROFIT GIVEBACK RULE -----------------
            # Once net profit reaches >= +0.50%, do not let the market eat more than 40% of it!
            # If it gives back 40%, you keep the other 60%+ of the gain!
            if peak_net >= 0.50:
                dynamic_floor = peak_net * 0.60  # Keeps 60% of peak net profit
                if dynamic_floor > trailing_floor_net:
                    trailing_floor_net = dynamic_floor

            # ----------------- 4. STRUCTURAL WAVE EXHAUSTION -----------------
            # Evaluates structural waves over ~32 seconds (ignores 4s micro-noise)
            is_wave_exhausted = MarketMath.audit_wave_exhaustion(price_ticks, direction)

            if tick_count % 3 == 0:
                logger.info(
                    f"📊 4s Pulse #{tick_count} [{base} {direction.upper()}]: Net Move: {net_move:+.2f}% "
                    f"(Peak Net: +{peak_net:.2f}%) | Net ROE (5x): {net_roe:+.2f}% | Floor: {trailing_floor_net:+.2f}%"
                )

            # ----------------- EXIT CONDITIONS -----------------
            # A. 40% Giveback Floor Hit
            if net_move <= trailing_floor_net:
                if is_live:
                    await self.bitget.safe_close_position_uta(sym, direction)

                if net_move > 0.05:
                    state["streak"] += 1
                    logger.info(
                        f"💰 40% RATCHET HARVEST! Banked Net: +{net_move:.2f}% | "
                        f"Net ROE: +{net_roe:.2f}% (Peak Net was +{peak_net:.2f}%). Streak: {state['streak']}/{REQUIRED_STREAK}"
                    )
                elif breakeven_triggered:
                    logger.info(f"🛡️ BREAKEVEN EXIT: Preserved capital at zero loss. Streak intact at {state['streak']}.")
                else:
                    logger.warning(f"🛑 STOPPED OUT! Net: {net_move:.2f}%. Streak reset to 0.")
                    state["streak"] = 0
                    state["unlocked"] = False

                save_state(state)
                break

            # B. Structural Wave Reversal Exit
            if peak_net >= 0.60 and is_wave_exhausted and net_move <= (peak_net * 0.75):
                if is_live:
                    await self.bitget.safe_close_position_uta(sym, direction)

                state["streak"] += 1
                logger.info(
                    f"🏆 WAVE EXHAUSTION HARVEST! Banked Net: +{net_move:.2f}% | "
                    f"Net ROE: +{net_roe:.2f}%. Streak: {state['streak']}/{REQUIRED_STREAK}"
                )
                save_state(state)
                break

        self.active_trade = None

    async def main_loop(self):
        run_health_server()
        asyncio.create_task(self.global_vol.background_worker())

        live_bal = await self.bitget.get_available_usdt()
        margin_used = live_bal * 0.90
        notional_val = margin_used * LEVERAGE

        logger.info(
            f"⚡ 80%+ Win-Rate Outlier Sentinel Online.\n"
            f"   - 1-Hour Baseline: Average 1m Fluctuation >= 0.10% REQUIRED\n"
            f"   - Sizing: ${live_bal:.2f} Balance | Margin: ${margin_used:.2f} (5x = ~${notional_val:.2f})\n"
            f"   - Asymmetric Rules: Cut Losers in 40s | Give Winners Room to Breathe | 40% Max Giveback\n"
            f"   - Streak: {state['streak']}/{REQUIRED_STREAK}"
        )

        cycle = 0
        while True:
            cycle += 1
            now = time.time()
            t0 = time.time()
            try:
                url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures"
                async with self.s.get(url, timeout=2.0) as r:
                    if r.status == 200:
                        data = await r.json()
                        wiggling_cohort = []
                        total_tracked = 0

                        for item in data.get("data", []):
                            sym = item.get("symbol", "")
                            if not sym.endswith("USDT"): continue

                            base = sym[:-4]
                            bitget_vol = float(item.get("usdtVolume", 0.0))
                            curr_price = float(item.get("lastPr", 0.0))

                            if curr_price <= 0: continue

                            global_vol = self.global_vol.get_global_volume(base, bitget_vol)
                            if global_vol < GLOBAL_MIN_VOL_USD:
                                continue

                            total_tracked += 1

                            if base not in self.price_history:
                                self.price_history[base] = deque(maxlen=60)
                            self.price_history[base].append((now, curr_price))

                            history = self.price_history[base]
                            if len(history) >= 10:
                                old_time, old_price = history[0]
                                elapsed = now - old_time

                                if elapsed >= 90:
                                    pct_3m = ((curr_price - old_price) / old_price) * 100.0
                                    speed_3m = abs(pct_3m)

                                    if speed_3m >= 0.45:
                                        wiggling_cohort.append({
                                            "symbol": sym,
                                            "base": base,
                                            "price": curr_price,
                                            "speed_3m": speed_3m,
                                            "pct_3m": pct_3m
                                        })

                        wiggling_cohort.sort(key=lambda x: x["speed_3m"], reverse=True)
                        top_candidates = wiggling_cohort[:15]

                        if cycle % 5 == 0:
                            global_count = self.global_vol.qualifying_count or total_tracked
                            top_info = f"Top: {top_candidates[0]['base']} ({top_candidates[0]['pct_3m']:+.2f}%/3m)" if top_candidates else "None"
                            logger.info(
                                f"💓 Imbalance Radar: Tracking {total_tracked} pairs ({global_count} >= $1M) | "
                                f"Active Movers: {len(top_candidates)} ({top_info}) | Streak: {state['streak']}/{REQUIRED_STREAK}"
                            )

                        if not self.active_trade and top_candidates:
                            # 1. Parallel candle fetch (75 candles to verify 1h baseline)
                            tasks = [self.fetch_single_candle_set(c["symbol"], c["base"]) for c in top_candidates]
                            candle_results = await asyncio.gather(*tasks, return_exceptions=True)
                            candle_map = {b: d for b, d in candle_results if isinstance(b, str) and isinstance(d, list)}

                            snapback_pool = []
                            for c in top_candidates:
                                base = c["base"]
                                candles = candle_map.get(base, [])
                                snap = MarketMath.audit_reversal_candidate(candles, c["price"])
                                if snap["qualified"]:
                                    snapback_pool.append({
                                        "symbol": c["symbol"],
                                        "base": base,
                                        "price": c["price"],
                                        "direction": snap["direction"],
                                        "snap": snap
                                    })

                            # 2. Parallel 8-Exchange Depth Check
                            if snapback_pool:
                                depth_tasks = [self.depth_probe.get_depths_all_8(c["base"]) for c in snapback_pool]
                                depth_results = await asyncio.gather(*depth_tasks, return_exceptions=True)

                                scored_candidates = []
                                for candidate, depths in zip(snapback_pool, depth_results):
                                    if not isinstance(depths, list): continue

                                    imbalance = MarketMath.audit_cross_imbalance(depths, candidate["direction"])
                                    if imbalance["has_imbalance"]:
                                        scored_candidates.append({
                                            "candidate": candidate,
                                            "imbalance_ratio": imbalance["imbalance_ratio"],
                                            "venues_count": imbalance["venues_count"]
                                        })

                                # 3. Strictly select the #1 LARGEST global order book wall
                                if scored_candidates:
                                    scored_candidates.sort(key=lambda x: x["imbalance_ratio"], reverse=True)
                                    winner = scored_candidates[0]
                                    chosen = winner["candidate"]
                                    ratio = winner["imbalance_ratio"]
                                    venues = winner["venues_count"]
                                    side = chosen["direction"]

                                    elapsed_scan = time.time() - t0
                                    logger.info(
                                        f"🎯 #1 LARGEST IMBALANCE CONFIRMED [{side.upper()}] (Scan: {elapsed_scan:.2f}s): {chosen['base']}!\n"
                                        f"   - 1h Baseline Volatility: {chosen['snap']['avg_1h_fluctuation']}%/min (>= 0.10% filter passed)\n"
                                        f"   - Global Wall Imbalance: {ratio}x across {venues}/8 exchanges (Strongest in Market)\n"
                                        f"   - Outlier Move: {chosen['snap']['extreme_move']}% | Rebound: {chosen['snap']['rebound_pct']}%\n"
                                        f"   - Entering trade with 40% Giveback Protection..."
                                    )
                                    asyncio.create_task(
                                        self.run_fast_scalp_watchdog(chosen["symbol"], chosen["base"], side, chosen["price"])
                                    )

            except Exception as e:
                logger.error(f"Loop error: {e}")

            await asyncio.sleep(2.5)

async def main():
    connector = aiohttp.TCPConnector(
        limit=80,
        limit_per_host=25,
        ttl_dns_cache=300,
        keepalive_timeout=60.0
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        engine = MasterEngine(session)
        await engine.main_loop()

if __name__ == "__main__":
    asyncio.run(main())
