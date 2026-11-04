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
from http.server import HTTPServer, BaseHTTPRequestHandler
import aiohttp

from market_math import MarketMath

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GlobalSentinel")

# Option B: Reads either variable name format from Render dashboard
API_KEY = os.getenv("API_KEY") or os.getenv("BITGET_API_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("BITGET_API_SECRET", "")
PASSPHRASE = os.getenv("PASSPHRASE") or os.getenv("BITGET_API_PASSPHRASE", "")
PORT = int(os.getenv("PORT", 10000))

# ----------------- CONSTANTS -----------------
LEVERAGE = 5
FEE_AND_SPREAD = 0.17           # 0.12% fees + 0.05% spread
TARGET_NET_MOVE = 1.50          # +1.50% Net Move = +7.50% Net ROE at 5x
HARD_STOP_GROSS = -0.50         # Stop Loss at -0.50% gross (1:3 Risk/Reward)
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

# ----------------- RENDER KEEP-ALIVE SERVER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ONLINE",
            "mode": "LIVE" if state["unlocked"] else "PAPER_GAUNTLET",
            "streak": f"{state['streak']}/{REQUIRED_STREAK}",
            "trades": state["total_trades"],
            "one_way_mode": True,
            "reduce_only": True
        }).encode("utf-8"))
    def log_message(self, *args): pass

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# ----------------- BITGET V2 CLIENT (ONE-WAY & REDUCE-ONLY) -----------------
class BitgetClient:
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

    async def setup_one_way_mode(self, symbol: str):
        """Enforces One-Way Mode (non-hedged) & Isolated 5x leverage on Bitget."""
        if not API_KEY or not SECRET_KEY:
            return
        path = "/api/v2/mix/account/set-position-mode"
        payload = json.dumps({"productType": "usdt-futures", "posMode": "one_way_mode"})
        try:
            headers = self._headers("POST", path, payload)
            await self.s.post(self.base_url + path, data=payload, headers=headers, timeout=2.0)
        except Exception: pass

        lev_path = "/api/v2/mix/account/set-leverage"
        lev_payload = json.dumps({"symbol": symbol, "productType": "usdt-futures", "marginCoin": "USDT", "leverage": str(LEVERAGE)})
        try:
            h = self._headers("POST", lev_path, lev_payload)
            await self.s.post(self.base_url + lev_path, data=lev_payload, headers=h, timeout=2.0)
        except Exception: pass

    async def open_market_long(self, symbol: str, size: float) -> bool:
        """Opens Long Position in One-Way Mode."""
        path = "/api/v2/mix/order/place-order"
        payload = json.dumps({
            "symbol": symbol,
            "productType": "usdt-futures",
            "marginMode": "isolated",
            "marginCoin": "USDT",
            "size": str(size),
            "side": "buy",
            "orderType": "market",
            "tradeSide": "open"
        })
        try:
            headers = self._headers("POST", path, payload)
            async with self.s.post(self.base_url + path, data=payload, headers=headers, timeout=2.0) as r:
                res = await r.json()
                return res.get("code") == "00000"
        except Exception: return False

    async def close_market_long_reduce_only(self, symbol: str, size: float) -> bool:
        """Closes Long Position strictly using REDUCE-ONLY in One-Way Mode."""
        path = "/api/v2/mix/order/place-order"
        payload = json.dumps({
            "symbol": symbol,
            "productType": "usdt-futures",
            "marginMode": "isolated",
            "marginCoin": "USDT",
            "size": str(size),
            "side": "sell",
            "orderType": "market",
            "tradeSide": "close",
            "reduceOnly": "yes"    # <--- Enforces Reduce-Only
        })
        for _ in range(3):
            try:
                headers = self._headers("POST", path, payload)
                async with self.s.post(self.base_url + path, data=payload, headers=headers, timeout=2.0) as r:
                    res = await r.json()
                    if res.get("code") == "00000":
                        logger.info(f"🔒 Position closed cleanly on Bitget with REDUCE-ONLY: {symbol}")
                        return True
            except Exception: pass
            await asyncio.sleep(0.5)
        return False

