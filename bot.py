# bot.py
import os
import json
import time
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import aiohttp

from market_math import MarketMath

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MidRangeEngine")

# Option B: Reads either variable name format
API_KEY = os.getenv("API_KEY") or os.getenv("BITGET_API_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("BITGET_API_SECRET", "")
PASSPHRASE = os.getenv("PASSPHRASE") or os.getenv("BITGET_API_PASSPHRASE", "")
PORT = int(os.getenv("PORT", 10000))

# ----------------- MID-RANGE TARGET CONSTANTS -----------------
LEVERAGE = 5
FEE_AND_SPREAD = 0.17           # 0.12% fees + 0.05% spread
TARGET_NET_MOVE = 1.50          # +1.50% Net Price Move = +7.50% Net ROE at 5x
HARD_STOP_GROSS = -0.50         # Stop Loss at -0.50% (1:3 Risk/Reward ratio)
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

# ----------------- RENDER HEALTH SERVER -----------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ONLINE",
            "mode": "MID_RANGE_MOMENTUM (+1.5% TARGET)",
            "streak": f"{state['streak']}/{REQUIRED_STREAK}",
            "trades": state["total_trades"]
        }).encode("utf-8"))
    def log_message(self, *args): pass

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# ----------------- PARALLEL ORDER BOOK READER -----------------
class MultiExchangeProbe:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session

    async def _binance_depth(self, base: str):
        try:
            url = f"https://fapi.binance.com/fapi/v1/depth?symbol={base}USDT&limit=50"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = await r.json()
                    return ("binance", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _bybit_depth(self, base: str):
        try:
            url = f"https://api.bybit.com/v5/market/orderbook?category=linear&symbol={base}USDT&limit=50"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("result", {})
                    return ("bybit", d.get("b", []), d.get("a", []))
        except Exception: pass
        return None

    async def _bitget_depth(self, base: str):
        try:
            url = f"https://api.bitget.com/api/v2/mix/market/orderbook?symbol={base}USDT&productType=usdt-futures&limit=50"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    return ("bitget", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def get_depths(self, base: str) -> list:
        tasks = [self._binance_depth(base), self._bybit_depth(base), self._bitget_depth(base)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, tuple) and r is not None]

# ----------------- MASTER ENGINE -----------------
class MidRangeEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.probe = MultiExchangeProbe(session)
        self.highs_30m = {}  # base -> highest price in 30m window
        self.active_trade = None

    async def scan_market_breakouts(self) -> list:
        """
        Scans all 400+ coins in a single batch call.
        Finds coins breaking 30m highs with > $1M 24h volume.
        """
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
                        high_price = float(item.get("high24h", 0.0))
                        base = sym[:-4]

                        if vol < 1_000_000.0 or curr_price <= 0:
                            continue

                        # Keep track of local high
                        if base not in self.highs_30m:
                            self.highs_30m[base] = curr_price
                        else:
                            self.highs_30m[base] = max(self.highs_30m[base], curr_price)

                        # Check breakout
                        if MarketMath.audit_15m_breakout(curr_price, self.highs_30m[base], vol):
                            breakouts.append({
                                "symbol": sym,
                                "base": base,
                                "price": curr_price,
                                "vol": vol
                            })
        except Exception as e:
            logger.error(f"Batch scan error: {e}")

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

        logger.info(
            f"🚀 MID-RANGE TRADE #{state['total_trades']} OPENED: {base} @ ${entry_price:.4f} | "
            f"Target: +1.50% Net (+7.50% ROE) | Streak: {state['streak']}/{REQUIRED_STREAK}"
        )

        # 30 cycles * 20s = 600s (10-minute maximum hold window)
        for cycle in range(1, 31):
            await asyncio.sleep(20.0)

            # Query current price
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

            # ----------------- 1. TARGET WIN (+1.50% Net Move = +7.50% Net ROE) -----------------
            if net_move >= TARGET_NET_MOVE:
                state["streak"] += 1
                logger.info(f"🏆 BIG WIN #{state['streak']} BANKED! Net ROE: +{net_roe:.2f}% (Gross: +{gross:.2f}%)")
                if state["streak"] >= REQUIRED_STREAK:
                    state["unlocked"] = True
                    logger.info("🚨 8 CONSECUTIVE 7.5% ROE WINS ACHIEVED! LIVE UNLOCKED! 🚨")
                save_state(state)
                break

            # ----------------- 2. STRICT STOP LOSS (-0.50% Gross) -----------------
            if gross <= HARD_STOP_GROSS:
                logger.warning(f"🛑 STOPPED OUT! Gross: {gross:.2f}%. Streak reset.")
                state["streak"] = 0
                state["unlocked"] = False
                save_state(state)
                break

            # ----------------- 3. TIMEOUT (10 Minutes) -----------------
            if cycle == 30:
                if net_move >= TARGET_NET_MOVE:
                    state["streak"] += 1
                    logger.info(f"🏆 WIN #{state['streak']} BANKED ON TIMEOUT!")
                else:
                    logger.info(f"⏱️ 10m Momentum window closed (+{net_move:.2f}%). Streak reset.")
                    state["streak"] = 0
                    state["unlocked"] = False
                save_state(state)
                break

        self.active_trade = None

    async def main_loop(self):
        run_health_server()
        logger.info(f"⚡ Mid-Range Sentinel Online. Target: +1.50% Net (+7.50% ROE). Streak: {state['streak']}/{REQUIRED_STREAK}")
        cycle = 0

        while True:
            cycle += 1
            try:
                if not self.active_trade:
                    # 1. Scan all 400+ coins in 1 single HTTP request
                    breakouts = await self.scan_market_breakouts()

                    if cycle % 4 == 0:
                        logger.info(f"💓 Breakout Radar: Tracking {len(self.highs_30m)} coins | Breakout Candidates: {len(breakouts)}")

                    for coin in breakouts:
                        base = coin["base"]

                        # 2. Check 5-minute Taker Buy Inflow
                        candles = await self.fetch_5m_flow(base)
                        fuel = MarketMath.calculate_5m_fuel(candles)

                        if not fuel["has_fuel"]:
                            continue

                        # 3. Check Order Book Highway (Is +1.5% clear of sell walls?)
                        depths = await self.probe.get_depths(base)
                        runway = MarketMath.audit_runway_clearance(depths, fuel["net_inflow_5m"])

                        if runway["has_runway"]:
                            logger.info(
                                f"🎯 +1.5% RUNWAY CONFIRMED: {base}!\n"
                                f"   - 5m Net Inflow: ${fuel['net_inflow_5m']:,.0f}\n"
                                f"   - Resting Wall (+1.5% zone): ${runway['wall_usd']:,.0f}\n"
                                f"   - Clearance Ratio: {runway['clearance_ratio']}x across {runway['venues_count']} exchanges"
                            )
                            await self.run_midrange_watchdog(coin["symbol"], base, coin["price"])
                            break

            except Exception as e:
                logger.error(f"Loop error: {e}")

            await asyncio.sleep(12.0)

async def main():
    connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        engine = MidRangeEngine(session)
        await engine.main_loop()

if __name__ == "__main__":
    asyncio.run(main())
