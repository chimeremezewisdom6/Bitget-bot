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

FEE_ROUND_TRIP = 0.0012
GATE_WINS_REQUIRED = 8
GATE_MIN_NET = 0.0042
STATE_FILE = "state.json"

# --- LEVERAGE CAP ---
MAX_LEVERAGE = 5 

CURRENT_CANDIDATE = None
CURRENT_ACTION = "Waiting for the GitHub scanner to find the best fingerprint..."

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
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai"
        return requests.get(url, timeout=15).text.strip()
    except Exception as e:
        return f"AI failed: {e}"

async def ai_reporter(state):
    """Generates a human-like summary every 10 minutes."""
    while True:
        await asyncio.sleep(600)
        status = f"Currently holding {CURRENT_CANDIDATE['symbol']}." if CURRENT_CANDIDATE else "Waiting for the GitHub scanner to find a new 50-bot consensus."
        prompt = (
            f"You are my trading AI. Give me a 10-minute status report. Win streak: {state['streak']}/8. "
            f"Live mode: {'UNLOCKED' if state['unlocked'] else 'LOCKED'}. Status: {status}. Last action: {CURRENT_ACTION}. "
            f"Write exactly 2 professional sentences."
        )
        log.info("🧠 Generating 10-minute AI summary...")
        ai_summary = await asyncio.to_thread(ask_ai, prompt)
        log.info(f"\n📊 10-MIN AI REPORT:\n{ai_summary}\n")

def ask_ai_risk_manager(symbol, direction, current_pnl):
    """Asks the AI to decide whether to cut a losing trade early."""
    prompt = (
        f"I am in a {direction} trade on {symbol}, losing {current_pnl*100:.2f}%. "
        f"Explain in 1 sentence what is going wrong. End with '[ACTION: CUT]' or '[ACTION: HOLD]'."
    )
    return ask_ai(prompt)

async def check_for_candidate():
    try:
        # Make sure this URL matches your exact GitHub repo
        url = "https://raw.githubusercontent.com/chimeremezewisdom6/Bitget-bot/main/candidate.json"
        res = requests.get(url, timeout=10)
        data = res.json()
        if "symbol" in data: return data
        return None
    except Exception:
        return None