# ----------------- PARALLEL 8-EXCHANGE PROBE (<250ms) -----------------
class EightExchangeProbe:
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

    async def _okx(self, base: str):
        try:
            url = f"https://www.okx.com/api/v5/market/books?instId={base}-USDT-SWAP&sz=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", [{}])[0]
                    # Sanitizes OKX's 4-item list to [price, size]
                    bids = [[x[0], x[1]] for x in d.get("bids", []) if len(x) >= 2]
                    asks = [[x[0], x[1]] for x in d.get("asks", []) if len(x) >= 2]
                    return ("okx", bids, asks)
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

# ----------------- MAIN SCANNER & EXECUTION LOOP -----------------
class MasterEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.probe = EightExchangeProbe(session)
        self.bitget = BitgetClient(session)
        self.highs_30m = {}
        self.active_trade = None

    async def scan_market_breakouts(self) -> list:
        url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures"
        breakouts = []
        try:
            async with self.s.get(url, timeout=2.5) as r:
                if r.status == 200:
                    data = await r.json()
                    for item in data.get("data", []):
                        sym = item.get("symbol", "")
                        if not sym.endswith("USDT"): continue

                        vol = float(item.get("usdtVolume", 0.0))
                        curr_price = float(item.get("lastPr", 0.0))
                        base = sym[:-4]

                        if vol < 1_000_000.0 or curr_price <= 0:
                            continue

                        if base not in self.highs_30m:
                            self.highs_30m[base] = curr_price
                        else:
                            self.highs_30m[base] = max(self.highs_30m[base], curr_price)

                        if MarketMath.audit_15m_breakout(curr_price, self.highs_30m[base], vol):
                            breakouts.append({"symbol": sym, "base": base, "price": curr_price, "vol": vol})
        except Exception: pass
        return breakouts

    async def fetch_5m_flow(self, base: str) -> list:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={base}USDT&interval=1m&limit=5"
        try:
            async with self.s.get(url, timeout=1.2) as r:
                if r.status == 200:
                    return await r.json()
        except Exception: pass
        return []

    async def run_midrange_watchdog(self, sym: str, base: str, entry_price: float):
        global state
        self.active_trade = sym
        state["total_trades"] += 1
        save_state(state)

        is_live = state["unlocked"] and bool(API_KEY and SECRET_KEY)

        if is_live:
            await self.bitget.setup_one_way_mode(sym)
            await self.bitget.open_market_long(sym, size=1.0)
            logger.info(f"⚡ LIVE ORDER OPENED (One-Way Mode): {sym} at 5x")

        logger.info(
            f"🚀 TRADE #{state['total_trades']} OPENED: {base} @ ${entry_price:.4f} | "
            f"Mode: {'LIVE' if is_live else 'PAPER_GAUNTLET'} | Streak: {state['streak']}/{REQUIRED_STREAK}"
        )

        for cycle in range(1, 31):  # 30 cycles * 20s = 600s (10-minute maximum hold)
            await asyncio.sleep(20.0)

            url = f"https://api.bitget.com/api/v2/mix/market/ticker?symbol={sym}&productType=usdt-futures"
            curr_price = 0.0
            try:
                async with self.s.get(url, timeout=1.0) as r:
                    if r.status == 200:
                        d = await r.json()
                        curr_price = float(d.get("data", [{}])[0].get("lastPr", 0.0))
            except Exception: pass

            if curr_price <= 0: continue

            gross = ((curr_price - entry_price) / entry_price) * 100.0
            net_move = gross - FEE_AND_SPREAD
            net_roe = net_move * LEVERAGE

            logger.info(
                f"⏱️ {(cycle * 20)}s [{base}]: Gross: {gross:+.2f}% | "
                f"Net Move: {net_move:+.2f}% | Net ROE (5x): {net_roe:+.2f}%"
            )

            # ----------------- 1. WIN TARGET (+1.50% Net Move = +7.50% Net ROE) -----------------
            if net_move >= TARGET_NET_MOVE:
                if is_live:
                    await self.bitget.close_market_long_reduce_only(sym, size=1.0)
                state["streak"] += 1
                logger.info(f"🏆 BIG WIN #{state['streak']} BANKED! Net ROE: +{net_roe:.2f}% (Gross: +{gross:.2f}%)")
                if state["streak"] >= REQUIRED_STREAK:
                    state["unlocked"] = True
                    logger.info("🚨 8 CONSECUTIVE 7.5% ROE WINS ACHIEVED! LIVE TRADING UNLOCKED! 🚨")
                save_state(state)
                break

            # ----------------- 2. HARD STOP LOSS (-0.50% Gross) -----------------
            if gross <= HARD_STOP_GROSS:
                if is_live:
                    await self.bitget.close_market_long_reduce_only(sym, size=1.0)
                logger.warning(f"🛑 STOPPED OUT! Gross: {gross:.2f}%. Streak reset to 0.")
                state["streak"] = 0
                state["unlocked"] = False
                save_state(state)
                break

            # ----------------- 3. TIMEOUT (10 Minutes) -----------------
            if cycle == 30:
                if is_live:
                    await self.bitget.close_market_long_reduce_only(sym, size=1.0)
                if net_move >= TARGET_NET_MOVE:
                    state["streak"] += 1
                    logger.info(f"🏆 WIN #{state['streak']} BANKED ON TIMEOUT!")
                else:
                    logger.info(f"⏱️ 10m Window Expired (+{net_move:.2f}%). Streak reset to 0.")
                    state["streak"] = 0
                    state["unlocked"] = False
                save_state(state)
                break

        self.active_trade = None

    async def main_loop(self):
        run_health_server()
        logger.info(
            f"⚡ 8-Exchange Mid-Range Sentinel Online.\n"
            f"   - Target: +1.50% Net (+7.50% ROE at 5x)\n"
            f"   - Venues: Binance, OKX, Bybit, Gate, MEXC, KuCoin, BingX, Hyperliquid\n"
            f"   - One-Way Mode: ENFORCED | Close: REDUCE-ONLY\n"
            f"   - Streak: {state['streak']}/{REQUIRED_STREAK}"
        )
        cycle = 0

        while True:
            cycle += 1
            try:
                if not self.active_trade:
                    breakouts = await self.scan_market_breakouts()

                    if cycle % 4 == 0:
                        logger.info(f"💓 Breakout Radar: Tracking {len(self.highs_30m)} coins | Breakout Candidates: {len(breakouts)}")

                    for coin in breakouts:
                        base = coin["base"]

                        candles = await self.fetch_5m_flow(base)
                        fuel = MarketMath.calculate_5m_fuel(candles)

                        if not fuel["has_fuel"]:
                            continue

                        # Queries all 8 exchanges in parallel
                        depths = await self.probe.get_depths_all_8(base)
                        runway = MarketMath.audit_runway_clearance(depths, fuel["net_inflow_5m"])

                        if runway["has_runway"]:
                            logger.info(
                                f"🎯 +1.5% RUNWAY CONFIRMED: {base}!\n"
                                f"   - 5m Net Inflow: ${fuel['net_inflow_5m']:,.0f}\n"
                                f"   - Resting Wall (+1.5% zone): ${runway['wall_usd']:,.0f}\n"
                                f"   - Clearance: {runway['clearance_ratio']}x across {runway['venues_count']}/8 exchanges"
                            )
                            await self.run_midrange_watchdog(coin["symbol"], base, coin["price"])
                            break

            except Exception as e:
                logger.error(f"Loop error: {e}")

            await asyncio.sleep(12.0)

async def main():
    connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        engine = MasterEngine(session)
        await engine.main_loop()

if __name__ == "__main__":
    asyncio.run(main())
