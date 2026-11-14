import asyncio
import ccxt.pro as ccxtpro
import json
import logging
import os
import requests
import threading
import time
import math
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

BITGET_API_KEY = os.environ.get("BITGET_API_KEY", "")
BITGET_SECRET = os.environ.get("BITGET_SECRET", "")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE", "")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "NO") == "YES"
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

FEE_ROUND_TRIP = 0.0012
GATE_WINS_REQUIRED = 8
GATE_MIN_NET = 0.0042
STATE_FILE = "state.json"
MAX_LEVERAGE = 5 

CURRENT_CANDIDATE = None
CURRENT_ACTION = "Waiting for the GitHub scanner..."

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

def ask_ai(prompt, max_retries=5):
    if not POLLINATIONS_KEY: return "AI key missing."
    url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai&token={POLLINATIONS_KEY}"
    for attempt in range(max_retries):
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                text = res.text.strip()
                if text and len(text) > 10 and "error" not in text.lower():
                    return text
        except Exception: pass
        time.sleep(2)
    return "AI analysis unavailable."

async def github_pinger():
    if not GITHUB_TOKEN: return
    url = "https://api.github.com/repos/chimeremezewisdom6/Bitget-bot/actions/workflows/scanner.yml/dispatches"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    while True:
        try:
            res = requests.post(url, headers=headers, json={"ref": "main"}, timeout=10)
            if res.status_code == 204: log.info("🔔 Successfully pinged GitHub to run a new scan.")
        except Exception: pass
        await asyncio.sleep(600) 

async def check_for_candidate():
    try:
        res = requests.get("https://raw.githubusercontent.com/chimeremezewisdom6/Bitget-bot/main/candidate.json", timeout=10)
        data = res.json()
        return data if "symbol" in data else None
    except Exception: return None

async def execute_trade(exchange, candidate, state):
    global CURRENT_CANDIDATE, CURRENT_ACTION
    CURRENT_CANDIDATE = candidate
    sym, direction = candidate['symbol'], candidate['direction']
    
    log.info("🧠 AI is analyzing the Exhaustion Reversal...")
    sequence_str = json.dumps(candidate['sequence'])
    entry_prompt = (
        f"You are an expert crypto trader. The price of {sym} had a trend of {candidate.get('trend_30m', 0):.2f}% over 30m, "
        f"and is now making an early reversal {direction} at the '500m mark'. "
        f"Candle sequence: {sequence_str}. "
        f"Tell me in 2 sentences if the exhausted side is truly giving way."
    )
    entry_analysis = await asyncio.to_thread(ask_ai, entry_prompt)
    log.info(f"==================================================")
    log.info(f"🧠 ENTRY ANALYSIS:\n{entry_analysis}")
    log.info(f"==================================================")

    market_sym = f"{sym}/USDT:USDT"
    market = exchange.market(market_sym)
    if not market: CURRENT_CANDIDATE = None; return

    try:
        balance = await exchange.fetch_balance(params={'uta': True})
        usdt_free = balance['USDT']['free']
        ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
        entry_px = ticker['last']
    except Exception: CURRENT_CANDIDATE = None; return

    min_amt = market['limits']['amount']['min']
    required_leverage = math.ceil((min_amt * entry_px) / (usdt_free * 0.90)) if usdt_free > 0 else 999

    if required_leverage > MAX_LEVERAGE:
        log.info(f"❌ Balance too small for {sym}. Skipping.")
        CURRENT_CANDIDATE = None; return

    await exchange.set_leverage(required_leverage, market_sym, params={'uta': True})
    amount = float(exchange.amount_to_precision(market_sym, (usdt_free * 0.90 * required_leverage) / entry_px))
    
    is_live = LIVE_TRADING and state["unlocked"]
    mode = "LIVE" if is_live else "PAPER"
    
    log.info(f"🚀 [{mode}] OPENING {direction} ON {sym} | Price: {entry_px} | Size: {amount}")
    CURRENT_ACTION = f"Opened {direction} on {sym} at {entry_px}."

    if is_live:
        side = "buy" if direction == "LONG" else "sell"
        try: await exchange.create_order(market_sym, "market", side, amount, params={'uta': True, 'reduceOnly': 'no'})
        except Exception: CURRENT_CANDIDATE = None; return

    start_time = time.time()
    exit_reason = "timeout_5min"
    current_px = entry_px
    peak_px = entry_px
    breakeven_locked = False

    while time.time() - start_time < 300: # 5 mins max
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

            if pnl <= -0.015: 
                exit_reason = "hard_stop_loss"
                break
                
            if pnl >= 0.003:
                breakeven_locked = True

            if breakeven_locked:
                if direction == "LONG":
                    if (peak_px - current_px) / peak_px >= 0.004:
                        exit_reason = "trailing_stop_profit"
                        break
                    if pnl <= 0:
                        exit_reason = "breakeven_stop"
                        break
                else:
                    if (current_px - peak_px) / peak_px >= 0.004:
                        exit_reason = "trailing_stop_profit"
                        break
                    if pnl <= 0:
                        exit_reason = "breakeven_stop"
                        break
                        
        except Exception: pass

    final = current_px
    gross = (final - entry_px) / entry_px if direction == "LONG" else (entry_px - final) / entry_px
    net = gross - FEE_ROUND_TRIP
    
    log.info(f"==================================================")
    log.info(f"📉 [{mode}] CLOSED {direction} ON {sym} ({exit_reason})")
    log.info(f"   Net PnL: {net*100:+.2f}%")
    log.info(f"==================================================")
    
    if is_live:
        close_side = "sell" if direction == "LONG" else "buy"
        try: await exchange.create_order(market_sym, "market", close_side, amount, params={'uta': True, 'reduceOnly': 'yes'})
        except Exception as e: log.critical(f"🚨 [LIVE] FAILED TO CLOSE! Error: {e}")

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
    CURRENT_CANDIDATE = None

async def main_loop():
    state = load_state()
    log.info(f"Executor starting | Mode: {'LIVE' if LIVE_TRADING and state['unlocked'] else 'PAPER'} | Streak: {state['streak']}/8")
    
    exchange = ccxtpro.bitget({'apiKey': BITGET_API_KEY, 'secret': BITGET_SECRET, 'password': BITGET_PASSPHRASE, 'enableRateLimit': True, 'options': {'defaultType': 'swap', 'uta': True}})
    
    try:
        log.info("📥 Loading Bitget markets...")
        await exchange.load_markets()
        log.info(f"✅ Loaded {len(exchange.markets)} markets.")
    except Exception: return

    asyncio.create_task(github_pinger())

    last_traded = None
    while True:
        try:
            candidate = await check_for_candidate()
            if candidate and candidate['symbol'] != last_traded:
                log.info(f"🎯 Received Best Available Candidate: {candidate['symbol']} ({candidate['direction']})")
                last_traded = candidate['symbol']
                await execute_trade(exchange, candidate, state)
            else:
                await asyncio.sleep(30)
        except Exception: await asyncio.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main_loop())
