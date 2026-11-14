import asyncio
import ccxt.pro as ccxtpro
import ccxt.async_support as ccxt_async
import json
import logging
import os
import requests
import threading
import time
import math
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

BITGET_API_KEY = os.environ.get("BITGET_API_KEY", "")
BITGET_SECRET = os.environ.get("BITGET_SECRET", "")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE", "")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "NO") == "YES"

FEE_ROUND_TRIP = 0.0012
GATE_WINS_REQUIRED = 8
GATE_MIN_NET = 0.0042
STATE_FILE = "state.json"
MAX_LEVERAGE = 5 

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# Keep track of the last time a coin fired to prevent spamming
last_trade_time = {}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, format, *args): pass

def run_keepalive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {"streak": 0, "unlocked": False}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f: json.dump(state, f)
    except Exception: pass

# ==========================================
# TRADE EXECUTION
# ==========================================
async def execute_trade(exchange, sym, direction, state, ignition_data):
    market_sym = f"{sym}/USDT:USDT"
    market = exchange.market(market_sym)
    if not market: return

    try:
        balance = await exchange.fetch_balance(params={'uta': True})
        usdt_free = balance['USDT']['free']
        ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
        entry_px = ticker['last']
    except Exception as e:
        return

    min_amt = market['limits']['amount']['min']
    required_leverage = math.ceil((min_amt * entry_px) / (usdt_free * 0.90)) if usdt_free > 0 else 999

    if required_leverage > MAX_LEVERAGE:
        log.info(f"❌ Balance too small for {sym}")
        return

    await exchange.set_leverage(required_leverage, market_sym, params={'uta': True})
    amount = float(exchange.amount_to_precision(market_sym, (usdt_free * 0.90 * required_leverage) / entry_px))
    
    is_live = LIVE_TRADING and state["unlocked"]
    mode = "LIVE" if is_live else "PAPER"
    
    log.info(f"==================================================")
    log.info(f"⚡ 1-MINUTE IGNITION DETECTED!")
    log.info(f"   Symbol: {sym} | Direction: {direction}")
    log.info(f"   Move: {ignition_data['move']}% | Vol Spike: {ignition_data['vol_spike']}x")
    log.info(f"🚀 [{mode}] OPENING {direction} | Price: {entry_px} | Size: {amount}")
    log.info(f"==================================================")
    
    last_trade_time[sym] = time.time()

    if is_live:
        side = "buy" if direction == "LONG" else "sell"
        try: await exchange.create_order(market_sym, "market", side, amount, params={'uta': True, 'reduceOnly': 'no'})
        except Exception as e: return

    # Monitor Trade
    start_time = time.time()
    current_px = entry_px
    peak_px = entry_px
    breakeven_locked = False
    
    while time.time() - start_time < 600: 
        await asyncio.sleep(1) 
        try:
            ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
            current_px = ticker['last']
            
            if direction == "LONG":
                pnl = (current_px - entry_px) / entry_px
                peak_px = max(peak_px, current_px)
            else:
                pnl = (entry_px - current_px) / entry_px
                peak_px = min(peak_px, current_px)

            if pnl <= -0.015: break
            if pnl >= 0.003: breakeven_locked = True

            if breakeven_locked:
                if direction == "LONG":
                    if (peak_px - current_px) / peak_px >= 0.004 or pnl <= 0: break
                else:
                    if (current_px - peak_px) / peak_px >= 0.004 or pnl <= 0: break
                        
        except Exception: pass

    gross = (current_px - entry_px) / entry_px if direction == "LONG" else (entry_px - current_px) / entry_px
    net = gross - FEE_ROUND_TRIP
    log.info(f"📉 [{mode}] CLOSED {direction} ON {sym} | Net PnL: {net*100:+.2f}%")
    
    if is_live:
        close_side = "sell" if direction == "LONG" else "buy"
        try: await exchange.create_order(market_sym, "market", close_side, amount, params={'uta': True, 'reduceOnly': 'yes'})
        except Exception: pass

    if net >= GATE_MIN_NET:
        state["streak"] += 1
        log.info(f"✅ WIN! Streak: {state['streak']}/8")
    else:
        state["streak"] = 0
        log.info(f"❌ LOSS. Streak reset to 0.")

    save_state(state)

