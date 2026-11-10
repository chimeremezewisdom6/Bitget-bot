import asyncio
import ccxt.pro as ccxtpro
import os
import time
import threading
import requests
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

# --- 2. AI Coin Selector (OpenRouter) ---
def get_ai_target_coin():
    print("🧠 Asking AI to find the best high-beta altcoin...", flush=True)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️ No OpenRouter Key found. Defaulting to SOL/USDT:USDT", flush=True)
        return "SOL/USDT:USDT"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = "I am running a high-frequency momentum bot on Bitget Futures. Reply with ONLY the ticker symbol of a highly volatile altcoin (e.g., SOL, WIF, PEPE, DOGE). Format it exactly like this: 'SOL/USDT:USDT'. Do not include any other text."
    
    payload = {
        "model": "openrouter/free", 
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
        data = response.json()
        
        if 'choices' in data and len(data['choices']) > 0:
            symbol = data['choices'][0]['message']['content'].strip()
            symbol = symbol.replace('"', '').replace("'", "").split('\n')[0].strip()
            print(f"🎯 AI Selected: {symbol}", flush=True)
            return symbol
        else:
            print(f"⚠️ AI returned unexpected format: {data}", flush=True)
            return "SOL/USDT:USDT"
            
    except Exception as e:
        print(f"⚠️ AI Failed: {e}. Defaulting to SOL.", flush=True)
        return "SOL/USDT:USDT"

# --- 3. Main Execution Loop ---
async def main():
    target_coin = get_ai_target_coin()

    print("🚀 Starting Bitget Connection...", flush=True)
    exchange = ccxtpro.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })

    strategy = MicroMomentumStrategy(target_coin)
    print(f"🔗 Bot Started. Strategy: {strategy.name}", flush=True)

    last_summary_time = time.time()
    trades = 0

    while True:
        try:
            if time.time() - last_summary_time >= 600:
                print(f"\n📊 10-MIN SUMMARY | Trades: {trades} | Current Price: {strategy.peak_price}", flush=True)
                last_summary_time = time.time()

            # FIXED: Use watch_ticker instead of watch_trades to avoid list/dict errors
            ticker = await exchange.watch_ticker(target_coin)
            
            if 'last' not in ticker or ticker['last'] is None:
                continue
                
            current_price = ticker['last']
            signal = strategy.analyze(current_price)
            
            if signal == "BUY":
                print(f"🚀 IGNITION! BUY {target_coin} at {current_price}", flush=True)
                trades += 1
                # -> ADD REAL EXCHANGE BUY ORDER HERE
                
            elif signal == "SELL_MOMENTUM_DIED":
                print(f"📉 MOMENTUM DIED. SELL at {current_price}", flush=True)
                # -> ADD REAL EXCHANGE SELL ORDER HERE

            elif signal == "SELL_TRAILING_STOP":
                print(f"🛑 PEAK DROP. SELL at {current_price}", flush=True)
                # -> ADD REAL EXCHANGE SELL ORDER HERE

            await asyncio.sleep(0.05) # 50 milliseconds loop speed

        except Exception as e:
            print(f"⚠️ Connection Error: {e}", flush=True)
            await asyncio.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main())
