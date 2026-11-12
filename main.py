import asyncio
import ccxt.pro as ccxtpro
import json
import logging
import os
import requests
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

BITGET_API_KEY = os.environ.get("BITGET_API_KEY", "")
BITGET_SECRET = os.environ.get("BITGET_SECRET", "")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE", "")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "NO") == "YES"
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_API_KEY", "")

FEE_ROUND_TRIP = 0.0012
GATE_WINS_REQUIRED = 8
GATE_MIN_NET = 0.0042
STATE_FILE = "state.json"

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

def ask_ai_risk_manager(symbol, direction, current_pnl, price_change):
    if not POLLINATIONS_KEY: return "HOLD"
    prompt = (
        f"You are an expert crypto trader managing my live trade. I am in a {direction} trade on {symbol}. "
        f"Entry momentum was {price_change:.2f}%. I am currently losing {current_pnl*100:.2f}%. "
        f"Explain in a short paragraph what is going wrong and how to trade to profit from here. "
        f"End with exactly '[ACTION: CUT]' or '[ACTION: HOLD]'."
    )
    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai"
        return requests.get(url, timeout=10).text.strip()
    except Exception:
        return "HOLD"

async def check_for_candidate():
    try:
        # REPLACE THE URL BELOW WITH YOUR ACTUAL GITHUB RAW URL
        url = "https://raw.githubusercontent.com/chimeremezewisdom6/Bitget-bot/main/candidate.json"
        res = requests.get(url, timeout=10)
        data = res.json()
        if "symbol" in data: return data
        return None
    except Exception:
        return None

async def execute_trade(exchange, candidate, state):
    sym = candidate['symbol']
    direction = candidate['direction']
    entry_px = candidate['entry_px']
    
    is_live = LIVE_TRADING and state["unlocked"]
    mode = "LIVE" if is_live else "PAPER"
    
    log.info(f"🚀 [{mode}] Opening {direction} on {sym} at {entry_px}...")
    
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
                    ai_decision = await asyncio.to_thread(ask_ai_risk_manager, sym, direction, pnl, 0)
                    if "CUT" in ai_decision.upper():
                        log.info(f"\n🤖 AI TRADER ANALYSIS:\n{ai_decision}\n")
                        exit_reason = "ai_cut"
                        break
                if current_px < peak_px * 0.995: exit_reason = "fade"; break
                if pnl <= -0.015: exit_reason = "stop_loss"; break
            else:
                pnl = (entry_px - current_px) / entry_px
                peak_px = min(peak_px, current_px)
                if pnl < -0.005 and pnl > -0.015:
                    ai_decision = await asyncio.to_thread(ask_ai_risk_manager, sym, direction, pnl, 0)
                    if "CUT" in ai_decision.upper():
                        log.info(f"\n🤖 AI TRADER ANALYSIS:\n{ai_decision}\n")
                        exit_reason = "ai_cut"
                        break
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

async def main_loop():
    state = load_state()
    log.info(f"Executor starting | Mode: {'LIVE' if LIVE_TRADING and state['unlocked'] else 'PAPER'} | Streak: {state['streak']}/8")
    
    exchange = ccxtpro.bitget({
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })
    
    last_candidate = None
    while True:
        try:
            candidate = await check_for_candidate()
            if candidate and candidate != last_candidate:
                log.info(f"🎯 Received new candidate: {candidate['symbol']}")
                last_candidate = candidate
                await execute_trade(exchange, candidate, state)
            else:
                await asyncio.sleep(30) # Check GitHub every 30s
        except Exception as e:
            log.error(f"Executor loop error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main_loop())
