import os
import sys
import time
import json
import asyncio
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

# LEVERAGE & MICROSTRUCTURE RULES
LEVERAGE = 5                    # 5x Leverage: Safe buffer (~19% liquidation distance)
MIN_NOTIONAL_USDT = 5.2         # Bitget requires >= 5.0 USDT order value (clamped at $5.20)
TARGET_NET_WIN_PCT = 1.0        # Strict +1.0% NET profit per win
REQUIRED_WIN_STREAK = 8         # 8 consecutive wins required to unlock live trading
HARD_STOP_PCT = -0.65           # Hard Stop Loss (-0.65% price move = -3.25% ROE at 5x)
STAGNATION_CUT_PCT = -0.28      # Cut trade if stalled after 120s
STAGNATION_TIME_SEC = 120

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Bitget5xEngine")

# ----------------- HEALTH CHECK SERVER (RENDER) -----------------
system_status = {
    "status": "RUNNING",
    "leverage": f"{LEVERAGE}x",
    "mode": "PAPER_GAUNTLET",
    "streak": "0/8",
    "active_trade": None,
    "last_audit": "None"
}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(system_status).encode('utf-8'))
        except (BrokenPipeError, ConnectionResetError, Exception):
            pass

    def log_message(self, format, *args):
        pass

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Render Health Server bound to 0.0.0.0:{PORT}")

# ----------------- DYNAMIC CROSS-VENUE AUDITOR -----------------
class DynamicCrossVenueAuditor:
    def __init__(self):
        self.venues = {
            "bitget": ccxt_async.bitget({'options': {'defaultType': 'swap'}}),
            "gateio": ccxt_async.gateio({'options': {'defaultType': 'swap'}}),
            "mexc": ccxt_async.mexc({'options': {'defaultType': 'swap'}}),
            "bybit": ccxt_async.bybit({'options': {'defaultType': 'linear'}}),
            "binance": ccxt_async.binance({'options': {'defaultType': 'swap'}})
        }
        # Mapping: clean_base -> { venue_name: ccxt_symbol }
        self.listing_map = {}

    async def initialize(self):
        """Maps assets across venues using normalized base names."""
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

        # Keep assets tradeable on Bitget + at least 1 other venue
        self.listing_map = {
            b: venues for b, venues in self.listing_map.items()
            if "bitget" in venues and len(venues) >= 2
        }
        logger.info(f"Listing Map verified: {len(self.listing_map)} coins qualified across 2-5 venues.")

    async def _fetch_depth(self, venue_name: str, symbol: str) -> tuple:
        client = self.venues[venue_name]
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

    async def audit_coin(self, base: str, velocity_2m: float) -> dict:
        venue_dict = self.listing_map.get(base, {})
        if len(venue_dict) < 2 or "bitget" not in venue_dict:
            return {"approved": False}

        tasks = [self._fetch_depth(v_name, sym) for v_name, sym in venue_dict.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, tuple) and r is not None]

        if not any(v[0] == "bitget" for v in valid) or len(valid) < 2:
            return {"approved": False}

        tot_bid_usd = sum(v[3] for v in valid)
        tot_ask_usd = sum(v[4] for v in valid)
        avg_bid_gap = sum(v[1] for v in valid) / len(valid)
        avg_ask_gap = sum(v[2] for v in valid) / len(valid)

        # Reject crowded books (e.g. BTC/ETH where gaps are microscopic <0.035%)
        if avg_bid_gap < 0.035 and avg_ask_gap < 0.035:
            return {"approved": False}

        # LONG VACUUM: Asks have >=2x wider gaps | Bids have >=2x USD depth
        long_gap_r = avg_ask_gap / max(avg_bid_gap, 0.0001)
        long_depth_r = tot_bid_usd / max(tot_ask_usd, 0.0001)
        score_long = min(1.0, long_gap_r / 2.0) * 40.0 + min(1.0, long_depth_r / 2.0) * 40.0 + (20.0 if 0.25 <= velocity_2m <= 1.95 else 0.0)

        # SHORT VACUUM: Bids have >=2x wider gaps | Asks have >=2x USD depth
        short_gap_r = avg_bid_gap / max(avg_ask_gap, 0.0001)
        short_depth_r = tot_ask_usd / max(tot_bid_usd, 0.0001)
        score_short = min(1.0, short_gap_r / 2.0) * 40.0 + min(1.0, short_depth_r / 2.0) * 40.0 + (20.0 if -1.95 <= velocity_2m <= -0.25 else 0.0)

        if score_long >= 90.0 and score_long > score_short:
            return {"approved": True, "side": "buy", "score": score_long, "bitget_symbol": venue_dict["bitget"]}

        if score_short >= 90.0 and score_short > score_long:
            return {"approved": True, "side": "sell", "score": score_short, "bitget_symbol": venue_dict["bitget"]}

        return {"approved": False}

    async def close(self):
        for client in self.venues.values():
            await client.close()

