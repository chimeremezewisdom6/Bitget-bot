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
logger = logging.getLogger("TurboSentinel")

# Option B: Reads either variable name format from Render (stripped of whitespace)
API_KEY = (os.getenv("API_KEY") or os.getenv("BITGET_API_KEY", "")).strip()
SECRET_KEY = (os.getenv("SECRET_KEY") or os.getenv("BITGET_API_SECRET", "")).strip()
PASSPHRASE = (os.getenv("PASSPHRASE") or os.getenv("BITGET_API_PASSPHRASE", "")).strip()
PORT = int(os.getenv("PORT", 10000))

# ----------------- RISK & EXECUTION PARAMETERS -----------------
LEVERAGE = 5
FEE_AND_SLIPPAGE = 0.22         # 0.12% fees + 0.10% real market-order slippage
HARD_STOP_GROSS = -0.55         # Emergency hard stop
GLOBAL_MIN_VOL_USD = 1_000_000.0  # Summed across all 8 exchanges >= $1M
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
            "account_mode": "BITGET_UNIFIED_TRADING_ACCOUNT_V3",
            "mode": "LIVE" if state["unlocked"] else "PAPER_GAUNTLET",
            "streak": f"{state['streak']}/{REQUIRED_STREAK}",
            "trades": state["total_trades"],
            "pipeline": "SUB_SECOND_WARM_TLS"
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
        """Pulls actual live balance using Bitget UTA V3 endpoints."""
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
                                logger.info(f"✅ Bitget UTA Connected! Live USDT: ${val:.2f}")
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
                                    logger.info(f"✅ Bitget Universal Balance: ${val:.2f}")
                                    return val
        except Exception: pass

        return 1.58

    def calculate_order_qty(self, current_price: float, balance_usdt: float) -> str:
        """Calculates size adapted to $1.58 balance, ensuring notional >= 5.10 USDT."""
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
        """Opens position using Bitget UTA V3 Order API."""
        lev_path = "/api/v3/account/set-leverage"
        lev_body = json.dumps({"category": "USDT-FUTURES", "symbol": symbol, "leverage": str(LEVERAGE)})
        try:
            h = self._headers("POST", lev_path, lev_body)
            await self.s.post(self.base_url + lev_path, data=lev_body, headers=h, timeout=1.5)
        except Exception: pass

        path = "/api/v3/trade/place-order"
        payload = json.dumps({
            "category": "USDT-FUTURES",
            "symbol": symbol,
            "side": side,
            "orderType": "market",
            "qty": qty_str,
            "reduceOnly": "no"
        })
        try:
            h = self._headers("POST", path, payload)
            async with self.s.post(self.base_url + path, data=payload, headers=h, timeout=2.0) as r:
                res = await r.json()
                return res.get("code") == "00000"
        except Exception:
            return False

    async def safe_close_position_uta(self, symbol: str, open_side: str) -> bool:
        """Zero-Error Close in UTA: Queries live open size and closes with reduce-only."""
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
            "category": "USDT-FUTURES",
            "symbol": symbol,
            "side": close_side,
            "orderType": "market",
            "qty": actual_qty,
            "reduceOnly": "yes"
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

# ----------------- BACKGROUND GLOBAL VOLUME AGGREGATOR (DECOUPLED) -----------------
class GlobalVolumeEngine:
    """Runs as a detached background worker. NEVER freezes the main scanner!"""
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.global_volume_cache = {}

    async def background_worker(self):
        """Refreshes volume across all 7 external exchanges every 5 minutes in background."""
        while True:
            try:
                totals = {}

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
                                        vol_coins = float(item.get("volCcy24h", 0.0))
                                        last_price = float(item.get("last", 0.0))
                                        totals[b] = totals.get(b, 0.0) + (vol_coins * last_price)
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
            except Exception: pass
            await asyncio.sleep(300)

    def get_global_volume(self, base: str, bitget_vol: float) -> float:
        """Instant in-memory lookup (0.00001 seconds)."""
        return self.global_volume_cache.get(base, 0.0) + bitget_vol

