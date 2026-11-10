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
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# --- 2. Strategy Manager with Metrics Tracking ---
class StrategyManager:
    def __init__(self):
        self.strategies = [ScalpingStrategy(), TrendFollowingStrategy()]
        self.current_strategy_index = 0
        self.loss_streak = 0
        self.max_loss_streak = 3 
        
        # Metrics for the 10-minute summary
        self.trades_count = 0
        self.wins = 0
        self.losses = 0
        self.switches_count = 0

    def get_current_strategy(self):
        return self.strategies[self.current_strategy_index]

    def record_trade_result(self, profit_loss):
        self.trades_count += 1
        if profit_loss < 0:
            self.losses += 1
            self.loss_streak += 1
            if self.loss_streak >= self.max_loss_streak:
                self.switch_strategy()
        else:
            self.wins += 1
            self.loss_streak = 0

    def switch_strategy(self):
        self.loss_streak = 0
        self.switches_count += 1
        self.current_strategy_index = (self.current_strategy_index + 1) % len(self.strategies)

    def generate_summary(self, current_price, spread):
        strat = self.get_current_strategy()
        win_rate = (self.wins / self.trades_count * 100) if self.trades_count > 0 else 0
        
        summary = f"""
==================================================
📊 10-MINUTE BOT SUMMARY
==================================================
🧠 Active Strategy : {strat.name}
🔄 Strategy Switches: {self.switches_count}
--------------------------------------------------
💰 BTC Price       : ${current_price:.2f} (Spread: ${spread:.2f})
📈 Total Trades    : {self.trades_count}
✅ Wins            : {self.wins}
❌ Losses          : {self.losses}
🎯 Win Rate        : {win_rate:.1f}%
==================================================
"""
        print(summary, flush=True)
        
        # Reset interval metrics (optional: keep totals, reset 10-min window)
        self.trades_count = 0
        self.wins = 0
        self.losses = 0
        self.switches_count = 0


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

    last_summary_time = time.time()
    SUMMARY_INTERVAL = 600 # 10 minutes in seconds (600s)

    current_price = 0
    current_spread = 0

    while True:
        try:
            # 1. Check if 10 minutes have passed
            if time.time() - last_summary_time >= SUMMARY_INTERVAL:
                manager.generate_summary(current_price, current_spread)
                last_summary_time = time.time() # Reset timer

            # 2. Get Live Data
            orderbook = await exchange.watch_order_book(symbol)
            candles = await exchange.fetch_ohlcv(symbol, '1m', limit=30)
            
            best_bid = orderbook['bids'][0][0] if orderbook['bids'] else 0
            best_ask = orderbook['asks'][0][0] if orderbook['asks'] else 0
            current_price = best_bid
            current_spread = best_ask - best_bid
            
            # 3. Analyze
            active_strategy = manager.get_current_strategy()
            signal = active_strategy.analyze(orderbook, candles)
            
            # 4. Execute (Simulated for now)
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

            await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ Connection Error: {e}", flush=True)
            await asyncio.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main())
