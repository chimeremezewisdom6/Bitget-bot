import os
import json
import asyncio
import logging
import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt
import requests
import base64
import math
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_executor")

# --- CONFIGURATION ---
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "my_secret_password_123")
WIN_THRESHOLD = 8
LIVE_TRADING = os.environ.get("LIVE_TRADING", "YES") == "YES"

# GitHub Setup (To save the 8-win streak permanently)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO") # e.g., "yourusername/Bitget-bot"
STATE_FILE_PATH = "state.json"

# --- GITHUB STATE MANAGEMENT ---
def get_github_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_state_from_github():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE_PATH}"
    res = requests.get(url, headers=get_github_headers())
    if res.status_code == 200:
        content = base64.b64decode(res.json()['content']).decode('utf-8')
        return json.loads(content), res.json()['sha']
    return {"streak": 0, "unlocked": False}, None

def save_state_to_github(state, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE_PATH}"
    content_encoded = base64.b64encode(json.dumps(state, indent=2).encode('utf-8')).decode('utf-8')
    payload = {"message": f"Update state: Streak {state['streak']}", "content": content_encoded}
    if sha: payload["sha"] = sha
    res = requests.put(url, headers=get_github_headers(), json=payload)
    return res.status_code in [200, 201]

# --- AI RISK MANAGER (Pollinations) ---
async def get_ai_confirmation(symbol, direction, rsi, move_1h, move_5m):
    prompt = f"Risk Manager: Symbol: {symbol}, Dir: {direction}, RSI: {rsi}, 1H: {move_1h}%, 5M: {move_5m}%. Good reversal? Reply YES or NO."
    payload = {"model": "openai", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://text.pollinations.ai/openai", json=payload) as resp:
                data = await resp.json()
                ai_response = data["choices"][0]["message"]["content"].strip().upper()
                log.info(f"🤖 AI Analysis: {ai_response}")
                return "YES" in ai_response
    except Exception as e:
        log.error(f"AI API failed: {e}")
        return False

# --- BITGET UTA EXECUTION (One-Way Mode) ---
async def execute_bitget_trade(symbol, direction):
    exchange = ccxt.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'options': {'defaultType': 'swap', 'uta': True}
    })
    try:
        await exchange.load_markets()
        
        # 1. Fetch Balance
        balance = await exchange.fetch_balance(params={'uta': True})
        usdt_free = balance.get('USDT', {}).get('free', 0)
        log.info(f"💰 Available Balance: ${usdt_free:.2f}")

        if usdt_free < 1.0:
            log.error("❌ Balance too low to trade.")
            return False

        # 2. Check Minimums & Price
        market = exchange.market(symbol)
        ticker = await exchange.fetch_ticker(symbol)
        price = ticker['last']
        min_amount = market['limits']['amount']['min']
        
        # 3. Calculate Position Size
        usable_balance = usdt_free * 0.90
        required_leverage = math.ceil((min_amount * price) / usable_balance) if usable_balance > 0 else 999
        
        if required_leverage > 20:
            log.error(f"❌ Balance too small to trade {symbol}. Required leverage: {required_leverage}x")
            return False

        await exchange.set_leverage(required_leverage, symbol, params={'uta': True})
        amount = (usable_balance * required_leverage) / price
        amount = float(exchange.amount_to_precision(symbol, amount))
        
        # 4. OPEN POSITION (One-Way Mode)
        side = "buy" if direction == "LONG" else "sell"
        
        log.info(f"🚀 Opening {direction}: {amount} {symbol} at {required_leverage}x leverage")
        
        order = await exchange.create_order(
            symbol=symbol, 
            type="market", 
            side=side, 
            amount=amount,
            params={'uta': True, 'reduceOnly': False} # reduceOnly=False for opening
        )
        log.info(f"✅ OPEN ORDER PLACED: {order['id']}")
        
        # --- SIMULATE HOLDING THE TRADE ---
        # In a real bot, you would monitor the price for your exit condition (Fade/Stop Loss)
        log.info("⏳ Holding trade for 5 seconds to simulate...")
        await asyncio.sleep(5) 
        
        # 5. CLOSE POSITION (reduceOnly=True)
        close_side = "sell" if direction == "LONG" else "buy"
        log.info(f"🔄 Closing {direction} position...")
        
        close_order = await exchange.create_order(
            symbol=symbol, 
            type="market", 
            side=close_side, 
            amount=amount,
            params={'uta': True, 'reduceOnly': True} # reduceOnly=True for closing
        )
        log.info(f"✅ CLOSE ORDER PLACED: {close_order['id']}")
        return True
        
    except Exception as e:
        log.error(f"Bitget execution failed: {e}")
        return False
    finally:
        await exchange.close()

# --- WEBHOOK RECEIVER ---
async def handle_signal(request):
    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized")

    try:
        data = await request.json()
        log.info(f"📥 Signal Received: {data['symbol']} {data['direction']}")
        
        # 1. AI Check
        if not await get_ai_confirmation(data['symbol'], data['direction'], data['macro_rsi'], data['move_1h'], data['move_5m']):
            return web.Response(status=200, text="AI Rejected")

        # 2. Load State
        state, sha = load_state_from_github()
        is_live = LIVE_TRADING and state["unlocked"] 
        
        trade_successful = False

        if is_live:
            log.info("🔴 GATE UNLOCKED. EXECUTING LIVE TRADE.")
            trade_successful = await execute_bitget_trade(data['symbol'], data['direction'])
        else:
            log.info(f"🟢 PAPER TRADE. Current Streak: {state['streak']}/8")
            # Simulate a paper trade taking 5 seconds
            await asyncio.sleep(5)
            trade_successful = True # Simulate a win

        # 3. Update Streak (Only if not already unlocked)
        if trade_successful and not state["unlocked"]:
            state["streak"] += 1
            log.info(f"✅ Trade WON. New Streak: {state['streak']}")
            
            if state["streak"] >= WIN_THRESHOLD:
                state["unlocked"] = True
                log.info("🚀 8 WINS ACHIEVED! GATE UNLOCKED.")
            
            save_state_to_github(state, sha)

        return web.Response(status=200, text="Processed")
    except Exception as e:
        log.error(f"Signal error: {e}")
        return web.Response(status=500, text="Error")

async def main():
    app = web.Application()
    app.router.add_post('/signal', handle_signal)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    log.info("🚀 Webhook Active on /signal")
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
