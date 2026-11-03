import os
import sys
import time
import json
import asyncio
import aiohttp
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt.async_support as ccxt_async
from coinglass_feed import GlobalFeedAggregator, normalize_base

# ----------------- ENVIRONMENT CONFIGURATION -----------------
BITGET_API_KEY = os.getenv("BITGET_API_KEY", "")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET", "")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE", "")
PORT = int(os.getenv("PORT", 10000))

# LEVERAGE & RISK MANAGEMENT
LEVERAGE = 5                    # 5x Leverage: Safe buffer (~19% liquidation distance)
MIN_NOTIONAL_USDT = 5.2         # Bitget requires >= 5.0 USDT order value (clamped at $5.20)
TARGET_NET_WIN_PCT = 1.00       # Strict Gauntlet Target: Must bank >= +1.00% NET profit
REQUIRED_WIN_STREAK = 8         # 8 consecutive wins required to unlock live execution
HARD_STOP_PCT = -0.65           # Hard Stop Loss (-0.65% price move = -3.25% ROE at 5x)
MAX_HOLD_SEC = 300              # Maximum 5 mins in trade (Wave reaches 10m total)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AsymmetricSniper")

system_status = {
    "status": "RUNNING",
    "leverage": f"{LEVERAGE}x",
    "mode": "PAPER_GAUNTLET",
    "streak": "0/8",
    "active_trade": None,
    "last_exit_reason": "None"
}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(system_status).encode('utf-8'))
        except Exception:
            pass

    def log_message(self, format, *args):
        pass

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Render Health Server bound to 0.0.0.0:{PORT}")

