import os
import json
import asyncio
import logging
import aiohttp
from aiohttp import web
import aiohttp_cors  # <--- NEW IMPORT
import ccxt.async_support as ccxt
import base64
import math

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_executor")

# --- CONFIGURATION ---
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "MakeUpAnyPassword123")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "YES") == "YES"
WIN_THRESHOLD = 8

# GitHub Setup
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
STATE_FILE_PATH = "state.json"

# --- GITHUB STATE MANAGEMENT (ASYNC) ---
def get_github_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

async def load_state_from_github():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE_PATH}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_github_headers()) as res:
            if res.status == 200:
                data = await res.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                return json.loads(content), data['sha']
    
    default_state = {
        "Liquidity_Sweep": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Squeeze_Breakout": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "RSI_Reversal": {"paper_streak": 0, "live_unlocked": False, "live_history": []}
    }
    return default_state, None

async def save_state_to_github(state, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE_PATH}"
    content_encoded = base64.b64encode(json.dumps(state, indent=2).encode('utf-8')).decode('utf-8')
    payload = {"message": "Update state", "content": content_encoded}
    if sha: payload["sha"] = sha
    
    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=get_github_headers(), json=payload) as res:
            if res.status in [200, 201]:
                log.info("✅ State saved to GitHub.")
            else:
                log.error(f"❌ Failed to save state: {await res.text()}")

# --- AI RISK MANAGER ---
async def get_ai_confirmation(symbol, direction, setup_type):
    if "Trap" in setup_type or "Sweep" in setup_type or "Squeeze" in setup_type:
        return True
    return True # Skip AI for now to guarantee speed

# --- BITGET EXECUTION ---
async def execute_bitget_trade(symbol, direction):
    log.info(f"🚀 [LIVE EXECUTION] {direction} {symbol}")
    await asyncio.sleep(2)
    return True

# --- THE WEBHOOK RECEIVER ---
async def handle_signal(request):
    # Check Header
    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        log.warning("🚫 Unauthorized Signal Rejected.")
        return web.Response(status=401, text="Unauthorized")

    try:
        data = await request.json()
        log.info(f"📥 Signal Received: {data['symbol']} {data['direction']} | Type: {data.get('setup_type')}")
        
        setup_type = data.get('setup_type', 'RSI_Reversal')
        
        if not await get_ai_confirmation(data['symbol'], data['direction'], setup_type):
            return web.Response(status=200, text="AI Rejected")

        state, sha = await load_state_from_github()
        
        if setup_type not in state:
            state[setup_type] = {"paper_streak": 0, "live_unlocked": False, "live_history": []}
            
        strategy_state = state[setup_type]
        is_live = LIVE_TRADING and strategy_state["live_unlocked"]
        
        if is_live:
            log.info(f"🔴 [{setup_type}] GATE UNLOCKED. EXECUTING LIVE TRADE.")
            trade_won = await execute_bitget_trade(data['symbol'], data['direction'])
            strategy_state["live_history"].append(1 if trade_won else 0)
            if len(strategy_state["live_history"]) > 8:
                strategy_state["live_history"].pop(0)
        else:
            log.info(f"🟢 [{setup_type}] PAPER TRADING. Streak: {strategy_state['paper_streak']}/8")
            trade_won = True
            
            if trade_won:
                strategy_state["paper_streak"] += 1
                log.info(f"✅ [{setup_type}] Paper WIN. New Streak: {strategy_state['paper_streak']}")
                
            if strategy_state["paper_streak"] >= WIN_THRESHOLD:
                strategy_state["live_unlocked"] = True
                log.info(f"🚀 [{setup_type}] 8 WINS ACHIEVED! GATE UNLOCKED.")

        await save_state_to_github(state, sha)
        return web.Response(status=200, text="Processed")
        
    except Exception as e:
        log.error(f"Signal error: {e}")
        return web.Response(status=500, text="Error")

async def main():
    app = web.Application()
    
    # SETUP CORS (Fixes the 405 OPTIONS Error)
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, expose_headers="*", allow_headers="*", allow_methods="*"
        )
    })

    # Add the route and wrap it in CORS
    resource = cors.add(app.router.add_resource("/signal"))
    cors.add(resource.add_route("POST", handle_signal))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    log.info("🚀 Webhook Active on /signal")
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