async def execute_trade(exchange, candidate, state):
    global CURRENT_CANDIDATE, CURRENT_ACTION
    CURRENT_CANDIDATE = candidate
    sym = candidate['symbol']
    direction = candidate['direction']
    market_sym = f"{sym}/USDT:USDT"

    # 1. Verify market exists
    market = exchange.market(market_sym)
    if not market:
        log.info(f"❌ {sym} not found on Bitget execution markets. Skipping.")
        CURRENT_CANDIDATE = None
        return

    # 2. Fetch balance & price (UTA Mode)
    try:
        balance = await exchange.fetch_balance(params={'uta': True})
        usdt_free = balance['USDT']['free']
        ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
        price = ticker['last']
    except Exception as e:
        log.error(f"❌ Failed to fetch UTA balance/price: {e}")
        CURRENT_CANDIDATE = None
        return

    # 3. Small Balance Check ($1.58 Logic)
    min_amt = market['limits']['amount']['min']
    min_notional = min_amt * price
    
    # We use 90% of balance to avoid margin errors. 
    # How much leverage do we need to afford the minimum order?
    required_leverage = math.ceil(min_notional / (usdt_free * 0.90)) if usdt_free > 0 else 999

    # STRICT 5X LEVERAGE CAP
    if required_leverage > MAX_LEVERAGE:
        log.info(f"❌ Balance ${usdt_free:.2f} too small for {sym} (min notional ${min_notional:.2f}, requires {required_leverage}x leverage). Max allowed is {MAX_LEVERAGE}x. Skipping.")
        CURRENT_CANDIDATE = None
        return

    # 4. Set Leverage (UTA Mode)
    try:
        await exchange.set_leverage(required_leverage, market_sym, params={'uta': True})
        log.info(f"⚙️ Leverage set to {required_leverage}x for {sym}.")
    except Exception as e:
        log.error(f"❌ Failed to set leverage: {e}")
        CURRENT_CANDIDATE = None
        return

    # 5. Calculate Order Size
    side = "buy" if direction == "LONG" else "sell"
    amount = (usdt_free * 0.90 * required_leverage) / price
    amount = float(exchange.amount_to_precision(market_sym, amount))

    if amount < min_amt:
        log.info(f"❌ Calculated amount {amount} below minimum {min_amt}. Skipping.")
        CURRENT_CANDIDATE = None
        return

    is_live = LIVE_TRADING and state["unlocked"]
    mode = "LIVE" if is_live else "PAPER"
    CURRENT_ACTION = f"Opened {direction} {sym} at {price}."
    log.info(f"🚀 [{mode}] Opening {direction} on {sym} | Size: {amount} @ {price}")

    # 6. Open Order (UTA Mode, One-Way)
    if is_live:
        try:
            # One-way mode: no posSide, reduceOnly='no'
            await exchange.create_order(market_sym, "market", side, amount, params={'uta': True, 'reduceOnly': 'no'})
        except Exception as e:
            log.error(f"❌ [LIVE] Failed to open order: {e}")
            CURRENT_CANDIDATE = None
            return

    # 7. Monitor Trade (Max 10 Minutes)
    start_time = time.time()
    peak = price
    exit_reason = "timeout"
    current = price

    while time.time() - start_time < 600:
        await asyncio.sleep(5)
        try:
            ticker = await exchange.fetch_ticker(market_sym, params={'uta': True})
            current = ticker['last']
            pnl = (current - price) / price if direction == "LONG" else (price - current) / price

            if direction == "LONG":
                peak = max(peak, current)
                # AI Risk Manager check if bleeding
                if pnl < -0.005 and pnl > -0.015:
                    ai_decision = await asyncio.to_thread(ask_ai_risk_manager, sym, direction, pnl)
                    if "CUT" in ai_decision.upper():
                        log.info(f"\n🤖 AI RISK MANAGER:\n{ai_decision}\n")
                        exit_reason = "ai_cut"
                        break
                if current < peak * 0.995: exit_reason = "fade"; break
                if pnl <= -0.015: exit_reason = "stop_loss"; break
            else:
                peak = min(peak, current)
                if pnl < -0.005 and pnl > -0.015:
                    ai_decision = await asyncio.to_thread(ask_ai_risk_manager, sym, direction, pnl)
                    if "CUT" in ai_decision.upper():
                        log.info(f"\n🤖 AI RISK MANAGER:\n{ai_decision}\n")
                        exit_reason = "ai_cut"
                        break
                if current > peak * 1.005: exit_reason = "fade"; break
                if pnl <= -0.015: exit_reason = "stop_loss"; break
        except Exception as e:
            log.error(f"Monitoring error: {e}")

    # 8. Close Order (UTA Mode, One-Way, ReduceOnly)
    final = current
    gross = (final - price) / price if direction == "LONG" else (price - final) / price
    net = gross - FEE_ROUND_TRIP
    CURRENT_ACTION = f"Closed {direction} {sym} ({exit_reason}). Net: {net*100:.2f}%"
    log.info(f"📉 [{mode}] {CURRENT_ACTION}")

    if is_live:
        close_side = "sell" if direction == "LONG" else "buy"
        try:
            # One-way mode: no posSide, reduceOnly='yes'
            await exchange.create_order(market_sym, "market", close_side, amount, params={'uta': True, 'reduceOnly': 'yes'})
            log.info(f"✅ [LIVE] Position closed safely.")
        except Exception as e:
            log.critical(f"🚨 [LIVE] FAILED TO CLOSE POSITION! CLOSE MANUALLY! Error: {e}")

    # 9. Update the 8-Win Gate
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
    
    exchange = ccxtpro.bitget({
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
        'enableRateLimit': True,
        'options': {'defaultType': 'swap', 'uta': True}
    })
    
    last_candidate = None
    while True:
        try:
            candidate = await check_for_candidate()
            if candidate and candidate != last_candidate:
                log.info(f"🎯 Received candidate from GitHub: {candidate['symbol']}")
                last_candidate = candidate
                await execute_trade(exchange, candidate, state)
            else:
                await asyncio.sleep(30)
        except Exception as e:
            log.error(f"Executor loop error: {e}")
            await asyncio.sleep(10)

async def main():
    threading.Thread(target=run_keepalive, daemon=True).start()
    await asyncio.gather(main_loop(), ai_reporter(load_state()))

if __name__ == "__main__":
    asyncio.run(main())