# ----------------- DYNAMIC VENUE MATRIX AUDITOR -----------------
class DynamicVenueMatrix:
    def __init__(self):
        # Venues that operate reliably without cloud IP bans
        self.venues = {
            "bitget": ccxt_async.bitget({'options': {'defaultType': 'swap'}}),
            "okx": ccxt_async.okx({'options': {'defaultType': 'swap'}}),
            "bybit": ccxt_async.bybit({'options': {'defaultType': 'linear'}}),
            "gate": ccxt_async.gate({'options': {'defaultType': 'swap'}}),
            "mexc": ccxt_async.mexc({'options': {'defaultType': 'swap'}})
        }
        self.listing_map = {}

    async def initialize(self):
        """Builds venue mapping. Discovers which exchanges trade each asset."""
        for name, client in self.venues.items():
            try:
                markets = await client.load_markets()
                for sym, m in markets.items():
                    if not (m.get('swap', False) or m.get('linear', False)):
                        continue
                    raw_base = m.get('base', '') or sym.split('/')[0].split(':')[0]
                    clean = normalize_base(raw_base)
                    if clean not in self.listing_map:
                        self.listing_map[clean] = {}
                    self.listing_map[clean][name] = sym
            except Exception as e:
                logger.warning(f"Could not load markets for {name}: {e}")

        # Retain only assets available on Bitget
        self.listing_map = {b: v for b, v in self.listing_map.items() if "bitget" in v}
        logger.info(f"Listing Map complete: {len(self.listing_map)} Bitget assets cross-referenced.")

    async def _fetch_binance_depth_ws(self, base: str) -> tuple:
        """Pulls top 20 levels from Binance WebSocket (Zero REST 418 bans)."""
        variants = [f"{base.lower()}usdt", f"1000{base.lower()}usdt"]
        for stream_sym in variants:
            url = f"wss://fstream.binance.com/ws/{stream_sym}@depth20"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, timeout=1.4) as ws:
                        msg = await asyncio.wait_for(ws.receive(), timeout=1.2)
                        data = json.loads(msg.data)
                        bids = [[float(p), float(q)] for p, q in data.get('b', [])]
                        asks = [[float(p), float(q)] for p, q in data.get('a', [])]

                        if len(bids) < 3 or len(asks) < 3:
                            return None
                        mid = (bids[0][0] + asks[0][0]) / 2.0
                        bids_2pct = [b for b in bids if b[0] >= mid * 0.98]
                        asks_2pct = [a for a in asks if a[0] <= mid * 1.02]
                        if len(bids_2pct) < 2 or len(asks_2pct) < 2:
                            return None

                        bid_usd = sum(b[0] * b[1] for b in bids_2pct)
                        ask_usd = sum(a[0] * a[1] for a in asks_2pct)
                        b_gaps = [(bids_2pct[i][0] - bids_2pct[i+1][0]) / bids_2pct[i][0] for i in range(len(bids_2pct)-1)]
                        a_gaps = [(asks_2pct[i+1][0] - asks_2pct[i][0]) / asks_2pct[i][0] for i in range(len(asks_2pct)-1)]

                        return ("binance", sum(b_gaps)/len(b_gaps)*100.0, sum(a_gaps)/len(a_gaps)*100.0, bid_usd, ask_usd)
            except Exception:
                continue
        return None

    async def _fetch_depth(self, venue_name: str, symbol: str) -> tuple:
        client = self.venues.get(venue_name)
        if not client:
            return None
        try:
            ob = await asyncio.wait_for(client.fetch_order_book(symbol, limit=35), timeout=1.4)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])
            if len(bids) < 3 or len(asks) < 3:
                return None
            mid = (bids[0][0] + asks[0][0]) / 2.0

            bids_2pct = [b for b in bids if b[0] >= mid * 0.98]
            asks_2pct = [a for a in asks if a[0] <= mid * 1.02]
            if len(bids_2pct) < 2 or len(asks_2pct) < 2:
                return None

            bid_usd = sum(b[0] * b[1] for b in bids_2pct)
            ask_usd = sum(a[0] * a[1] for a in asks_2pct)

            bid_gaps = [(bids_2pct[i][0] - bids_2pct[i+1][0]) / bids_2pct[i][0] for i in range(len(bids_2pct) - 1)]
            ask_gaps = [(asks_2pct[i+1][0] - asks_2pct[i][0]) / asks_2pct[i][0] for i in range(len(asks_2pct) - 1)]

            avg_b_gap = (sum(bid_gaps) / len(bid_gaps)) * 100.0
            avg_a_gap = (sum(ask_gaps) / len(ask_gaps)) * 100.0
            return (venue_name, avg_b_gap, avg_a_gap, bid_usd, ask_usd)
        except Exception:
            return None

    async def audit_microstructure(self, base: str, vel_5m: float, consecutive_hits: int) -> dict:
        """
        Enforces:
        1. Venue Isolation: Focuses on Bitget + max 3 other venues (2 to 4 total).
           Isolates coins on >=5 venues UNLESS they showed results across last 3 checks.
        2. Fluid Spacing: Average limit order gap strictly inside [0.05%, 0.50%].
        3. 1.75x Depth & Gap Asymmetry.
        """
        venue_dict = self.listing_map.get(base, {})
        venue_count = len(venue_dict)

        # Isolated Mega-Cap Rule: >= 5 exchanges isolated unless persistent
        if venue_count >= 5 and consecutive_hits < 3:
            return {"approved": False, "reason": "ISOLATED_MEGA_CAP"}

        if venue_count < 2 or "bitget" not in venue_dict:
            return {"approved": False, "reason": "NO_CONFIRMATION_VENUE"}

        tasks = [self._fetch_depth(v_name, sym) for v_name, sym in venue_dict.items()]
        tasks.append(self._fetch_binance_depth_ws(base))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, tuple) and r is not None]

        if not any(v[0] == "bitget" for v in valid) or len(valid) < 2:
            return {"approved": False, "reason": "DEPTH_UNAVAILABLE"}

        tot_bid_usd = sum(v[3] for v in valid)
        tot_ask_usd = sum(v[4] for v in valid)
        avg_bid_gap = sum(v[1] for v in valid) / len(valid)
        avg_ask_gap = sum(v[2] for v in valid) / len(valid)

        # Fluid Spacing Check [0.05% - 0.50%]
        if vel_5m > 0:
            if not (0.05 <= avg_ask_gap <= 0.50):
                return {"approved": False, "reason": f"ASK_GAP_OUT_OF_BOUNDS ({avg_ask_gap:.3f}%)"}

            long_gap_r = avg_ask_gap / max(avg_bid_gap, 0.0001)
            long_depth_r = tot_bid_usd / max(tot_ask_usd, 0.0001)

            if long_gap_r >= 1.75 and long_depth_r >= 1.75:
                return {
                    "approved": True,
                    "side": "buy",
                    "bitget_symbol": venue_dict["bitget"],
                    "gap_pct": round(avg_ask_gap, 3),
                    "venues": [v[0] for v in valid]
                }

        elif vel_5m < 0:
            if not (0.05 <= avg_bid_gap <= 0.50):
                return {"approved": False, "reason": f"BID_GAP_OUT_OF_BOUNDS ({avg_bid_gap:.3f}%)"}

            short_gap_r = avg_bid_gap / max(avg_ask_gap, 0.0001)
            short_depth_r = tot_ask_usd / max(tot_bid_usd, 0.0001)

            if short_gap_r >= 1.75 and short_depth_r >= 1.75:
                return {
                    "approved": True,
                    "side": "sell",
                    "bitget_symbol": venue_dict["bitget"],
                    "gap_pct": round(avg_bid_gap, 3),
                    "venues": [v[0] for v in valid]
                }

        return {"approved": False, "reason": "INSUFFICIENT_RATIO"}

    async def close(self):
        for client in self.venues.values():
            await client.close()

