"""
SINGLE-FILE MASTERPIECE: Global Momentum Bot with Human-Like AI Risk Manager.
"""
import asyncio
import ccxt.async_support as ccxt
import ccxt.pro as ccxtpro
import json
import logging
import os
import requests
import threading
import time
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. CONFIGURATION & KEYS
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

BITGET_API_KEY = os.environ.get("BITGET_API_KEY", "")
BITGET_SECRET = os.environ.get("BITGET_SECRET", "")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE", "")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "NO") == "YES"
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_API_KEY", "")

POSITION_USD = 1.50
LEVERAGE = 5
FEE_ROUND_TRIP = 0.0012
GATE_WINS_REQUIRED = 8
GATE_MIN_NET = 0.0042
STATE_FILE = "state.json"

# ==========================================
# 2. KEEP-ALIVE SERVER (For Render)
# ==========================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, format, *args): pass

def run_keepalive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# ==========================================
# 3. STATE & 8-WIN GATE
# ==========================================
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"streak": 0, "unlocked": False}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

# ==========================================
# 4. THE HUMAN-LIKE AI RISK MANAGER
# ==========================================
def ask_ai_risk_manager(symbol, direction, current_pnl, price_change):
    if not POLLINATIONS_KEY:
        return "HOLD"
        
    prompt = (
        f"You are an expert crypto trader managing my live trade. "
        f"I am currently in a {direction} trade on {symbol}. "
        f"The 10-minute entry momentum was {price_change:.2f}%. "
        f"I am currently losing {current_pnl*100:.2f}%. The momentum is fading against me. "
        f"Explain in a short paragraph exactly what is going wrong with this trade and how we can trade to profit from this situation. "
        f"End your response with exactly '[ACTION: CUT]' if I should close the trade immediately, "
        f"or '[ACTION: HOLD]' if I should wait. Do not write anything after the action tag."
    )
    
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai"
        res = requests.get(url, timeout=15)
        return res.text.strip()
    except Exception as e:
        log.warning(f"AI Risk Manager failed: {e}. Defaulting to HOLD.")
        return "HOLD"

# ==========================================
# 5. THE 100-SEQUENCE BACKTESTER
# ==========================================
def run_backtest(candles):
    best_seq = None
    best_win_rate = -1
    best_net_pnl = -999

    for ratio_trig in [3, 4, 5, 6, 7]:
        for strength_trig in [0.70, 0.75, 0.80, 0.85, 0.90]:
            for fade_trig in [1.5, 2.0, 2.5, 3.0]:
                trades = []
                for i in range(5, len(candles)-1):
                    c = candles[i]
                    c_next = candles[i+1]
                    rng = c[2] - c[3]
                    clv = (c[4] - c[3]) / rng if rng > 0 else 0.5
                    b = c[5] * clv
                    s = c[5] - b
                    
                    strength = max(b, s) / (b + s) if (b+s) > 0 else 0
                    ratio = max(b, s) / min(b, s) if min(b, s) > 0 else 999
                    
                    if ratio >= ratio_trig and strength >= strength_trig:
                        side = 1 if b >= s else -1
                        entry = c_next[1]
                        exit_px = c_next[4]
                        gross = side * ((exit_px - entry) / entry)
                        net = gross - FEE_ROUND_TRIP
                        trades.append(net)
                        
                if len(trades) >= 3:
                    wins = sum(1 for x in trades if x > 0)
                    win_rate = wins / len(trades)
                    net_pnl = sum(trades)
                    if win_rate > best_win_rate or (win_rate == best_win_rate and net_pnl > best_net_pnl):
                        best_win_rate = win_rate
                        best_net_pnl = net_pnl
                        best_seq = {"ratio": ratio_trig, "strength": strength_trig, "fade": fade_trig, "win_rate": win_rate, "net": net_pnl}
    return best_seq

# ==========================================
# 6. THE AGGREGATED SCANNER
# ==========================================
def get_global_mover():
    log.info("🌐 Scanning global market via CoinPaprika...")
    try:
        res = requests.get("https://api.coinpaprika.com/v1/tickers", timeout=10)
        tickers = res.json()
        
        valid_symbols = []
        for t in tickers:
            vol = t.get('quotes', {}).get('USD', {}).get('volume_24h', 0)
            if vol and vol >= 1_000_000:
                valid_symbols.append(t['symbol'])
        
        top_movers = []
        for sym in valid_symbols[:40]:
            try:
                url = f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=1m&limit=60"
                kres = requests.get(url, timeout=5).json()
                if len(kres) < 60 or 'code' in kres: continue
                
                open_10m = float(kres[-11][1])
                close_now = float(kres[-1][4])
                price_change = ((close_now - open_10m) / open_10m) * 100
                
                vol_10m = sum(float(k[5]) for k in kres[-10:]) / 10
                vol_50m = sum(float(k[5]) for k in kres[:-10]) / 50
                surge = vol_10m / vol_50m if vol_50m > 0 else 1
                
                score = abs(price_change) * surge
                
                top_movers.append({
                    "symbol": sym,
                    "price_change": price_change,
                    "candles": kres,
                    "score": score
                })
            except Exception:
                continue
                
        if not top_movers:
            return None
            
        top_movers.sort(key=lambda x: x['score'], reverse=True)
        return top_movers[0]
    except Exception as e:
        log.error(f"Scanner failed: {e}")
        return None

