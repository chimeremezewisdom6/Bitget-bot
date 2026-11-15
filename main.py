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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_executor")

# --- CONFIGURATION ---
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "my_secret_password_123")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "YES") == "YES"
WIN_THRESHOLD = 8

# GitHub Setup
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
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
    
    # Default state if file doesn't exist
    default_state = {
        "Reversal": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Momentum": {"paper_streak": 0, "live_unlocked": False, "live_history": []}
    }
    return default_state, None

def save_state_to_github(state, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE_PATH}"
    content_encoded = base64.b64encode(json.dumps(state, indent=2).encode('utf-8')).decode('utf-8')
    payload = {"message": f"Update state", "content": content_encoded}
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

# --- BITGET UTA EXECUTION ---
async def execute_bitget_trade(symbol, direction):
    exchange = ccxt.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'options': {'defaultType': 'swap', 'uta': True}
    })
    try:
        await exchange.load_markets()
        balance = await exchange.fetch_balance(params={'uta': True})
        usdt_free = balance.get('USDT', {}).get('free', 0)
        
        if usdt_free < 1.0:
            log.error("❌ Balance too low to trade.")
            return False

        market = exchange.market(symbol)
        ticker = await exchange.fetch_ticker(symbol)
        price = ticker['last']
        min_amount = market['limits']['amount']['min']
        
        usable_balance = usdt_free * 0.90
        required_leverage = math.ceil((min_amount * price) / usable_balance) if usable_balance > 0 else 999
        
        if required_leverage > 20:
            log.error(f"❌ Balance too small. Required leverage: {required_leverage}x")
            return False

        await exchange.set_leverage(required_leverage, symbol, params={'uta': True})
        amount = float(exchange.amount_to_precision(symbol, (usable_balance * required_leverage) / price))
        
        side = "buy" if direction == "LONG" else "sell"
        log.info(f"🚀 LIVE {direction}: {amount} {symbol} at {required_leverage}x")
        
        order = await exchange.create_order(
            symbol=symbol, type="market", side=side, amount=amount,
            params={'uta': True, 'reduceOnly': False}
        )
        
        # --- SIMULATE TRADE HOLD & RESULT ---
        # In production, you monitor the price here. For now, we assume a win to test the logic.
        await asyncio.sleep(5) 
        trade_won = True 
        
        close_side = "sell" if direction == "LONG" else "buy"
        await exchange.create_order(
            symbol=symbol, type="market", side=close_side, amount=amount,
            params={'uta': True, 'reduceOnly': True}
        )
        return trade_won
        
    except Exception as e:
        log.error(f"Bitget execution failed: {e}")
        return False
    finally:
        await exchange.close()

# --- WEBHOOK RECEIVER & STATE MACHINE ---
async def handle_signal(request):
    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized")

    try:
        data = await request.json()
        symbol = data['symbol']
        direction = data['direction']
        setup_type = data.get('setup_type', 'Reversal') # Defaults to Reversal if missing
        
        log.info(f"📥 Signal Received: {symbol} {direction} | Type: {setup_type}")
        
        # 1. AI Check
        if not await get_ai_confirmation(symbol, direction, data['macro_rsi'], data['move_1h'], data['move_5m']):
            return web.Response(status=200, text="AI Rejected")

        # 2. Load State
        state, sha = load_state_from_github()
        
        # Ensure setup type exists in state
        if setup_type not in state:
            state[setup_type] = {"paper_streak": 0, "live_unlocked": False, "live_history": []}
            
        strategy_state = state[setup_type]
        
        # 3. Execute based on Gate
        is_live = LIVE_TRADING and strategy_state["live_unlocked"]
        trade_won = False
        
        if is_live:
            log.info(f"🔴 [{setup_type}] GATE UNLOCKED. EXECUTING LIVE TRADE.")
            trade_won = await execute_bitget_trade(symbol, direction)
            
            # Track Live History
            strategy_state["live_history"].append(1 if trade_won else 0)
            if len(strategy_state["live_history"]) > 8:
                strategy_state["live_history"].pop(0)
                
            # --- DEMOTION RULES ---
            if len(strategy_state["live_history"]) >= 3 and strategy_state["live_history"][-3:] == [0, 0, 0]:
                log.info(f"🛑 [{setup_type}] DEMOTED: 3 consecutive losses. Back to paper trading.")
                strategy_state["live_unlocked"] = False
                strategy_state["paper_streak"] = 0
                strategy_state["live_history"] = []
                
            elif len(strategy_state["live_history"]) >= 8 and strategy_state["live_history"].count(0) >= 6:
                log.info(f"🛑 [{setup_type}] DEMOTED: 6 losses in last 8 trades. Back to paper trading.")
                strategy_state["live_unlocked"] = False
                strategy_state["paper_streak"] = 0
                strategy_state["live_history"] = []
                
        else:
            log.info(f"🟢 [{setup_type}] PAPER TRADING. Streak: {strategy_state['paper_streak']}/8")
            
            # SIMULATE PAPER TRADE
            await asyncio.sleep(5)
            trade_won = True # Set to False to test loss logic
            
            if trade_won:
                strategy_state["paper_streak"] += 1
                log.info(f"✅ [{setup_type}] Paper WIN. New Streak: {strategy_state['paper_streak']}")
            else:
                strategy_state["paper_streak"] = 0
                log.info(f"❌ [{setup_type}] Paper LOSS. Streak reset.")
                
            if strategy_state["paper_streak"] >= WIN_THRESHOLD:
                strategy_state["live_unlocked"] = True
                log.info(f"🚀 [{setup_type}] 8 WINS ACHIEVED! GATE UNLOCKED.")

        # 4. Save State
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