# ----------------- MASTER EXECUTION & SMART FADE SENSOR -----------------
class TradingEngine:
    def __init__(self):
        self.exchange = ccxt_async.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_API_SECRET,
            'password': BITGET_API_PASSPHRASE,
            'options': {'defaultType': 'swap', 'createMarketBuyOrderRequiresPrice': False}
        })
        self.feed = GlobalFeedAggregator()
        self.auditor = DynamicVenueMatrix()
        self.streak = 0
        self.live_unlocked = False

    async def setup_symbol_mode(self, symbol: str):
        try:
            await self.exchange.set_margin_mode('isolated', symbol)
        except Exception:
            pass
        try:
            await self.exchange.set_position_mode(hedged=False, symbol=symbol)
        except Exception:
            pass
        try:
            await self.exchange.set_leverage(LEVERAGE, symbol)
        except Exception:
            pass

    async def get_order_size(self, symbol: str, current_price: float):
        try:
            bal = await self.exchange.fetch_balance()
            free_usdt = float(bal.get('USDT', {}).get('free', 0.0))
            if free_usdt < 0.5:
                free_usdt = 1.50
        except Exception:
            free_usdt = 1.50

        if (free_usdt * LEVERAGE) < 5.05:
            return None

        target_margin = min(free_usdt * 0.85, free_usdt - 0.15)
        notional_value = max(target_margin * LEVERAGE, MIN_NOTIONAL_USDT)

        raw_amount = notional_value / current_price
        formatted_amount = float(self.exchange.amount_to_precision(symbol, raw_amount))

        market = self.exchange.market(symbol)
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0.0) or 0.0

        if (formatted_amount * current_price) < 5.0 and min_amount > 0:
            formatted_amount += min_amount

        return formatted_amount

    async def close_position_safely(self, symbol: str, side: str, amount: float):
        close_side = "sell" if side == "buy" else "buy"
        for attempt in range(1, 4):
            try:
                order = await self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=amount,
                    params={'reduceOnly': True}
                )
                logger.info(f"Position closed cleanly: {symbol}")
                return order
            except Exception:
                await asyncio.sleep(1.0)
        return None

    async def run_trade_lifecycle(self, symbol: str, side: str, entry_price: float, is_live: bool):
        """
        Executes trade and runs the 20-SECOND SMART FADE SENSOR:
        - Exits immediately if volume stalls and Open Interest decays.
        - Exits immediately at Hard Stop (-0.65%).
        - Banks win only if Net PnL strictly >= +1.00%.
        """
        start_time = time.time()
        order_amount = await self.get_order_size(symbol, entry_price)

        if not order_amount or order_amount <= 0:
            return

        if is_live:
            try:
                await self.setup_symbol_mode(symbol)
                await self.exchange.create_order(symbol=symbol, type='market', side=side, amount=order_amount)
                logger.info(f"⚡ LIVE {side.upper()} order opened at 5x: {order_amount} {symbol}")
            except Exception as e:
                logger.error(f"Live order failed: {e}")
                return

        prev_vol = None
        prev_oi = None
        stagnant_checks = 0

        while True:
            # 20-second smart pulse
            await asyncio.sleep(20.0)
            now = time.time()
            elapsed = now - start_time

            try:
                ticker = await self.exchange.fetch_ticker(symbol)
                curr_price = float(ticker['last'])
                curr_vol = float(ticker.get('baseVolume', 0.0) or ticker.get('quoteVolume', 0.0))
            except Exception:
                continue

            curr_oi = None
            try:
                oi_data = await self.exchange.fetch_open_interest(symbol)
                curr_oi = float(oi_data.get('openInterestValue', 0.0) or oi_data.get('openInterest', 0.0))
            except Exception:
                pass

            if side == "buy":
                gross_pnl = ((curr_price - entry_price) / entry_price) * 100.0
            else:
                gross_pnl = ((entry_price - curr_price) / entry_price) * 100.0

            net_pnl = gross_pnl - 0.17  # 0.12% fees + 0.05% spread penalty

            system_status["active_trade"] = {
                "symbol": symbol, "side": side, "net_pnl": f"{net_pnl:.2f}%", "elapsed": int(elapsed)
            }

            # ----------------- 1. WIN EXIT (STRICT >= +1.00% NET) -----------------
            if net_pnl >= TARGET_NET_WIN_PCT:
                if is_live:
                    await self.close_position_safely(symbol, side, order_amount)
                self.streak += 1
                logger.info(f"🎯 GAUNTLET WIN #{self.streak}! Net PnL: +{net_pnl:.2f}% (Gross: +{gross_pnl:.2f}%)")
                if self.streak >= REQUIRED_WIN_STREAK:
                    self.live_unlocked = True
                    logger.info("🚨 8 CONSECUTIVE 1% NET WINS! LIVE TRADING UNLOCKED! 🚨")
                break

            # ----------------- 2. HARD STOP LOSS (-0.65%) -----------------
            if gross_pnl <= HARD_STOP_PCT:
                if is_live:
                    await self.close_position_safely(symbol, side, order_amount)
                logger.warning(f"🛑 STOPPED OUT! Net PnL: {net_pnl:.2f}%. Streak reset to 0.")
                self.streak = 0
                self.live_unlocked = False
                break

            # ----------------- 3. 20-SECOND SMART MICRO-EXIT (FADING SENSOR) -----------------
            if prev_vol is not None and prev_oi is not None and curr_oi is not None:
                vol_delta = curr_vol - prev_vol
                oi_delta = curr_oi - prev_oi

                # Momentum Fading Signature: Volume stalls and OI decays
                is_fading = (vol_delta <= 0) and (oi_delta < 0)

                if is_fading and net_pnl < 0.60:
                    stagnant_checks += 1
                else:
                    stagnant_checks = 0

                # 2 consecutive 20s checks confirming momentum has died
                if stagnant_checks >= 2 and elapsed >= 60.0:
                    if is_live:
                        await self.close_position_safely(symbol, side, order_amount)
                    logger.warning(f"💨 SMART EXIT: Volume stalled & OI dropped (-OI). Momentum faded at {int(elapsed)}s. Net PnL: {net_pnl:.2f}%.")
                    self.streak = 0
                    self.live_unlocked = False
                    break

            prev_vol = curr_vol
            if curr_oi is not None:
                prev_oi = curr_oi

            # ----------------- 4. 10-MINUTE WAVE EXHAUSTION CAP -----------------
            if elapsed >= MAX_HOLD_SEC:
                if is_live:
                    await self.close_position_safely(symbol, side, order_amount)
                logger.info(f"⏱️ 10-Minute Momentum Cycle exhausted. Exited at Net PnL: {net_pnl:.2f}%.")
                if net_pnl < TARGET_NET_WIN_PCT:
                    self.streak = 0
                    self.live_unlocked = False
                break

        system_status["active_trade"] = None
        system_status["streak"] = f"{self.streak}/{REQUIRED_WIN_STREAK}"
        system_status["mode"] = "LIVE_TRADING" if self.live_unlocked else "PAPER_GAUNTLET"

    async def main_loop(self):
        self.feed.start()
        await self.auditor.initialize()
        await self.exchange.load_markets()

        logger.info(f"Master Engine initialized with {LEVERAGE}x leverage. Scanning candidates...")

        while True:
            try:
                candidates = self.feed.get_candidate_coins(min_vol=1_000_000.0)

                for coin in candidates:
                    base = coin['base']
                    allowed_side = coin['side_allowed']  # "buy" (+OI) or "sell" (-OI Panic Waterfall)

                    # Audits venue isolation (<=4 venues) and fluid spacing [0.05% - 0.50%]
                    audit = await self.auditor.audit_microstructure(
                        base=base,
                        vel_5m=coin['vel_5m'],
                        consecutive_hits=coin['consecutive_hits']
                    )

                    if not audit['approved']:
                        continue

                    # Strict Asymmetric Filter: Short must be verified waterfall
                    if audit['side'] != allowed_side:
                        continue

                    bitget_symbol = audit['bitget_symbol']
                    if bitget_symbol not in self.exchange.markets:
                        continue

                    logger.info(
                        f"🎯 ASYMMETRIC TRIGGER: {base} | Side: {audit['side'].upper()} | "
                        f"5m Vel: {coin['vel_5m']}% | 5m OI Delta: {coin['oi_5m_delta']}% | "
                        f"Spacing: {audit['gap_pct']}% | Venues ({len(audit['venues'])}): {audit['venues']}"
                    )

                    await self.run_trade_lifecycle(
                        symbol=bitget_symbol,
                        side=audit['side'],
                        entry_price=coin['current_price'],
                        is_live=self.live_unlocked
                    )
                    break

            except Exception as e:
                logger.error(f"Main loop error: {e}")

            await asyncio.sleep(15)

    async def shutdown(self):
        self.feed.stop()
        await self.auditor.close()
        await self.exchange.close()

if __name__ == "__main__":
    start_health_server()
    engine = TradingEngine()
    try:
        asyncio.run(engine.main_loop())
    except (KeyboardInterrupt, SystemExit):
        asyncio.run(engine.shutdown())
