import asyncio
import ccxt.pro as ccxtpro
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from strategies import ScalpingStrategy, TrendFollowingStrategy
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
SYMBOL = 'BTC/USDT:USDT'
PAPER_TRADING = True  # ⚠️ SET TO False TO USE REAL MONEY
TRADE_SIZE_USDT = 2.0 # Amount per trade
MAX_LOSS_STREAK = 3   # Switch strategy after 3 losses in a row
TAKE_PROFIT_PCT = 0.0042 # 0.42%
STOP_LOSS_PCT = 0.0042   # 0.42%

# ==========================================
# 1. KEEP-ALIVE SERVER (For Render Free Tier)
# ==========================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, format, *args): pass

def run_keepalive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# ==========================================
# 2. STRATEGY MANAGER (The Genius Fallback)
# ==========================================
class StrategyManager:
    def __init__(self):
        self.strategies = [ScalpingStrategy(), TrendFollowingStrategy()]
        self.current_index = 0
        self.loss_streak = 0

    def get_active_strategy(self):
        return self.strategies[self.current_index]

    def record_trade(self, profit_loss_pct):
        if profit_loss_pct < 0:
            self.loss_streak += 1
            print(f"🔴 LOSS! Streak: {self.loss_streak}/{MAX_LOSS_STREAK}")
            
            if self.loss_streak >= MAX_LOSS_STREAK:
                self.switch_strategy()
        else:
            print(f"🟢 WIN! Profit: {profit_loss_pct*100:.2f}%. Resetting streak.")
            self.loss_streak = 0

    def switch_strategy(self):
        self.loss_streak = 0
        old_strategy = self.get_active_strategy().name
        self.current_index = (self.current_index + 1) % len(self.strategies)
        new_strategy = self.get_active_strategy().name
        print(f"\n🚨 BLEEDING DETECTED! Firing {old_strategy}... Hiring {new_strategy}!\n")

# ==========================================
# 3. MAIN EXECUTION ENGINE
# ==========================================
async def main():
    exchange = ccxtpro.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })

    manager = StrategyManager()
    position = None 
    
    print(f"🚀 Bot Started | Paper Trading: {PAPER_TRADING}")
    print(f"🧠 Active Strategy: {manager.get_active_strategy().name}")

    while True:
        try:
            # 1. Get live millisecond order book & 1m candles
            orderbook = await exchange.watch_order_book(SYMBOL)
            candles = await exchange.fetch_ohlcv(SYMBOL, '1m', limit=30)
            
            current_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
            
            # 2. Manage Open Position
            if position:
                entry_price = position['entry']
                side = position['side']
                
                if side == "BUY":
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price

                if pnl_pct >= TAKE_PROFIT_PCT or pnl_pct <= -STOP_LOSS_PCT:
                    print(f"🚪 Closing {side} position at {current_price:.2f} | PnL: {pnl_pct*100:.2f}%")
                    
                    if not PAPER_TRADING:
                        close_side = 'sell' if side == 'BUY' else 'buy'
                        await exchange.create_market_order(SYMBOL, close_side, position['amount'])
                    
                    manager.record_trade(pnl_pct)
                    position = None 
                    
                await asyncio.sleep(0.5) 
                continue

            # 3. Look for New Entries
            active_strategy = manager.get_active_strategy()
            signal = active_strategy.analyze(orderbook, candles)
            
            if signal in ["BUY", "SELL"]:
                print(f"🎯 [{active_strategy.name}] Signal: {signal} at {current_price:.2f}")
                
                amount = TRADE_SIZE_USDT / current_price
                
                if not PAPER_TRADING:
                    await exchange.create_market_order(SYMBOL, signal.lower(), amount)
                
                position = {
                    "side": signal,
                    "entry": current_price,
                    "amount": amount
                }

            await asyncio.sleep(0.1) 

        except Exception as e:
            print(f"⚠️ Error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main())