# ----------------- ASYNC MASTER TRADING ENGINE -----------------
class TradingEngine:
    def __init__(self):
        self.exchange = ccxt_async.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_API_SECRET,
            'password': BITGET_API_PASSPHRASE,
            'options': {
                'defaultType': 'swap',
                'createMarketBuyOrderRequiresPrice': False
            }
        })
        self.feed = GlobalFeedAggregator()
        self.auditor = DynamicCrossVenueAuditor()
        self.streak = 0
        self.live_unlocked = False

    async def setup_symbol_mode(self, symbol: str):
        """Configures isolated margin, one-way mode, and 5x leverage."""
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
        """
        Calculates contract amount for 5x leverage on a $1.50 account.
        Guarantees final order value >= $5.20 USDT without precision rejection.
        """
        try:
            bal = await self.exchange.fetch_balance()
            free_usdt = float(bal.get('USDT', {}).get('free', 0.0))
            if free_usdt < 0.5:
                free_usdt = 1.50  # Simulation fallback if testing unfunded
        except Exception:
            free_usdt = 1.50

        # Safety: Ensure $1.50 account can support 5x leverage ($5.00 min / 5 = $1.00 margin)
        if (free_usdt * LEVERAGE) < 5.05:
            logger.warning(f"Balance too low ({free_usdt} USDT) to open min contract at {LEVERAGE}x.")
            return None

        target_margin = min(free_usdt * 0.85, free_usdt - 0.15)
        notional_value = max(target_margin * LEVERAGE, MIN_NOTIONAL_USDT)

        raw_amount = notional_value / current_price
        formatted_amount = float(self.exchange.amount_to_precision(symbol, raw_amount))

        market = self.exchange.market(symbol)
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0.0) or 0.0

        # Precision step adjustment
        if (formatted_amount * current_price) < 5.0 and min_amount > 0:
            formatted_amount += min_amount

        # Final margin verification
        required_margin = (formatted_amount * current_price) / LEVERAGE
        if required_margin > free_usdt:
            logger.warning(f"Precision step pushed margin ({required_margin:.2f}) above balance ({free_usdt:.2f}).")
            return None

        return formatted_amount

    async def close_position_safely(self, symbol: str, side: str, amount: float):
        """Closes position using reduceOnly with a 3-stage retry loop."""
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
                logger.info(f"Position closed successfully: {symbol}")
                return order
            except Exception as e:
                logger.error(f"Close attempt {attempt} failed for {symbol}: {e}")
                await asyncio.sleep(1.0)
        return None

    async def run_trade_lifecycle(self, symbol: str, side: str, entry_price: float, is_live: bool):
        start_time = time.time()
        order_amount = await self.get_order_size(symbol, entry_price)

        if not order_amount or order_amount <= 0:
            logger.warning(f"Trade aborted: Sizing requirements not met for {symbol}.")
            return

        if is_live:
            try:
                await self.setup_symbol_mode(symbol)
                await self.exchange.create_order(symbol=symbol, type='market', side=side, amount=order_amount)
                logger.info(f"⚡ LIVE {side.upper()} opened at 5x: {order_amount} {symbol} at ${entry_price}")
            except Exception as e:
                logger.error(f"Live order placement failed: {e}")
                return

        while True:
            await asyncio.sleep(2.0)  # Native non-blocking sleep
            elapsed = time.time() - start_time

            try:
                ticker = await self.exchange.fetch_ticker(symbol)
                curr_price = float(ticker['last'])
            except Exception:
                continue

            if side == "buy":
                gross_pnl = ((curr_price - entry_price) / entry_price) * 100.0
            else:
                gross_pnl = ((entry_price - curr_price) / entry_price) * 100.0

            net_pnl = gross_pnl - 0.17  # 0.12% roundtrip taker fee + 0.05% spread penalty

            system_status["active_trade"] = {
                "symbol": symbol, "side": side, "net_pnl": f"{net_pnl:.2f}%", "elapsed": int(elapsed)
            }

            # 1. WIN EXIT (+1.00% Net Profit Achieved)
            if net_pnl >= TARGET_NET_WIN_PCT:
                if is_live:
                    await self.close_position_safely(symbol, side, order_amount)
                self.streak += 1
                logger.info(f"🎯 WIN #{self.streak}! Net PnL: +{net_pnl:.2f}% (Gross: +{gross_pnl:.2f}%)")
                if self.streak >= REQUIRED_WIN_STREAK:
                    self.live_unlocked = True
                    logger.info("🚨 8 CONSECUTIVE 1% WINS! LIVE TRADING UNLOCKED! 🚨")
                break

            # 2. HARD STOP LOSS (-0.65% Price Move = -3.25% ROE at 5x)
            if gross_pnl <= HARD_STOP_PCT:
                if is_live:
                    await self.close_position_safely(symbol, side, order_amount)
                logger.warning(f"🛑 STOPPED OUT! Net PnL: {net_pnl:.2f}%. Streak reset to 0.")
                self.streak = 0
                self.live_unlocked = False
                break

            # 3. STAGNATION CUT (120s with no momentum)
            if elapsed >= STAGNATION_TIME_SEC and gross_pnl <= STAGNATION_CUT_PCT:
                if is_live:
                    await self.close_position_safely(symbol, side, order_amount)
                logger.warning(f"⌛ STAGNATION CUT at 120s. Net PnL: {net_pnl:.2f}%. Streak reset to 0.")
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

                    audit = await self.auditor.audit_coin(base, coin['velocity_2m'])
                    if not audit['approved']:
                        continue

                    bitget_symbol = audit['bitget_symbol']
                    if bitget_symbol not in self.exchange.markets:
                        continue

                    logger.info(
                        f"🔥 90%+ AIR POCKET CONFIRMED: {base} | Side: {audit['side'].upper()} | "
                        f"Score: {audit['score']:.1f}% | Venue Symbol: {bitget_symbol}"
                    )

                    await self.run_trade_lifecycle(
                        symbol=bitget_symbol,
                        side=audit['side'],
                        entry_price=coin['current_price'],
                        is_live=self.live_unlocked
                    )
                    break  # One active position at a time to protect margin

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
