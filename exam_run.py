import asyncio
import ccxt.pro as ccxtpro
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from strategies import ScalpingStrategy, TrendFollowingStrategy
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
    print(f"🌐 Keep-Alive Server running on port {port}...", flush=True)
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# --- 2. Strategy Manager ---
class StrategyManager:
    def __init__(self):
        self.strategies = [ScalpingStrategy(), TrendFollowingStrategy()]
        self.current_strategy_index = 0
        self.loss_streak = 0
        self.max_loss_streak = 3

    def get_current_strategy(self):
        return self.strategies[self.current_strategy_index]

    def record_trade_result(self, profit_loss):
        if profit_loss < 0:
            self.loss_streak += 1
            print(f"⚠️ Loss detected. Streak: {self.loss_streak}/{self.max_loss_streak}", flush=True)
            if self.loss_streak >= self.max_loss_streak:
                self.switch_strategy()
        else:
            print("✅ Win detected. Resetting loss streak.", flush=True)
            self.loss_streak = 0

    def switch_strategy(self):
        self.loss_streak = 0
        self.current_strategy_index = (self.current_strategy_index + 1) % len(self.strategies)
        new_strategy = self.get_current_strategy()
        print(f"\n🔄 BLEEDING DETECTED. SWITCHING TO ALTERNATIVE STYLE: {new_strategy.name}\n", flush=True)

# --- 3. Main Execution Loop ---
async def main():
    print("🚀 Starting Bitget connection...", flush=True)
    
    exchange = ccxtpro.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })

    symbol = 'BTC/USDT:USDT'
    manager = StrategyManager()
    
    print(f"🔗 Bot Started. Initial Strategy: {manager.get_current_strategy().name}", flush=True)

    last_heartbeat = time.time()

    while True:
        try:
            # 1. Heartbeat Log (Proves the bot is alive even if no trades happen)
            if time.time() - last_heartbeat > 10:
                print(f"💓 Heartbeat: Bot is alive and waiting for signals...", flush=True)
                last_heartbeat = time.time()

            # 2. Get Live Data
            orderbook = await exchange.watch_order_book(symbol)
            candles = await exchange.fetch_ohlcv(symbol, '1m', limit=30)
            
            # 3. Ask the active strategy what to do
            active_strategy = manager.get_current_strategy()
            signal = active_strategy.analyze(orderbook, candles)
            
            best_bid = orderbook['bids'][0][0] if orderbook['bids'] else 0
            
            if signal == "BUY":
                print(f"🟢 [{active_strategy.name}] Signal: BUY at {best_bid}", flush=True)
                import random
                simulated_pnl = random.choice([0.5, -0.5, 0.2, -0.8]) 
                manager.record_trade_result(simulated_pnl)
                
            elif signal == "SELL":
                print(f"🔴 [{active_strategy.name}] Signal: SELL at {best_bid}", flush=True)
                import random
                simulated_pnl = random.choice([0.5, -0.5, 0.2, -0.8])
                manager.record_trade_result(simulated_pnl)

            await asyncio.sleep(2)

        except Exception as e:
            print(f"⚠️ Connection Error: {e}", flush=True)
            await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main())
