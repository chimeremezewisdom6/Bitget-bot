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

# ==================== CONFIGURATION ====================
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

# ==================== KEEP-ALIVE SERVER ====================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, format, *args): pass

def run_keepalive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# ==================== STATE MANAGEMENT ====================
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

# ==================== AI ENGINE (With 10x Retry) ====================
def ask_ai(prompt, max_retries=10):
    """Calls Pollinations AI with an aggressive retry loop."""
    if not POLLINATIONS_KEY: return "AI key missing."
    
    url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai&token={POLLINATIONS_KEY}"
    
    for attempt in range(max_retries):
        try:
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                text = res.text.strip()
                # Check if Pollinations returned a real answer (not an error page)
                if text and len(text) > 10 and "error" not in text.lower():
                    return text
        except Exception as e:
            log.warning(f"AI attempt {attempt+1}/10 failed: {e}")
            
        # Wait 3 seconds before rechecking
        time.sleep(3)
            
    return "⚠️ AI analysis failed after 10 attempts. (The trade proceeded without analysis to not miss the entry window)."

async def ai_reporter(state):
    while True:
        await asyncio.sleep(600)
        status = f"Holding {CURRENT_CANDIDATE['direction']} on {CURRENT_CANDIDATE['symbol']}." if CURRENT_CANDIDATE else "Waiting for GitHub scanner."
        prompt = f"Facts: Win streak {state['streak']}/8. Mode {'UNLOCKED' if state['unlocked'] else 'LOCKED'}. Status: {status}. Last action: {CURRENT_ACTION}. Write exactly 2 sentences."
        log.info("🧠 Generating 10-minute AI summary...")
        ai_summary = await asyncio.to_thread(ask_ai, prompt, 3) # Only retry 3x for regular reports
        log.info(f"\n📊 10-MIN AI REPORT:\n{ai_summary}\n")

def ask_ai_risk_manager(symbol, direction, current_pnl):
    prompt = f"I am in a {direction} trade on {symbol}, losing {current_pnl*100:.2f}%. Explain in 1 sentence what is going wrong. End with '[ACTION: CUT]' or '[ACTION: HOLD]'."
    return ask_ai(prompt, 2) # Only retry 2x for emergency checks

# ==================== GITHUB PINGER ====================
async def github_pinger():
    if not GITHUB_TOKEN: return
    url = "https://api.github.com/repos/chimeremezewisdom6/Bitget-bot/actions/workflows/scanner.yml/dispatches"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    while True:
        try:
            res = requests.post(url, headers=headers, json={"ref": "main"}, timeout=10)
            if res.status_code == 204: log.info("🔔 Successfully pinged GitHub to run a new 100-bot scan.")
        except Exception: pass
        await asyncio.sleep(600) 

# ==================== CANDIDATE CHECKER ====================
async def check_for_candidate():
    try:
        res = requests.get("https://raw.githubusercontent.com/chimeremezewisdom6/Bitget-bot/main/candidate.json", timeout=10)
        data = res.json()
        return data if "symbol" in data else None
    except Exception: return None

