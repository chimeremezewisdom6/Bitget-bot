import asyncio
import ccxt.pro as ccxtpro
import os
import time
import threading
import json
import math
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from strategies import OrderFlowImbalanceStrategy
from aggregated_depth import get_aggregated_ratio, passes_volume_check, fetch_coins_above_1m_volume
from dotenv import load_dotenv

try:
    from browser_use_sdk.v4 import BrowserUse
except ImportError:
    BrowserUse = None

load_dotenv()

# --- SILENCE HTTP NOISE ---
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("main")

# --- 1. Keep-Alive Server ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, format, *args): pass

def run_keepalive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# --- 2. State Management ---
STATE_FILE = "state.json"
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f: return json.load(f)
    return {"streak": 0, "is_live": False}

def save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f)

# --- 3. AI Background Worker ---
def fetch_macro_data():
    api_key = os.environ.get("BROWSER_USE_API_KEY")
    if not api_key or BrowserUse is None: return
    while True:
        logger.info("🤖 AI Agent: Checking CoinGlass liquidations...")
        try:
            with BrowserUse(api_key=api_key) as client:
                run = client.runs.create("Go to CoinGlass.com, find the total 24-hour liquidations for Bitcoin, and tell me the number in millions.")
                result = client.runs.wait_for_completion(run.id)
                logger.info(f"📊 AI MACRO DATA: {result.result}")
        except Exception as e:
            logger.error(f"AI Agent Error: {e}")
        time.sleep(3600)

# --- 4. Dynamic Leverage ---
async def set_safe_leverage(exchange, symbol, balance_usdt):
    try:
        market = await exchange.load_markets()
        min_amount = market[symbol]['limits']['amount']['min']
        ticker = await exchange.fetch_ticker(symbol)
        min_cost = min_amount * ticker['last']
        req_lev = math.ceil(min_cost / balance_usdt)
        final_lev = max(5, min(req_lev, 20))
        await exchange.set_leverage(final_lev, symbol)
        return final_lev
    except Exception:
        return 5

# --- 5. Main Engine ---
async def main():
    state = load_state()
    logger.info(f"🛡️ PAPER TRADING MODE. Win Streak: {state['streak']}/8")

    exchange = ccxtpro.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap', 'adjustForTimeDifference': True}
    })

    # --- DYNAMIC COIN LIST ---
    dynamic_coins = fetch_coins_above_1m_volume()
    strategies = {coin: OrderFlowImbalanceStrategy(coin) for coin in dynamic_coins}

    active_trade = None
    active_strategy = None
    current_price = 0.0
    last_scan_time = 0
    last_summary_time = time.time()
    last_coin_refresh_time = time.time()

    while True:
        try:
            current_time = time.time()

            # REFRESH COIN LIST EVERY 30 MINUTES
            if current_time - last_coin_refresh_time >= 1800:
                logger.info("🔄 Refreshing dynamic coin list...")
                new_coins = fetch_coins_above_1m_volume()
                for c in new_coins:
                    if c not in strategies:
                        strategies[c] = OrderFlowImbalanceStrategy(c)
                last_coin_refresh_time = current_time

            # 10-MINUTE DASHBOARD
            if current_time - last_summary_time >= 600:
                logger.info("="*50)
                logger.info(f"📊 10-MIN SUMMARY | Mode: {'🔥 LIVE' if state['is_live'] else '📝 PAPER'} | Streak: {state['streak']}/8")
                logger.info(f"🔭 Scanning {len(strategies)} coins (>$1M volume)")
                if active_trade and active_strategy:
                    pnl = (current_price - active_strategy.entry_price) / active_strategy.entry_price if active_trade["direction"] == "LONG" else (active_strategy.entry_price - current_price) / active_strategy.entry_price
                    logger.info(f"💼 Active: {active_trade['symbol']} ({active_trade['direction']}) | Net PnL: {(pnl - 0.0012)*100:+.3f}%")
                else:
                    logger.info("💼 Active Trade: None (Scanning)")
                logger.info("="*50)
                last_summary_time = current_time

            # SCAN MARKET EVERY 15 SECONDS
            if current_time - last_scan_time >= 15:
                logger.info(f"🔭 Scanning {len(strategies)} coins for order flow imbalance...")
                
                # If in a trade, only check the active trade
                check_coins = [active_trade["symbol"]] if active_trade else list(strategies.keys())

                for coin in check_coins:
                    try:
                        # Skip if exchange doesn't have the market
                        market = exchange.market(coin)
                        if not market: continue
                        
                        ticker = await exchange.fetch_ticker(coin)
                        if not ticker or 'last' not in ticker: continue
                        current_price = ticker['last']

                        ratio = await get_aggregated_ratio(coin)
                        
                        if (ratio >= 4.0 or ratio <= 0.25) and not active_trade:
                            if not await passes_volume_check(coin):
                                continue

                        signal, gross_pnl = strategies[coin].analyze(ratio, current_price)

                        if signal in ["BUY_LONG", "SELL_SHORT"] and not active_trade:
                            direction = "LONG" if signal == "BUY_LONG" else "SHORT"
                            active_trade = {"symbol": coin, "direction": direction}
                            active_strategy = strategies[coin]
                            logger.info(f"🎯 ENTERED {direction} {coin} at {current_price} (Ratio: {ratio:.2f})")

                            if state["is_live"]:
                                balance = await exchange.fetch_balance()
                                usdt_free = balance['USDT']['free']
                                if usdt_free > 1.0:
                                    await set_safe_leverage(exchange, coin, usdt_free)
                                    amount = (usdt_free * 0.90) / current_price
                                    if direction == "LONG": await exchange.create_market_buy_order(coin, amount)
                                    else: await exchange.create_market_sell_order(coin, amount)

                        elif signal in ["CLOSE_LONG", "CLOSE_SHORT"] and active_trade and active_trade["symbol"] == coin:
                            net_pnl = gross_pnl - 0.0012
                            logger.info(f"📉 CLOSED {coin} | Gross: {gross_pnl*100:.3f}% | Net: {net_pnl*100:.3f}%")

                            if net_pnl >= 0.0042:
                                state["streak"] += 1
                                logger.info(f"✅ WIN! Streak: {state['streak']}/8")
                            elif net_pnl < 0.0022:
                                state["streak"] = 0
                                logger.info(f"❌ LOSS. Streak Reset to 0")
                            else:
                                logger.info(f"⚖️ SCRATCH. Streak Unchanged")

                            if state["streak"] >= 8 and not state["is_live"]:
                                state["is_live"] = True
                                logger.info("\n🔥🔥🔥 8 WINS! SWITCHING TO LIVE TRADING. 🔥🔥🔥\n")
                            
                            save_state(state)

                            if state["is_live"]:
                                balance = await exchange.fetch_balance()
                                held = balance[coin.split('/')[0]]['free']
                                if held > 0:
                                    if active_trade["direction"] == "LONG": await exchange.create_market_sell_order(coin, held)
                                    else: await exchange.create_market_buy_order(coin, held)

                            active_trade = None
                            active_strategy = None
                    except Exception as inner_e:
                        logger.error(f"Error processing {coin}: {inner_e}")

                last_scan_time = current_time

        except Exception as e:
            logger.error(f"CRITICAL LOOP ERROR: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=fetch_macro_data, daemon=True).start()
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main())