# ==========================================
# 7. EXECUTOR (With AI Human Check-in)
# ==========================================
async def execute_trade(exchange, mover, state):
    sym = mover['symbol']
    price_change = mover['price_change']
    side = "buy" if price_change > 0 else "sell"
    direction = "LONG" if side == "buy" else "SHORT"
    
    log.info(f"🎯 Momentum Detected: {sym} moved {price_change:.2f}%. Direction: {direction}")
    
    best_seq = run_backtest(mover['candles'])
    if not best_seq:
        return
        
    is_live = LIVE_TRADING and state["unlocked"]
    mode = "LIVE" if is_live else "PAPER"
    
    log.info(f"🚀 [{mode}] Opening {direction} on {sym}...")
    entry_px = float(mover['candles'][-1][4])
    
    start_time = time.time()
    peak_px = entry_px
    exit_reason = "timeout"
    
    while time.time() - start_time < 600:
        await asyncio.sleep(5)
        try:
            ticker = await exchange.fetch_ticker(f"{sym}/USDT:USDT")
            current_px = ticker['last']
            
            if direction == "LONG":
                pnl = (current_px - entry_px) / entry_px
                peak_px = max(peak_px, current_px)
                
                if pnl < -0.005 and pnl > -0.015:
                    ai_decision = await asyncio.to_thread(ask_ai_risk_manager, sym, direction, pnl, price_change)
                    if "CUT" in ai_decision.upper():
                        log.info(f"\n🤖 AI TRADER ANALYSIS:\n{ai_decision}\n")
                        log.info(f"✂️ Cutting loss early at {pnl*100:.2f}% based on AI analysis.")
                        exit_reason = "ai_cut"
                        break
                    else:
                        log.info(f"\n🤖 AI TRADER ANALYSIS (Holding):\n{ai_decision}\n")
                
                if current_px < peak_px * 0.995: exit_reason = "fade"; break
                if pnl <= -0.015: exit_reason = "stop_loss"; break
            else:
                pnl = (entry_px - current_px) / entry_px
                peak_px = min(peak_px, current_px)
                
                if pnl < -0.005 and pnl > -0.015:
                    ai_decision = await asyncio.to_thread(ask_ai_risk_manager, sym, direction, pnl, price_change)
                    if "CUT" in ai_decision.upper():
                        log.info(f"\n🤖 AI TRADER ANALYSIS:\n{ai_decision}\n")
                        log.info(f"✂️ Cutting loss early at {pnl*100:.2f}% based on AI analysis.")
                        exit_reason = "ai_cut"
                        break
                    else:
                        log.info(f"\n🤖 AI TRADER ANALYSIS (Holding):\n{ai_decision}\n")
                        
                if current_px > peak_px * 1.005: exit_reason = "fade"; break
                if pnl <= -0.015: exit_reason = "stop_loss"; break
                
        except Exception:
            pass
            
    final_px = current_px if 'current_px' in locals() else entry_px
    if direction == "LONG": gross = (final_px - entry_px) / entry_px
    else: gross = (entry_px - final_px) / entry_px
    
    net = gross - FEE_ROUND_TRIP
    
    log.info(f"📉 [{mode}] Closed {direction} on {sym} ({exit_reason}) | Net: {net*100:.2f}%")
    
    if net >= GATE_MIN_NET:
        state["streak"] += 1
        log.info(f"✅ WIN! Streak: {state['streak']}/8")
    else:
        state["streak"] = 0
        log.info(f"❌ LOSS. Streak reset to 0.")
        
    if state["streak"] >= GATE_WINS_REQUIRED and not state["unlocked"]:
        state["unlocked"] = True
        log.info("🔥🔥🔥 GATE PASSED! Live trading UNLOCKED. 🔥🔥🔥")
        
    save_state(state)

# ==========================================
# 8. MAIN LOOP
# ==========================================
async def main_loop():
    state = load_state()
    log.info(f"Starting Bot | Mode: {'LIVE' if LIVE_TRADING and state['unlocked'] else 'PAPER'} | Streak: {state['streak']}/8")
    
    exchange = ccxtpro.bitget({
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })
    
    while True:
        try:
            mover = get_global_mover()
            if mover:
                await execute_trade(exchange, mover, state)
            else:
                await asyncio.sleep(60)
        except Exception as e:
            log.error(f"Main loop error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main_loop())
