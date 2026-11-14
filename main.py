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

# ... [Keep all API keys and State configs exactly the same] ...

def ask_ai(prompt):
    if not POLLINATIONS_KEY: return "AI key missing."
    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai&token={POLLINATIONS_KEY}"
        return requests.get(url, timeout=20).text.strip() # Increased timeout
    except Exception as e:
        return f"AI failed: {e}"

async def execute_trade(exchange, candidate, state):
    global CURRENT_CANDIDATE, CURRENT_ACTION
    CURRENT_CANDIDATE = candidate
    sym, direction = candidate['symbol'], candidate['direction']
    
    # 1. AI READS THE SEQUENCE BEFORE ENTERING
    log.info("🧠 AI is analyzing the 10-minute price sequence...")
    sequence_str = json.dumps(candidate['sequence'])
    prompt = (
        f"You are an expert crypto trader. The price of {sym} moved {candidate['move']:.2f}% in the last 10 minutes. "
        f"Here is the exact candle sequence (Open, High, Low, Close, Volume): {sequence_str}. "
        f"The winning volume was {candidate['win_vol']*100:.1f}%, losing volume was {candidate['lose_vol']*100:.1f}%. "
        f"Look at the bodies and the wicks. Based ONLY on this data, tell me in 2 sentences exactly what moved the price. "
        f"Was it aggressive buyers stepping in? Was it a lack of sellers? Was it a fakeout rejection? Be precise."
    )
    ai_analysis = await asyncio.to_thread(ask_ai, prompt)
    
    log.info(f"==================================================")
    log.info(f"🧠 AI MARKET ANALYSIS:\n{ai_analysis}")
    log.info(f"==================================================")

    # 2. OPEN THE TRADE (Standard Logic)
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

    # ... [Keep the 10-minute monitor loop exactly the same] ...
    
    # ... [Keep the closing logic exactly the same] ...

# ... [Keep main_loop() and the rest of the file exactly the same] ...
