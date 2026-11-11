import asyncio
import ccxt.pro as ccxtpro
import os
import time
import threading
import requests
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from strategies import RubberBandStrategy
from dotenv import load_dotenv

# Try to import BrowserUse, handle if missing
try:
    from browser_use_sdk.v4 import BrowserUse
except ImportError:
    BrowserUse = None

load_dotenv()

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
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"streak": 0, "is_live": False}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# --- 3. AI Background Worker (Macro Data) ---
def fetch_macro_data():
    """Runs in a separate thread. Uses AI to check CoinGlass every 60 minutes."""
    api_key = os.environ.get("BROWSER_USE_API_KEY")
    if not api_key or BrowserUse is None:
        print("⚠️ No Browser Use API Key or SDK missing. Skipping AI macro data.", flush=True)
        return

    while True:
        print("🤖 AI Agent: Opening cloud browser to check CoinGlass liquidations...", flush=True)
        try:
            with BrowserUse(api_key=api_key) as client:
                task = "Go to CoinGlass.com, find the total 24-hour liquidations for Bitcoin, and tell me the number in millions."
                run = client.runs.create(task)
                result = client.runs.wait_for_completion(run.id)
                print(f"\n📊 AI MACRO DATA: BTC Liquidations -> {result.result}\n", flush=True)
        except Exception as e:
            print(f"⚠️ AI Agent Error: {e}", flush=True)
        
        # Wait 1 hour before checking again
        time.sleep(3600)

# --- 4. Market-Wide Scanner ---
async def scan_market_for_reversals(exchange):
    print("🔭 Scanning entire market for stretched rubber bands...", flush=True)
    try:
        tickers = await exchange.fetch_tickers()
        candidates = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(":USDT") and ticker['percentage'] is not None:
                if ticker['percentage'] < -5.0: # Dropped more than 5% today
                    candidates.append((symbol, ticker['percentage']))
                    
        candidates.sort(key=lambda x: x[1])
        top_losers = [c[0] for c in candidates[:15]]
        
        best_setups = []
        for symbol in top_losers:
            candles = await exchange.fetch_ohlcv(symbol, '1m', limit=20)
            if len(candles) < 20: continue
            
            prices = [c[4] for c in candles]
            sma = sum(prices) / 20
            variance = sum((p - sma) ** 2 for p in prices) / 20
            std_dev = math.sqrt(variance)
            lower_band = sma - (2.5 * std_dev)
            
            current_price = prices[-1]
            if current_price <= lower_band * 1.002: 
                best_setups.append(symbol)
                
        print(f"🎯 Found {len(best_setups)} coins currently touching extreme lower bands.", flush=True)
        return best_setups
    except Exception as e:
        print(f"⚠️ Scanner Error: {e}", flush=True)
        return []

# --- 5. Dynamic Leverage ---
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

