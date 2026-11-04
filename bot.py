# bot.py
import os
import json
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import aiohttp

from market_math import MarketMath, EightExchangeProbe

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GauntletBot")

# Option B: Reads either variable name from Render environment
API_KEY = os.getenv("API_KEY") or os.getenv("BITGET_API_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("BITGET_API_SECRET", "")
PASSPHRASE = os.getenv("PASSPHRASE") or os.getenv("BITGET_API_PASSPHRASE", "")
PORT = int(os.getenv("PORT", 10000))

# ----------------- GAUNTLET PARAMETERS -----------------
LEVERAGE = 5
FEE_AND_SPREAD_DRAG = 0.17       # 0.12% fees + 0.05% spread
TARGET_NET_MOVE = 0.50           # +0.50% Net Move = +2.50% Net ROE at 5x
HARD_STOP_GROSS = -0.40          # -0.40% Gross Move = -2.00% ROE Stop Loss
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
        payload = json.dumps({
            "status": "ONLINE",
            "mode": "LIVE" if state["unlocked"] else "PAPER_GAUNTLET",
            "streak": f"{state['streak']}/{REQUIRED_STREAK}",
            "total_trades": state["total_trades"]
        }).encode("utf-8")
        self.wfile.write(payload)
    def log_message(self, *args): pass

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Render Health Server bound to 0.0.0.0:{PORT}")

# ----------------- MASTER ENGINE -----------------
class MasterEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.probe = EightExchangeProbe(session)
        self.active_trade = None

    async def scan_bitget_top(self) -> list:
        url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures"
        candidates = []
        try:
            async with self.s.get(url, timeout=3.0) as r:
                if r.status == 200:
                    data = await r.json()
                    for item in data.get("data", []):
                        sym = item.get("symbol", "")
                        if sym.endswith("USDT") and float(item.get("usdtVolume", 0.0)) >= 1_000_000.0:
                            candidates.append({
                                "symbol": sym,
                                "base": sym[:-4],
                                "change24h": float(item.get("change24h", 0.0)),
                                "last_price": float(item.get("lastPr", 0.0))
                            })
        except Exception: pass
        candidates.sort(key=lambda x: x["change24h"], reverse=True)
        return candidates[:10]

    async def fetch_flow_candles(self, base: str) -> list:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={base}USDT&interval=1m&limit=15"
        try:
            async with self.s.get(url, timeout=1.5) as r:
                if r.status == 200:
                    return await r.json()
        except Exception: pass
        return []

    async def get_current_price(self, symbol: str) -> float:
        url = f"https://api.bitget.com/api/v2/mix/market/ticker?symbol={symbol}&productType=usdt-futures"
        try:
            async with self.s.get(url, timeout=1.5) as r:
                if r.status == 200:
                    d = await r.json()
                    return float(d.get("data", [{}])[0].get("lastPr", 0.0))
        except Exception: pass
        return 0.0

    async def run_20s_trade_watchdog(self, sym: str, base: str, entry_price: float, initial_buy_force: float):
        global state
        self.active_trade = sym
        state["total_trades"] += 1
        save_state(state)

        logger.info(
            f"🎯 GAUNTLET TRADE #{state['total_trades']} OPENED: {base} @ ${entry_price:.4f} | "
            f"Streak: {state['streak']}/{REQUIRED_STREAK} | Mode: {'LIVE' if state['unlocked'] else 'PAPER'}"
        )

        last_pulse_buy = initial_buy_force / 3.0

        for cycle in range(1, 10):  # 9 cycles * 20s = 180s (3-minute maximum run)
            await asyncio.sleep(20.0)

            curr_price = await self.get_current_price(sym)
            if curr_price <= 0: continue

            gross_move = ((curr_price - entry_price) / entry_price) * 100.0
            net_move = gross_move - FEE_AND_SPREAD_DRAG
            net_roe = net_move * LEVERAGE

            # Query 8 platforms for sell wall absorption
            venues_data = await self.probe.query_all_venues(base)
            sweep_audit = MarketMath.aggregate_8_exchanges(venues_data, initial_buy_force)

            candles = await self.fetch_flow_candles(base)
            curr_pulse_buy = float(candles[-1][10]) / 3.0 if candles else last_pulse_buy

            buyer_fatigued = curr_pulse_buy < (last_pulse_buy * 0.60)
            wall_blocked = sweep_audit["clearance_ratio"] < 0.85

            logger.info(
                f"⏱️ 20s [{base}]: Gross: {gross_move:+.2f}% | Net ROE (5x): {net_roe:+.2f}% | "
                f"Reporting: {sweep_audit['venues_count']}/8 | Wall Ratio: {sweep_audit['clearance_ratio']}x"
            )

            # WIN CONDITION: Net price move >= +0.50% (+2.50% Net ROE at 5x)
            if net_move >= TARGET_NET_MOVE:
                state["streak"] += 1
                logger.info(f"🏆 WIN #{state['streak']} BANKED! Net ROE: +{net_roe:.2f}% (Gross: +{gross_move:.2f}%)")
                if state["streak"] >= REQUIRED_STREAK:
                    state["unlocked"] = True
                    logger.info("🚨 8 CONSECUTIVE WINS ACHIEVED! LIVE TRADING UNLOCKED! 🚨")
                save_state(state)
                break

            # HARD STOP LOSS
            if gross_move <= HARD_STOP_GROSS:
                logger.warning(f"🛑 STOPPED OUT! Gross: {gross_move:.2f}%. Streak reset to 0.")
                state["streak"] = 0
                state["unlocked"] = False
                save_state(state)
                break

            # FADE EXIT: Buyers fatigued or sell wall replenished
            if buyer_fatigued or wall_blocked:
                reason = "BUYERS FATIGUED" if buyer_fatigued else "SELL WALL REPLENISHED"
                logger.warning(f"💨 FADE DETECTED ({reason}) on {base}! Exiting.")
                if net_move < TARGET_NET_MOVE:
                    state["streak"] = 0
                    state["unlocked"] = False
                save_state(state)
                break

            # TIMEOUT EXIT (3 Minutes)
            if cycle == 9:
                logger.warning(f"⏱️ 3-Minute Window Expired. Net Move: +{net_move:.2f}%. Streak reset.")
                state["streak"] = 0
                state["unlocked"] = False
                save_state(state)
                break

            last_pulse_buy = curr_pulse_buy

        self.active_trade = None

    async def main_loop(self):
        run_health_server()
        logger.info(f"⚡ Gauntlet Engine Online. Streak: {state['streak']}/{REQUIRED_STREAK}. RAM < 150 KB.")
        cycle = 0

        while True:
            cycle += 1
            try:
                if not self.active_trade:
                    candidates = await self.scan_bitget_top()

                    if cycle % 4 == 0:
                        logger.info(f"💓 Heartbeat: Streak {state['streak']}/{REQUIRED_STREAK} | Tracking {len(candidates)} coins.")

                    for coin in candidates:
                        base = coin["base"]
                        candles = await self.fetch_flow_candles(base)
                        flow = MarketMath.parse_flow_candles(candles)

                        if not flow or not flow["is_accelerating"] or flow["squeeze_ratio"] < 25.0:
                            continue

                        # Query the Big 8 exchanges in parallel
                        venues_data = await self.probe.query_all_venues(base)
                        sweep = MarketMath.aggregate_8_exchanges(venues_data, flow["last_minute_buy_force"])

                        if sweep["can_sweep"]:
                            logger.info(
                                f"🎯 SQUEEZE DETECTED: {base}!\n"
                                f"   - 5m Move: +{flow['total_5m_move']}%\n"
                                f"   - Locked Ratio: {flow['squeeze_ratio']}%\n"
                                f"   - Clearance: {sweep['clearance_ratio']}x across {sweep['venues_count']}/8 venues: {sweep['reporting_venues']}"
                            )
                            await self.run_20s_trade_watchdog(
                                coin["symbol"], base, coin["last_price"], flow["last_minute_buy_force"]
                            )
                            break
            except Exception as e:
                logger.error(f"Loop error: {e}")

            await asyncio.sleep(15.0)

async def main():
    connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        engine = MasterEngine(session)
        await engine.main_loop()

if __name__ == "__main__":
    asyncio.run(main())
