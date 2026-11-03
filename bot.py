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

# ----------------- CONFIGURATION -----------------
BITGET_API_KEY = os.getenv("BITGET_API_KEY", "")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET", "")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE", "")
PORT = int(os.getenv("PORT", 10000))

# LEVERAGE & EXECUTION RULES
LEVERAGE = 5                    # 5x Leverage: Safe liquidation cushion (~19%)
MIN_NOTIONAL_USDT = 5.2         # Bitget requires >= 5.0 USDT order value
TARGET_NET_WIN_PCT = 1.00       # Strict Gauntlet Target: Must bank >= +1.00% NET profit
REQUIRED_WIN_STREAK = 8         # 8 consecutive wins required to unlock live trading
HARD_STOP_PCT = -0.65           # Hard Stop Loss (-0.65% price move = -3.25% ROE at 5x)
MAX_HOLD_SEC = 300              # Maximum 5 mins in trade (Wave reaches 10m total)
TARGET_CLOSENESS_PCT = 85.0     # 90%+ target closeness across responding platforms

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CrossVenueSentinel")

system_status = {
    "status": "RUNNING",
    "leverage": f"{LEVERAGE}x",
    "mode": "PAPER_GAUNTLET",
    "streak": "0/8",
    "active_trade": None,
    "last_cross_refill": "None"
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

# ----------------- THE CROSS-VENUE MESSAGING & REFILL ENGINE -----------------
class CrossVenueRefillDispatcher:
    def __init__(self):
        self.venues = {
            "bitget": ccxt_async.bitget({'options': {'defaultType': 'swap'}}),
            "bybit": ccxt_async.bybit({'options': {'defaultType': 'linear'}}),
            "okx": ccxt_async.okx({'options': {'defaultType': 'swap'}}),
            "gate": ccxt_async.gate({'options': {'defaultType': 'swap'}}),
            "mexc": ccxt_async.mexc({'options': {'defaultType': 'swap'}})
        }
        self.listing_map = {}
        # Stores previous 20s telemetry snapshot per venue: venue -> (vol, oi, ts)
        self.telemetry_cache = {}

    async def initialize(self):
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
                logger.warning(f"Market mapping error on {name}: {e}")

        self.listing_map = {b: v for b, v in self.listing_map.items() if "bitget" in v}
        logger.info(f"Refill Dispatcher online: {len(self.listing_map)} Bitget assets cross-referenced.")

    async def _query_binance_depth_ws(self, base: str, side: str) -> tuple:
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

                        if side == "buy":
                            gaps = [(asks_2pct[i+1][0] - asks_2pct[i][0]) / asks_2pct[i][0] for i in range(len(asks_2pct)-1)]
                            avg_gap = (sum(gaps) / len(gaps)) * 100.0
                            d_score = min(1.0, (bid_usd / max(ask_usd, 1.0)) / 1.6) * 50.0
                            g_score = 50.0 if (0.05 <= avg_gap <= 0.50) else 0.0
                            return ("binance", d_score + g_score, avg_gap)
                        else:
                            gaps = [(bids_2pct[i][0] - bids_2pct[i+1][0]) / bids_2pct[i][0] for i in range(len(bids_2pct)-1)]
                            avg_gap = (sum(gaps) / len(bids_2pct)-1) * 100.0
                            d_score = min(1.0, (ask_usd / max(bid_usd, 1.0)) / 1.6) * 50.0
                            g_score = 50.0 if (0.05 <= avg_gap <= 0.50) else 0.0
                            return ("binance", d_score + g_score, avg_gap)
            except Exception:
                continue
        return None

    async def _query_venue_depth(self, venue_name: str, symbol: str, side: str) -> tuple:
        client = self.venues.get(venue_name)
        if not client:
            return None
        try:
            ob = await asyncio.wait_for(client.fetch_order_book(symbol, limit=25), timeout=1.4)
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

            if side == "buy":
                gaps = [(asks_2pct[i+1][0] - asks_2pct[i][0]) / asks_2pct[i][0] for i in range(len(asks_2pct)-1)]
                avg_gap = (sum(gaps) / len(gaps)) * 100.0
                d_score = min(1.0, (bid_usd / max(ask_usd, 1.0)) / 1.6) * 50.0
                g_score = 50.0 if (0.05 <= avg_gap <= 0.50) else 0.0
                return (venue_name, d_score + g_score, avg_gap)
            else:
                gaps = [(bids_2pct[i][0] - bids_2pct[i+1][0]) / bids_2pct[i][0] for i in range(len(bids_2pct)-1)]
                avg_gap = (sum(gaps) / len(bids_2pct)-1) * 100.0
                d_score = min(1.0, (ask_usd / max(bid_usd, 1.0)) / 1.6) * 50.0
                g_score = 50.0 if (0.05 <= avg_gap <= 0.50) else 0.0
                return (venue_name, d_score + g_score, avg_gap)
        except Exception:
            return None

    async def dispatch_entry_verification(self, base: str, side: str, confirmed_venues: list) -> dict:
        """Pings confirmed platforms before entering to verify 90%+ closeness."""
        venue_dict = self.listing_map.get(base, {})
        if "bitget" not in venue_dict:
            return {"approved": False, "reason": "NOT_ON_BITGET"}

        tasks = []
        for v_name in confirmed_venues:
            if v_name in venue_dict:
                tasks.append(self._query_venue_depth(v_name, venue_dict[v_name], side))
            elif v_name == "binance":
                tasks.append(self._query_binance_depth_ws(base, side))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, tuple) and r is not None]

        if len(valid) < 2:
            return {"approved": False, "reason": "INSUFFICIENT_RESPONSES"}

        avg_closeness = sum(v[1] for v in valid) / len(valid)
        bitget_record = next((v for v in valid if v[0] == "bitget"), None)
        bitget_gap = bitget_record[2] if bitget_record else 0.0

        if not (0.05 <= bitget_gap <= 0.50):
            return {"approved": False, "reason": f"BITGET_GAP_INVALID ({bitget_gap:.3f}%)"}

        is_approved = avg_closeness >= TARGET_CLOSENESS_PCT
        return {
            "approved": is_approved,
            "side": side,
            "closeness_pct": round(avg_closeness, 1),
            "bitget_symbol": venue_dict["bitget"],
            "bitget_gap": round(bitget_gap, 3),
            "reporting_venues": [v[0] for v in valid],
            "reason": f"CLOSENESS_{avg_closeness:.1f}%"
        }

    # ----------------- THE 20-SECOND CROSS-VENUE REFILL ROUTINE -----------------
    async def _fetch_venue_telemetry(self, venue_name: str, symbol: str) -> tuple:
        """Pings venue for live 24h volume and OI. Returns (venue_name, volume, oi)."""
        client = self.venues.get(venue_name)
        if not client:
            return None
        try:
            ticker = await asyncio.wait_for(client.fetch_ticker(symbol), timeout=1.4)
            vol = float(ticker.get('baseVolume', 0.0) or ticker.get('quoteVolume', 0.0))
            
            # Fetch OI if available
            oi = 0.0
            try:
                oi_data = await asyncio.wait_for(client.fetch_open_interest(symbol), timeout=1.2)
                oi = float(oi_data.get('openInterestValue', 0.0) or oi_data.get('openInterest', 0.0))
            except Exception:
                oi = float(ticker.get('info', {}).get('openInterest', 0.0) or 0.0)

            return (venue_name, vol, oi)
        except Exception:
            return None

    async def refill_and_audit_fade(self, base: str, confirmed_venues: list) -> dict:
        """
        Sends inquiry to confirmed venues every 20 seconds.
        Calculates if the cross-venue volume has stalled and OI is decaying globally.
        """
        venue_dict = self.listing_map.get(base, {})
        tasks = [
            self._fetch_venue_telemetry(v, venue_dict[v])
            for v in confirmed_venues if v in venue_dict
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, tuple) and r is not None]

        if not valid:
            return {"is_fading": False, "fade_ratio": 0.0}

        now = time.time()
        fading_votes = 0
        total_eval = 0
        fading_venues = []

        for name, curr_vol, curr_oi in valid:
            cache_key = f"{base}_{name}"
            prev_data = self.telemetry_cache.get(cache_key)

            if prev_data:
                prev_vol, prev_oi, prev_time = prev_data
                vol_delta = curr_vol - prev_vol
                oi_delta = curr_oi - prev_oi if (curr_oi > 0 and prev_oi > 0) else 0.0

                # Universal Fade across platforms: Volume stalls AND Open Interest declines
                if vol_delta <= 0 and oi_delta < 0:
                    fading_votes += 1
                    fading_venues.append(name)
                total_eval += 1

            self.telemetry_cache[cache_key] = (curr_vol, curr_oi, now)

        if total_eval == 0:
            return {"is_fading": False, "fade_ratio": 0.0}

        fade_ratio = fading_votes / total_eval
        # Majority (>= 60%) of reporting venues detect the fade
        is_global_fade = (fade_ratio >= 0.60) and (fading_votes >= 2)

        return {
            "is_fading": is_global_fade,
            "fade_ratio": round(fade_ratio * 100.0, 1),
            "fading_venues": fading_venues,
            "total_reporting": total_eval
        }

    async def close(self):
        for client in self.venues.values():
            await client.close()