# --- 6. Main Engine ---
async def main():
    state = load_state()
    print(f"🛡️ PAPER TRADING MODE. Win Streak: {state['streak']}/8", flush=True)

    exchange = ccxtpro.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap', 'adjustForTimeDifference': True}
    })

    strategies = {}
    active_trade = None
    active_strategy = None
    current_price = 0.0
    
    last_scan_time = 0
    last_summary_time = time.time()

    while True:
        try:
            current_time = time.time()

            # 📊 10-MINUTE DASHBOARD SUMMARY
            if current_time - last_summary_time >= 600:
                print("\n" + "="*50, flush=True)
                print("📊 10-MINUTE BOT SUMMARY", flush=True)
                print("="*50, flush=True)
                print(f"🛡️ Mode      : {'🔥 LIVE TRADING' if state['is_live'] else '📝 PAPER TRADING'}", flush=True)
                print(f"🏆 Win Streak: {state['streak']}/8 (Needs +0.42% NET)", flush=True)
                print(f"🔭 Watching  : {len(strategies)} coins for extreme rubber band bounces", flush=True)
                
                if active_trade and active_strategy:
                    current_pnl = (current_price - active_strategy.entry_price) / active_strategy.entry_price
                    net_pnl = current_pnl - 0.0012
                    print(f"💼 Active Trade: {active_trade}", flush=True)
                    print(f"   ├─ Entry Price: {active_strategy.entry_price}", flush=True)
                    print(f"   ├─ Current Px : {current_price}", flush=True)
                    print(f"   └─ Live PnL   : {net_pnl*100:+.3f}% (Net)", flush=True)
                else:
                    print(f"💼 Active Trade: None (Waiting for setup)", flush=True)
                print("="*50 + "\n", flush=True)
                
                last_summary_time = current_time

            # SCAN MARKET
            if current_time - last_scan_time >= 120 and active_trade is None:
                top_coins = await scan_market_for_reversals(exchange)
                
                for coin in top_coins:
                    if coin not in strategies:
                        strategies[coin] = RubberBandStrategy(coin)
                        candles = await exchange.fetch_ohlcv(coin, '1m', limit=20)
                        for c in candles:
                            strategies[coin].prices.append(c[4])
                last_scan_time = current_time

            # WATCH ACTIVE TRADE & CANDIDATES
            watch_list = []
            if active_trade:
                watch_list.append(active_trade)
            for coin in strategies.keys():
                if coin != active_trade:
                    watch_list.append(coin)

            if not watch_list:
                await asyncio.sleep(2)
                continue

            tasks = [exchange.watch_ticker(coin) for coin in watch_list]
            tickers = await asyncio.gather(*tasks)

            # OPPORTUNITY COST SWITCHING LOGIC
            for i, coin in enumerate(watch_list):
                ticker = tickers[i]
                if isinstance(ticker, list):
                    ticker = ticker[0] if len(ticker) > 0 else None
                
                if not ticker or 'last' not in ticker or ticker['last'] is None:
                    continue

                current_price = float(ticker['last'])
                signal, gross_pnl = strategies[coin].analyze(current_price)

                # SWITCHING LOGIC (Dump losing trade for a better setup)
                if signal == "BUY_REVERSION" and active_trade and active_trade != coin:
                    active_pnl = (current_price - active_strategy.entry_price) / active_strategy.entry_price
                    
                    if active_pnl < 0:
                        print(f"🔄 SWITCHING! Dumping {active_trade} at a loss to catch {coin}!", flush=True)
                        
                        if state["is_live"]:
                            try:
                                balance = await exchange.fetch_balance()
                                c_sym = active_trade.split('/')[0]
                                held = balance[c_sym]['free']
                                if held > 0:
                                    await exchange.create_market_sell_order(active_trade, held)
                            except Exception: pass
                        
                        active_strategy.in_position = False
                        active_trade = None
                        
                        active_trade = coin
                        active_strategy = strategies[coin]
                        active_strategy.in_position = True
                        active_strategy.entry_price = current_price
                        active_strategy.peak_price = current_price
                        print(f"🪀 IMMEDIATE RE-ENTRY! Bought {coin} at {current_price}", flush=True)
                        continue

                # NORMAL BUY ENTRY
                if signal == "BUY_REVERSION" and not active_trade:
                    print(f"🪀 RUBBER BAND BOUNCE! Bought {coin} at {current_price}", flush=True)
                    active_trade = coin
                    active_strategy = strategies[coin]
                    
                    if state["is_live"]:
                        try:
                            balance = await exchange.fetch_balance()
                            usdt_free = balance['USDT']['free']
                            if usdt_free > 1.0:
                                await set_safe_leverage(exchange, coin, usdt_free)
                                amount = (usdt_free * 0.90) / current_price
                                await exchange.create_market_buy_order(coin, amount)
                        except Exception as e: print(f"❌ Buy Error: {e}")

                # STRICT SELL LOGIC & 8-WIN GATE
                elif signal in ["SELL_TARGET", "SELL_STOP"] and active_trade == coin:
                    print(f"📉 {signal} on {coin} at {current_price} | Gross PnL: {gross_pnl*100:.3f}%", flush=True)
                    
                    net_pnl = gross_pnl - 0.0012 # Deduct 0.12% for fees
                    
                    # --- STRICT RULES APPLIED HERE ---
                    if net_pnl >= 0.0042:
                        state["streak"] += 1
                        print(f"✅ WIN! (+{net_pnl*100:.3f}%) | Streak: {state['streak']}/8", flush=True)
                    elif net_pnl < 0.0022:
                        state["streak"] = 0
                        print(f"❌ LOSS (Below 0.22%) ({net_pnl*100:+.3f}%) | Streak Reset to 0", flush=True)
                    else:
                        print(f"⚖️ SCRATCH (Between 0.22% and 0.42%) ({net_pnl*100:+.3f}%) | Streak Unchanged", flush=True)

                    # Unlock Live Trading
                    if state["streak"] >= 8 and not state["is_live"]:
                        state["is_live"] = True
                        print("\n🔥🔥🔥 8 WINS IN A ROW! SWITCHING TO LIVE TRADING. 🔥🔥🔥\n", flush=True)
                    
                    save_state(state)

                    if state["is_live"]:
                        try:
                            balance = await exchange.fetch_balance()
                            c_sym = coin.split('/')[0]
                            held = balance[c_sym]['free']
                            if held > 0:
                                await exchange.create_market_sell_order(coin, held)
                        except Exception as e: print(f"❌ Sell Error: {e}")

                    active_trade = None
                    active_strategy = None

        except Exception as e:
            print(f"⚠️ Connection Error: {e}", flush=True)
            await asyncio.sleep(2)

if __name__ == "__main__":
    # Start the AI macro data worker
    threading.Thread(target=fetch_macro_data, daemon=True).start()
    # Start the keep-alive server
    threading.Thread(target=run_keepalive, daemon=True).start()
    # Start the trading engine
    asyncio.run(main())