# ==================== TRADE EXECUTION ====================
async def execute_trade(exchange, candidate, state):
    global CURRENT_CANDIDATE, CURRENT_ACTION
    CURRENT_CANDIDATE = candidate
    sym, direction = candidate['symbol'], candidate['direction']
    
    # ----------------------------------------
    # 1. ENTRY AI ANALYSIS
    # ----------------------------------------
    log.info("🧠 AI is analyzing the entry 10-minute price sequence...")
    sequence_str = json.dumps(candidate['sequence'])
    entry_prompt = (
        f"You are an expert crypto trader. The price of {sym} moved {candidate['move']:.2f}% in the last 10 minutes. "
        f"Here is the exact candle sequence (Open, High, Low, Close, Volume): {sequence_str}. "
        f"Winning volume was {candidate['win_vol']*100:.1f}%, losing volume was {candidate['lose_vol']*100:.1f}%. "
        f"Look at the bodies and wicks. Tell me in 2 sentences exactly what moved the price. "
        f"Was it aggressive buyers stepping in? Was it a lack of sellers? Was it a fakeout rejection?"
    )
    entry_analysis = await asyncio.to_thread(ask_ai, entry_prompt)
    
    log.info(f"==================================================")
    log.info(f"🧠 ENTRY ANALYSIS:\n{entry_analysis}")
    log.info(f"==================================================")

    # ----------------------------------------
    # 2. OPEN THE TRADE
    # ----------------------------------------
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
        log.info(f"❌ Balance too small for {sym} (requires {required_leverage}x). Skipping.")
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

    # ----------------------------------------
    # 3. MONITOR FOR 10 MINUTES
    # ----------------------------------------
    start_time = time.time()
    exit_reason = "timeout_10min"
    current_px = entry_px

    while time.time() - start_time < 600:
        await asyncio.sleep(5)
        try:
            ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
            current_px = ticker['last']
            if direction == "LONG": pnl = (current_px - entry_px) / entry_px
            else: pnl = (entry_px - current_px) / entry_px
            
            # Emergency stop loss
            if pnl <= -0.015: 
                exit_reason = "stop_loss"
                break
                
            # AI Risk Manager if bleeding
            if pnl < -0.005 and pnl > -0.015:
                ai_decision = await asyncio.to_thread(ask_ai_risk_manager, sym, direction, pnl)
                if "CUT" in ai_decision.upper():
                    log.info(f"\n🤖 AI RISK MANAGER:\n{ai_decision}\n")
                    exit_reason = "ai_cut"
                    break
                    
        except Exception: pass

    # ----------------------------------------
    # 4. CLOSE THE TRADE & CALCULATE EXIT VOLUMES
    # ----------------------------------------
    close_win_vol, close_lose_vol = 0, 0
    exit_sequence_str = "No sequence data"
    try:
        ohlcv = await exchange.fetch_ohlcv(market_sym, timeframe='1m', limit=10)
        if ohlcv and len(ohlcv) >= 10:
            green = sum(c[5] for c in ohlcv if c[4] > c[1] and c[5] is not None)
            red = sum(c[5] for c in ohlcv if c[4] < c[1] and c[5] is not None)
            total = green + red
            if total > 0:
                close_green = (green / total) * 100
                close_red = (red / total) * 100
                if direction == "LONG":
                    close_win_vol, close_lose_vol = close_green, close_red
                else:
                    close_win_vol, close_lose_vol = close_red, close_green
            
            exit_seq = [{"o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": c[5]} for c in ohlcv]
            exit_sequence_str = json.dumps(exit_seq)
    except Exception: pass

    final = current_px
    gross = (final - entry_px) / entry_px if direction == "LONG" else (entry_px - final) / entry_px
    net = gross - FEE_ROUND_TRIP
    
    log.info(f"==================================================")
    log.info(f"📉 [{mode}] CLOSED {direction} ON {sym} ({exit_reason})")
    log.info(f"   Closing Price: {final:.6f}")
    log.info(f"   Closing Volumes: Winning {close_win_vol:.1f}% | Losing {close_lose_vol:.1f}%")
    log.info(f"   Net PnL: {net*100:+.2f}%")
    log.info(f"==================================================")
    
    CURRENT_ACTION = f"Closed {direction} {sym} ({exit_reason}). Net: {net*100:.2f}%"

    if is_live:
        close_side = "sell" if direction == "LONG" else "buy"
        try: await exchange.create_order(market_sym, "market", close_side, amount, params={'uta': True, 'reduceOnly': 'yes'})
        except Exception as e: log.critical(f"🚨 [LIVE] FAILED TO CLOSE! Error: {e}")

    # ----------------------------------------
    # 5. EXIT AI ANALYSIS
    # ----------------------------------------
    log.info("🧠 AI is analyzing the trade result...")
    exit_prompt = (
        f"You are an expert crypto trader. I just closed a {direction} trade on {sym}. "
        f"Entry Price: {entry_px}, Exit Price: {final}. Net PnL: {net*100:.2f}%. Exit Reason: {exit_reason}. "
        f"Entry Volume: Winning {candidate['win_vol']*100:.1f}% vs Losing {candidate['lose_vol']*100:.1f}%. "
        f"Exit Volume: Winning {close_win_vol:.1f}% vs Losing {close_lose_vol:.1f}%. "
        f"Here is the closing candle sequence: {exit_sequence_str}. "
        f"Explain in 2 sentences what happened during this trade and why it won or lost. Be precise."
    )
    exit_analysis = await asyncio.to_thread(ask_ai, exit_prompt)
    
    log.info(f"==================================================")
    log.info(f"🧠 EXIT ANALYSIS:\n{exit_analysis}")
    log.info(f"==================================================")

    # ----------------------------------------
    # 6. UPDATE GATE & CLEANUP
    # ----------------------------------------
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

# ==================== MAIN LOOP ====================
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
                log.info(f"🎯 Received candidate from GitHub: {candidate['symbol']} ({candidate['direction']})")
                last_traded = candidate['symbol']
                await execute_trade(exchange, candidate, state)
            else:
                await asyncio.sleep(30)
        except Exception: await asyncio.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    asyncio.run(main_loop())
