import os
import json
import asyncio
import logging
import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt
import requests
import base64

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

# --- AI RISK MANAGER (Pollinations - No Key Needed) ---
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

# --- BITGET UTA EXECUTION ---
async def execute_bitget_trade(symbol, direction, amount_usdt=10):
    exchange = ccxt.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'options': {'defaultType': 'swap', 'uta': True}
    })
    try:
        ticker = await exchange.fetch_ticker(symbol)
        amount = amount_usdt / ticker['last']
        side = "buy" if direction == "LONG" else "sell"
        pos_side = "long" if direction == "LONG" else "short"
        
        order = await exchange.create_order(
            symbol=symbol, type="market", side=side, amount=amount,
            params={'uta': True, 'posSide': pos_side, 'reduceOnly': False}
        )
        log.info(f"✅ LIVE ORDER PLACED ON BITGET: {order['id']}")
    except Exception as e:
        log.error(f"Bitget execution failed: {e}")
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

        # 2. Load State (Check 8-win gate)
        state, sha = load_state_from_github()
        
        # LIVE TRADING ONLY HAPPENS IF UNLOCKED
        is_live = LIVE_TRADING and state["unlocked"] 
        
        if is_live:
            log.info("🔴 GATE UNLOCKED. EXECUTING LIVE TRADE.")
            await execute_bitget_trade(data['symbol'], data['direction'])
        else:
            log.info(f"🟢 PAPER TRADE. Current Streak: {state['streak']}/8")
            
            # SIMULATED PAPER TRADE OUTCOME 
            # (Replace 'True' with actual PnL logic later)
            trade_won = True 
            
            if trade_won:
                state["streak"] += 1
                log.info(f"✅ Paper Trade WON. New Streak: {state['streak']}")
            else:
                state["streak"] = 0
                log.info(f"❌ Paper Trade LOST. Streak reset to 0.")

            if state["streak"] >= WIN_THRESHOLD:
                state["unlocked"] = True
                log.info("🚀 8 WINS ACHIEVED! GATE UNLOCKED FOR NEXT TRADE.")
            
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