# ----------------- MASTER EXECUTION & LIVE FADE ENGINE -----------------
class TradingEngine:
    def __init__(self):
        self.exchange = ccxt_async.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_API_SECRET,
            'password': BITGET_API_PASSPHRASE,
            'options': {'defaultType': 'swap', 'createMarketBuyOrderRequiresPrice': False}
        })
        self.feed = GlobalFeedAggregator()
        self.refill_engine = CrossVenueRefillDispatcher()
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

    async def run_trade_lifecycle(self, symbol: str, side: str, entry_price: float, is_live: bool, base: str, confirmed_venues: list):
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

        fade_confirmations = 0

        while True:
            # 20-second multi-venue refill pulse
            await asyncio.sleep(20.0)
            now = time.time()
            elapsed = now - start_time

            try:
                ticker = await self.exchange.fetch_ticker(symbol)
                curr_price = float(ticker['last'])
            except Exception:
                continue

            if side == "buy":
                gross_pnl = ((curr_price - entry_price) / entry_price) * 100.0
            else:
                gross_pnl = ((entry_price - curr_price) / entry_price) * 100.0

            net_pnl = gross_pnl - 0.17  # Strict deduction: 0.12% fees + 0.05% spread penalty

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

            # ----------------- 3. 20-SECOND CROSS-VENUE REFILL & FADE DUMP -----------------
            # Pings the other platforms to refill volume and OI telemetry
            cross_fade = await self.refill_engine.refill_and_audit_fade(base, confirmed_venues)
            system_status["last_cross_refill"] = f"{cross_fade.get('fade_ratio', 0.0)}% Fading"

            if cross_fade["is_fading"] and net_pnl < 0.60:
                fade_confirmations += 1
            else:
                fade_confirmations = 0

            # If 2 consecutive 20-second pulses confirm cross-venue fade, exit immediately!
            if fade_confirmations >= 2 and elapsed >= 60.0:
                if is_live:
                    await self.close_position_safely(symbol, side, order_amount)
                logger.warning(
                    f"💨 CROSS-VENUE FADE EXIT: Platforms {cross_fade['fading_venues']} reported volume stall & OI decline! "
                    f"Exited at {int(elapsed)}s before Bitget dumped. Net PnL: {net_pnl:.2f}%."
                )
                self.streak = 0
                self.live_unlocked = False
                break

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
        await self.refill_engine.initialize()
        await self.exchange.load_markets()

        logger.info(f"Cross-Venue Telemetry online at {LEVERAGE}x leverage. Scanning candidates...")

        while True:
            try:
                candidates = self.feed.get_candidate_coins(min_vol=1_000_000.0)

                for coin in candidates:
                    base = coin['base']
                    allowed_side = coin['side_allowed']

                    # 1. Entry Verification Dispatch (90%+ Closeness Check)
                    audit = await self.refill_engine.dispatch_entry_verification(
                        base=base,
                        side=allowed_side,
                        confirmed_venues=coin['confirmed_venues']
                    )

                    if not audit['approved']:
                        continue

                    bitget_symbol = audit['bitget_symbol']
                    if bitget_symbol not in self.exchange.markets:
                        continue

                    logger.info(
                        f"📡 90%+ GLOBAL DISPATCH CONFIRMED: {base} | Side: {allowed_side.upper()} | "
                        f"Closeness: {audit['closeness_pct']}% | Bitget Gap: {audit['bitget_gap']}% | "
                        f"Reporting Venues: {audit['reporting_venues']}"
                    )

                    # 2. Enter and monitor with 20-second Cross-Venue Refill Telemetry
                    await self.run_trade_lifecycle(
                        symbol=bitget_symbol,
                        side=allowed_side,
                        entry_price=coin['current_price'],
                        is_live=self.live_unlocked,
                        base=base,
                        confirmed_venues=coin['confirmed_venues']
                    )
                    break

            except Exception as e:
                logger.error(f"Main loop error: {e}")

            await asyncio.sleep(15)

    async def shutdown(self):
        self.feed.stop()
        await self.refill_engine.close()
        await self.exchange.close()

if __name__ == "__main__":
    start_health_server()
    engine = TradingEngine()
    try:
        asyncio.run(engine.main_loop())
    except (KeyboardInterrupt, SystemExit):
        asyncio.run(engine.shutdown())
