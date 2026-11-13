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

def ask_ai(prompt):
    if not POLLINATIONS_KEY: return "AI key missing."
    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai&token={POLLINATIONS_KEY}"
        return requests.get(url, timeout=15).text.strip()
    except Exception as e:
        return f"AI failed: {e}"

async def github_pinger():
    if not GITHUB_TOKEN: return
    url = "https://api.github.com/repos/chimeremezewisdom6/Bitget-bot/actions/workflows/scanner.yml/dispatches"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    while True:
        try:
            res = requests.post(url, headers=headers, json={"ref": "main"}, timeout=10)
            if res.status_code == 204: log.info("🔔 Successfully pinged GitHub to run a new 100-bot scan.")
        except Exception: pass
        await asyncio.sleep(600) # Ping every 10 minutes

async def ai_reporter(state):
    while True:
        await asyncio.sleep(600)
        status = f"Holding {CURRENT_CANDIDATE['direction']} on {CURRENT_CANDIDATE['symbol']}." if CURRENT_CANDIDATE else "Waiting for GitHub scanner."
        prompt = f"Facts: Win streak {state['streak']}/8. Mode {'UNLOCKED' if state['unlocked'] else 'LOCKED'}. Status: {status}. Last action: {CURRENT_ACTION}. Write exactly 2 sentences."
        log.info("🧠 Generating 10-minute AI summary...")
        ai_summary = await asyncio.to_thread(ask_ai, prompt)
        log.info(f"\n📊 10-MIN AI REPORT:\n{ai_summary}\n")

def ask_ai_risk_manager(symbol, direction, current_pnl):
    prompt = f"I am in a {direction} trade on {symbol}, losing {current_pnl*100:.2f}%. Explain in 1 sentence what is going wrong. End with '[ACTION: CUT]' or '[ACTION: HOLD]'."
    return ask_ai(prompt)

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
    market_sym = f"{sym}/USDT:USDT"

    market = exchange.market(market_sym)
    if not market: CURRENT_CANDIDATE = None; return

    try:
        balance = await exchange.fetch_balance(params={'uta': True})
        usdt_free = balance['USDT']['free']
        ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
        price = ticker['last']
    except Exception: CURRENT_CANDIDATE = None; return

    min_amt = market['limits']['amount']['min']
    required_leverage = math.ceil((min_amt * price) / (usdt_free * 0.90)) if usdt_free > 0 else 999

    if required_leverage > MAX_LEVERAGE:
        log.info(f"❌ Balance too small for {sym} (requires {required_leverage}x). Skipping.")
        CURRENT_CANDIDATE = None; return

    await exchange.set_leverage(required_leverage, market_sym, params={'uta': True})
    
    amount = float(exchange.amount_to_precision(market_sym, (usdt_free * 0.90 * required_leverage) / price))
    is_live = LIVE_TRADING and state["unlocked"]
    mode = "LIVE" if is_live else "PAPER"
    
    CURRENT_ACTION = f"Opened {direction} on {sym} at {price}."
    log.info(f"🚀 [{mode}] Opening {direction} on {sym} | Size: {amount} @ {price}")

    if is_live:
        side = "buy" if direction == "LONG" else "sell"
        try: await exchange.create_order(market_sym, "market", side, amount, params={'uta': True, 'reduceOnly': 'no'})
        except Exception: CURRENT_CANDIDATE = None; return

    # MONITOR FOR EXACTLY 10 MINUTES (600 SECONDS)
    start_time = time.time()
    exit_reason = "timeout_10min"
    current = price

    while time.time() - start_time < 600:
        await asyncio.sleep(5)
        try:
            ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
            current = ticker['last']
            
            if direction == "LONG": pnl = (current - price) / price
            else: pnl = (price - current) / price

            if pnl <= -0.015: 
                exit_reason = "stop_loss"
                break
        except Exception: pass

    # CLOSE TRADE
    final = current
    gross = (final - price) / price if direction == "LONG" else (price - final) / price
    net = gross - FEE_ROUND_TRIP
    CURRENT_ACTION = f"Closed {direction} {sym} ({exit_reason}). Net: {net*100:.2f}%"
    log.info(f"📉 [{mode}] {CURRENT_ACTION}")

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
    asyncio.create_task(ai_reporter(state))

    last_traded = None
    while True:
        try:
            candidate = await check_for_candidate()
            if candidate and candidate['symbol'] != last_traded:
                log.info(f"🎯 Received DAVID candidate: {candidate['symbol']} ({candidate['direction']})")
                last_traded = candidate['symbol']
                await execute_trade(exchange, candidate, state)
            else:
                await asyncio.sleep(30)
        except Exception: await asyncio.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main_loop())
