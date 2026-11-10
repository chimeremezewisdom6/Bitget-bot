import asyncio
import ccxt.pro as ccxtpro
import os
import time
import threading
import requests
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from strategies import MicroMomentumStrategy
from dotenv import load_dotenv

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

# --- 2. State Management (Saves Streak to Disk) ---
STATE_FILE = "state.json"
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"streak": 0, "is_live": False}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# --- 3. AI Coin Selector (OpenRouter) ---
def get_ai_target_coin():
    print("🧠 Asking AI to find the best high-beta altcoin...", flush=True)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "PEPE/USDT:USDT"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = "I am running a high-frequency momentum bot on Bitget Futures. Reply with ONLY the ticker symbol of a highly volatile altcoin (e.g., SOL, WIF, PEPE, DOGE). Format it exactly like this: 'PEPE/USDT:USDT'. Do not include any other text."
    payload = {"model": "openrouter/free", "messages": [{"role": "user", "content": prompt}]}

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
        data = response.json()
        if isinstance(data, dict) and 'choices' in data and len(data['choices']) > 0:
            symbol = data['choices'][0]['message']['content'].strip()
            symbol = symbol.replace('"', '').replace("'", "").split('\n')[0].strip()
            print(f"🎯 AI Selected: {symbol}", flush=True)
            return symbol
    except Exception:
        pass
    return "PEPE/USDT:USDT"

# --- 4. Dynamic Leverage Calculator ---
async def set_safe_leverage(exchange, symbol, balance_usdt):
    market = await exchange.load_markets()
    min_amount = market[symbol]['limits']['amount']['min']
    
    # Get current price to calculate minimum cost
    ticker = await exchange.fetch_ticker(symbol)
    price = ticker['last']
    
    min_cost = min_amount * price
    required_leverage = math.ceil(min_cost / balance_usdt)
    
    # Cap leverage at 20x for safety
    final_leverage = max(5, min(required_leverage, 20))
    
    print(f"⚙️ Balance: ${balance_usdt:.2f} | Min Order: ${min_cost:.2f} | Setting Leverage to {final_leverage}x", flush=True)
    await exchange.set_leverage(final_leverage, symbol)
    return final_leverage

# --- 5. Main Execution Loop ---
async def main():
    state = load_state()
    if state["is_live"]:
        print("🔥 SYSTEM IS LIVE. EXECUTING REAL TRADES.", flush=True)
    else:
        print(f"🛡️ PAPER TRADING MODE. Win Streak: {state['streak']}/8", flush=True)

    target_coin = get_ai_target_coin()

    exchange = ccxtpro.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap', 'adjustForTimeDifference': True}
    })

    strategy = MicroMomentumStrategy(target_coin)
    last_summary_time = time.time()

    while True:
        try:
            if time.time() - last_summary_time >= 600:
                print(f"\n📊 10-MIN SUMMARY | Streak: {state['streak']}/8 | Live: {state['is_live']} | Price: {strategy.peak_price}", flush=True)
                last_summary_time = time.time()

            raw_ticker = await exchange.watch_ticker(target_coin)
            if isinstance(raw_ticker, list):
                ticker = raw_ticker[0] if len(raw_ticker) > 0 else None
            else:
                ticker = raw_ticker

            if not ticker or 'last' not in ticker or ticker['last'] is None:
                continue
                
            current_price = float(ticker['last'])
            signal, gross_pnl = strategy.analyze(current_price)
            
            # --- BUY SIGNAL ---
            if signal == "BUY":
                print(f"🚀 IGNITION! BUY {target_coin} at {current_price}", flush=True)
                if state["is_live"]:
                    try:
                        balance = await exchange.fetch_balance()
                        usdt_free = balance['USDT']['free']
                        
                        lev = await set_safe_leverage(exchange, target_coin, usdt_free)
                        
                        # Use 90% of available margin
                        cost = usdt_free * 0.90
                        amount = cost / current_price
                        
                        order = await exchange.create_market_buy_order(target_coin, amount)
                        print(f"✅ REAL BUY EXECUTED: {order['id']}", flush=True)
                    except Exception as e:
                        print(f"❌ Buy Order Failed: {e}", flush=True)

            # --- SELL SIGNALS ---
            elif signal in ["SELL_MOMENTUM_DIED", "SELL_TRAILING_STOP"]:
                print(f"📉 {signal} at {current_price} | Gross PnL: {gross_pnl*100:.3f}%", flush=True)
                
                # Calculate NET PnL (Subtracting ~0.12% for trading fees & spread)
                net_pnl = gross_pnl - 0.0012 
                
                # Update Streak Logic
                if net_pnl >= 0.0042: # 0.42% NET win
                    state["streak"] += 1
                    print(f"✅ WIN! (+{net_pnl*100:.3f}%) | Streak: {state['streak']}/8", flush=True)
                else:
                    print(f"❌ NOT ACCEPTED (Below 0.42% NET) | Streak Reset to 0", flush=True)
                    state["streak"] = 0

                # Check if we unlock Live Trading
                if state["streak"] >= 8 and not state["is_live"]:
                    state["is_live"] = True
                    print("\n🔥🔥🔥 8 WINS IN A ROW! SWITCHING TO LIVE TRADING. 🔥🔥🔥\n", flush=True)
                
                save_state(state)

                # Execute Live Sell if applicable
                if state["is_live"]:
                    try:
                        balance = await exchange.fetch_balance()
                        coin_symbol = target_coin.split('/')[0]
                        amount_held = balance[coin_symbol]['free']
                        if amount_held > 0:
                            order = await exchange.create_market_sell_order(target_coin, amount_held)
                            print(f"✅ REAL SELL EXECUTED: {order['id']}", flush=True)
                    except Exception as e:
                        print(f"❌ Sell Order Failed: {e}", flush=True)

            await asyncio.sleep(0.05)

        except Exception as e:
            print(f"⚠️ Connection Error: {e}", flush=True)
            await asyncio.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main())