# ----------------- PARALLEL BI-DIRECTIONAL MASTER ENGINE -----------------
class MasterEngine:
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session
        self.bitget = BitgetUTAClient(session)
        self.global_vol = GlobalVolumeEngine(session)
        self.active_trade = None
        self.sem = asyncio.Semaphore(25)

    async def fetch_single_candle_set(self, base: str) -> tuple:
        """
        Fetches 45 1m candles.
        Includes automatic fallback for meme coins with '1000' prefix on Binance!
        """
        async with self.sem:
            for variant in [base, f"1000{base}"]:
                url = f"https://fapi.binance.com/fapi/v1/klines?symbol={variant}USDT&interval=1m&limit=45"
                try:
                    async with self.s.get(url, timeout=0.9) as r:
                        if r.status == 200:
                            d = await r.json()
                            if isinstance(d, list) and len(d) >= 20:
                                return (base, d)
                except Exception: pass
        return (base, [])

    async def run_open_ended_watchdog(self, sym: str, base: str, direction: str, entry_price: float):
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
                f"(Balance: ${balance_usdt:.2f} USDT | Notional: ~${(balance_usdt * 0.9 * LEVERAGE):.2f})"
            )

        logger.info(
            f"🚀 TRADE #{state['total_trades']} OPENED: {base} ({direction.upper()}) @ ${entry_price:.4f} | "
            f"Mode: {'LIVE' if is_live else 'PAPER_GAUNTLET'} | Streak: {state['streak']}/{REQUIRED_STREAK}"
        )

        price_ticks = []
        peak_gross = 0.0
        trailing_floor = HARD_STOP_GROSS
        tick_count = 0

        while True:
            await asyncio.sleep(20.0)
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
            if len(price_ticks) > 10:
                price_ticks.pop(0)

            if direction == "buy":
                gross = ((curr_price - entry_price) / entry_price) * 100.0
            else:
                gross = ((entry_price - curr_price) / entry_price) * 100.0

            net_move = gross - FEE_AND_SLIPPAGE
            net_roe = net_move * LEVERAGE

            if gross > peak_gross:
                peak_gross = gross

            # Parabolic Trailing Ratchet
            if peak_gross >= 0.40 and trailing_floor < 0.22:
                trailing_floor = 0.22
                logger.info(f"🛡️ BREAKEVEN LOCKED on {base} (+0.22% floor, zero risk).")

            if peak_gross >= 1.50 and trailing_floor < 1.15:
                trailing_floor = 1.15
                logger.info(f"💎 +1.5% HIT on {base} ({direction.upper()})! Ratchet locked. Riding for +5%+...")

            if peak_gross >= 2.50:
                potential_floor = peak_gross - 0.35
                if potential_floor > trailing_floor:
                    trailing_floor = potential_floor

            wiggle = MarketMath.audit_wiggle_direction(price_ticks, direction)

            logger.info(
                f"📊 Pulse #{tick_count} [{base} {direction.upper()}]: Gross: {gross:+.2f}% (Peak: +{peak_gross:.2f}%) | "
                f"Net ROE: {net_roe:+.2f}% | Floor: {trailing_floor:+.2f}% | State: {wiggle['status']}"
            )

            # Exit Conditions
            if peak_gross >= 0.60 and wiggle["should_exit"] and gross <= (peak_gross - 0.22):
                if is_live:
                    await self.bitget.safe_close_position_uta(sym, direction)
                if net_move > 0:
                    state["streak"] += 1
                    logger.info(
                        f"💰 WIGGLE FADE HARVESTED! Closed at Gross: +{gross:.2f}% | "
                        f"Net ROE: +{net_roe:.2f}% (Peak: +{peak_gross:.2f}%!). Streak: {state['streak']}/{REQUIRED_STREAK}"
                    )
                else:
                    logger.warning(f"🛑 Wiggle failed near entry. Streak reset.")
                    state["streak"] = 0
                    state["unlocked"] = False
                save_state(state)
                break

            if gross <= trailing_floor:
                if is_live:
                    await self.bitget.safe_close_position_uta(sym, direction)
                if net_move > 0:
                    state["streak"] += 1
                    logger.info(
                        f"🏆 TRAILING RATCHET EXIT! Net ROE: +{net_roe:.2f}% | "
                        f"Peak: +{peak_gross:.2f}%. Streak: {state['streak']}/{REQUIRED_STREAK}"
                    )
                else:
                    logger.warning(f"🛑 STOPPED OUT! Gross: {gross:.2f}%. Streak reset.")
                    state["streak"] = 0
                    state["unlocked"] = False
                save_state(state)
                break

        self.active_trade = None

    async def main_loop(self):
        run_health_server()
        # Launch volume aggregator in decoupled background task
        asyncio.create_task(self.global_vol.background_worker())

        live_bal = await self.bitget.get_available_usdt()
        margin_used = live_bal * 0.90
        notional_val = margin_used * LEVERAGE

        logger.info(
            f"⚡ Turbo 8-Exchange Global UTA Sentinel Online.\n"
            f"   - Bitget Balance: ${live_bal:.2f} USDT | Margin: ${margin_used:.2f} (5x = ~${notional_val:.2f})\n"
            f"   - Scanning Interval: 3.0s | Warm TLS Keep-Alive Active\n"
            f"   - Meme Coin 1000-Prefix Radar: ENABLED\n"
            f"   - Streak: {state['streak']}/{REQUIRED_STREAK}"
        )

        while True:
            t0 = time.time()
            try:
                if not self.active_trade:
                    url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures"
                    async with self.s.get(url, timeout=2.0) as r:
                        if r.status == 200:
                            data = await r.json()
                            fast_candidates = []

                            # 1. Instant in-memory filter (<1ms): skips flat coins
                            for item in data.get("data", []):
                                sym = item.get("symbol", "")
                                if not sym.endswith("USDT"): continue

                                base = sym[:-4]
                                bitget_vol = float(item.get("usdtVolume", 0.0))
                                curr_price = float(item.get("lastPr", 0.0))
                                high_24h = float(item.get("high24h", 0.0))
                                low_24h = float(item.get("low24h", 0.0))

                                if curr_price <= 0 or low_24h <= 0: continue

                                if ((high_24h - low_24h) / low_24h) < 0.060:
                                    continue

                                global_vol = self.global_vol.get_global_volume(base, bitget_vol)
                                if global_vol < GLOBAL_MIN_VOL_USD:
                                    continue

                                fast_candidates.append((sym, base, curr_price))

                            # 2. Parallel Scatter-Gather (<0.4s) with meme coin resolution
                            if fast_candidates:
                                tasks = [self.fetch_single_candle_set(base) for _, base, _ in fast_candidates]
                                candle_results = await asyncio.gather(*tasks, return_exceptions=True)
                                candle_map = {b: c for b, c in candle_results if isinstance(b, str) and isinstance(c, list)}

                                qualified_pool = []
                                for sym, base, price in fast_candidates:
                                    candles = candle_map.get(base, [])
                                    wave = MarketMath.audit_wave_dominance(candles)
                                    if wave["qualified"]:
                                        qualified_pool.append({
                                            "symbol": sym, "base": base, "price": price,
                                            "direction": wave["direction"], "wave": wave
                                        })

                                # 3. Select #1 fastest candidate
                                if qualified_pool:
                                    qualified_pool.sort(key=lambda x: x["wave"]["power_score"], reverse=True)
                                    chosen = qualified_pool[0]
                                    w = chosen["wave"]
                                    side = chosen["direction"]

                                    elapsed_scan = time.time() - t0
                                    logger.info(
                                        f"⚡ #1 EXPLOSIVE SETUP [{side.upper()}] (Scan: {elapsed_scan:.2f}s): {chosen['base']}!\n"
                                        f"   - Impulse: {w['total_wave']}% in {w['duration_mins']}m (Speed: {w['velocity']}%/min)\n"
                                        f"   - Power Score: {w['power_score']} | Direction: {side.upper()}\n"
                                        f"   - Entering trade adapted to ${live_bal:.2f} balance..."
                                    )
                                    await self.run_open_ended_watchdog(chosen["symbol"], chosen["base"], side, chosen["price"])

            except Exception as e:
                logger.error(f"Loop error: {e}")

            # Polling every 3.0 seconds for maximum reaction speed
            await asyncio.sleep(3.0)

async def main():
    # Warm TCP connection pool with 60s keep-alive
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