# ==========================================
# THE MARKET SCANNER (Runs on Render every 15s)
# ==========================================
async def scan_market_for_ignition(exchange_rest, exchange_ws, state):
    """Fetches all tickers, finds the biggest sudden movers, and checks their 1m candles."""
    try:
        # 1. Fetch all live tickers from Bitget
        tickers = await exchange_rest.fetch_tickers()
        
        movers = []
        for sym, ticker in tickers.items():
            if not sym.endswith("USDT:USDT"): continue
            base = sym.split('/')[0]
            if base in MEGA_COINS: continue
            
            vol_24h = ticker.get('quoteVolume')
            if not vol_24h or float(vol_24h) < 1_000_000: continue
            
            # Check if it moved in the last 1 minute (ticker percentage is 24h, but we can use it to filter fast)
            # Actually, we just grab the top 50 by absolute 24h change to check their candles.
            change = ticker.get('percentage', 0)
            if change: movers.append((sym, abs(change)))
            
        # 2. Take the top 30 most volatile coins right now
        movers.sort(key=lambda x: x[1], reverse=True)
        top_movers = [m[0] for m in movers[:30]]
        
        # 3. Check their 1-minute candles for Ignition
        for market_sym in top_movers:
            base = market_sym.split('/')[0]
            
            # Don't scan if we just traded it in the last 5 minutes
            if base in last_trade_time and (time.time() - last_trade_time[base]) < 300:
                continue
                
            # Fetch the last 20 candles
            candles = await exchange_rest.fetch_ohlcv(market_sym, '1m', limit=20)
            if len(candles) < 20: continue
            
            closed_candle = candles[-2]
            base_candles = candles[:-2]
            
            # Check Quiet Base
            base_high = max(c[2] for c in base_candles)
            base_low = min(c[3] for c in base_candles)
            base_range = ((base_high - base_low) / base_low) * 100
            
            if base_range > 1.0: continue
                
            base_vol_avg = sum(c[5] for c in base_candles) / len(base_candles)
            if base_vol_avg == 0: continue
                
            o, h, l, c, v = closed_candle[1], closed_candle[2], closed_candle[3], closed_candle[4], closed_candle[5]
            total_range = h - l
            if total_range == 0: continue
            
            body_ratio = abs(c - o) / total_range
            move_pct = (abs(c - o) / o) * 100
            vol_spike = v / base_vol_avg
            
            # THE TRIGGER
            if move_pct >= 0.50 and body_ratio >= 0.75 and vol_spike >= 3.0:
                direction = "LONG" if c > o else "SHORT"
                ignition_data = {"move": round(move_pct, 2), "vol_spike": round(vol_spike, 1)}
                
                # Fire the trade using the WebSocket exchange instance
                await execute_trade(exchange_ws, base, direction, state, ignition_data)
                
    except Exception as e:
        log.error(f"Scanner error: {e}")

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================
async def main():
    threading.Thread(target=run_keepalive, daemon=True).start()
    
    state = load_state()
    log.info(f"Executor starting | Mode: {'LIVE' if LIVE_TRADING and state['unlocked'] else 'PAPER'} | Streak: {state['streak']}/8")
    
    # We need two instances: one for REST polling (scanning), one for WebSocket (trading)
    exchange_rest = ccxt_async.bitget({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
    
    exchange_ws = ccxtpro.bitget({
        'apiKey': BITGET_API_KEY, 
        'secret': BITGET_SECRET, 
        'password': BITGET_PASSPHRASE, 
        'enableRateLimit': True, 
        'options': {'defaultType': 'swap', 'uta': True}
    })
    
    try:
        await exchange_rest.load_markets()
        await exchange_ws.load_markets()
    except Exception:
        return

    log.info("📡 Live Market Scanner Active. Checking top movers every 15 seconds...")

    while True:
        try:
            # Scan the entire market for ignition every 15 seconds
            await scan_market_for_ignition(exchange_rest, exchange_ws, state)
            await asyncio.sleep(15)
            
        except Exception as e:
            log.error(f"Main loop error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
