import asyncio
import ccxt.pro as ccxtpro
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

CURRENT_ACTION = "Waiting for WebSocket Ignition..."

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
# THE MILLISECOND TRADE EXECUTION
# ==========================================
async def execute_trade(exchange, sym, direction, state, ignition_data):
    global CURRENT_ACTION
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
        return

    await exchange.set_leverage(required_leverage, market_sym, params={'uta': True})
    amount = float(exchange.amount_to_precision(market_sym, (usdt_free * 0.90 * required_leverage) / entry_px))
    
    is_live = LIVE_TRADING and state["unlocked"]
    mode = "LIVE" if is_live else "PAPER"
    
    log.info(f"==================================================")
    log.info(f"⚡ MILLISECOND IGNITION DETECTED!")
    log.info(f"   Symbol: {sym} | Direction: {direction}")
    log.info(f"   Move: {ignition_data['move']}% | Vol Spike: {ignition_data['vol_spike']}x")
    log.info(f"🚀 [{mode}] OPENING {direction} | Price: {entry_px} | Size: {amount}")
    log.info(f"==================================================")
    
    CURRENT_ACTION = f"Opened {direction} on {sym} at {entry_px}."

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
# THE WEBSOCKET WATCHER
# ==========================================
async def watch_coin_ignition(exchange, sym, state):
    market_sym = f"{sym}/USDT:USDT"
    
    while True:
        try:
            ohlcvs = await exchange.watch_ohlcv(market_sym, '1m')
            
            if len(ohlcvs) < 20:
                continue
                
            closed_candle = ohlcvs[-2]
            base_candles = ohlcvs[-20:-1]
            
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
            
            if move_pct >= 0.50 and body_ratio >= 0.75 and vol_spike >= 3.0:
                direction = "LONG" if c > o else "SHORT"
                ignition_data = {"move": round(move_pct, 2), "vol_spike": round(vol_spike, 1)}
                
                await execute_trade(exchange, sym, direction, state, ignition_data)
                await asyncio.sleep(300) 
                
        except Exception:
            await asyncio.sleep(1)

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================
async def main():
    threading.Thread(target=run_keepalive, daemon=True).start()
    
    state = load_state()
    log.info(f"Executor starting | Mode: {'LIVE' if LIVE_TRADING and state['unlocked'] else 'PAPER'} | Streak: {state['streak']}/8")
    
    exchange = ccxtpro.bitget({
        'apiKey': BITGET_API_KEY, 
        'secret': BITGET_SECRET, 
        'password': BITGET_PASSPHRASE, 
        'enableRateLimit': True, 
        'options': {'defaultType': 'swap', 'uta': True}
    })
    
    try:
        await exchange.load_markets()
    except Exception:
        return

    active_watchers = {}
    
    while True:
        try:
            # Corrected URL: chimeremezewisdom6
            url = "https://raw.githubusercontent.com/chimeremezewisdom6/Bitget-bot/main/candidate.json"
            res = requests.get(url, timeout=10)
            
            if res.status_code != 200:
                log.warning(f"GitHub returned {res.status_code}. Waiting for watchlist...")
                await asyncio.sleep(30)
                continue
                
            try:
                data = res.json()
            except json.JSONDecodeError:
                log.warning(f"GitHub file is not valid JSON. It returned: {res.text[:50]}")
                await asyncio.sleep(30)
                continue
                
            watchlist = data.get("watchlist", [])
            
            if not watchlist:
                log.info("Watchlist empty. Waiting for GitHub scan...")
                await asyncio.sleep(30)
                continue
                
            log.info(f"📡 WebSocket active. Watching {len(watchlist)} coins for Ignition...")
            
            for sym in watchlist:
                if sym not in active_watchers:
                    task = asyncio.create_task(watch_coin_ignition(exchange, sym, state))
                    active_watchers[sym] = task
                    
            await asyncio.sleep(600)
            
        except Exception as e:
            log.error(f"Main loop error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
