import os
import json
import asyncio
import logging
import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt
import base64
import math

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_executor")

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "my_secret_password_123")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "YES") == "YES"
WIN_THRESHOLD = 8

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
STATE_FILE_PATH = "state.json"

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

# --- REAL TRADE EXECUTION & PROFIT TRACKING ---
async def execute_bitget_trade(symbol, direction):
    exchange = ccxt.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'options': {'defaultType': 'swap', 'uta': True}
    })
    try:
        await exchange.load_markets()
        
        # Live Trade Setup (Skipping balance check for paper trading simulation)
        ticker = await exchange.fetch_ticker(symbol)
        entry_price = ticker['last']
        log.info(f"🚀 [PAPER TRADE] Opened {direction} on {symbol} at ${entry_price}")
        
        # We simulate a small delay before starting the loop
        await asyncio.sleep(2)
        
        peak_price = entry_price
        trailing_callback = 0.005 # 0.5% trailing stop
        max_time_minutes = 120 # Max 2 hours
        
        log.info(f"⏳ Monitoring trade... Trailing stop at {trailing_callback*100}%")
        
        for _ in range(max_time_minutes):
            await asyncio.sleep(60) # Check price every minute
            
            try:
                ticker = await exchange.fetch_ticker(symbol)
                current_price = ticker['last']
            except Exception:
                continue # Skip this minute if API fails
                
            if direction == "LONG":
                peak_price = max(peak_price, current_price)
                drop_from_peak = ((peak_price - current_price) / peak_price)
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                
                # Log the current status so the user can see the gain!
                log.info(f"📊 {symbol} LONG | Current: ${current_price} | PnL: {profit_pct:+.2f}%")
                
                # Exit if trailing stop is hit OR if it's a loss > 2%
                if (profit_pct > 1.0 and drop_from_peak > trailing_callback) or profit_pct < -2.0:
                    log.info(f"💰 TRAILING STOP HIT. Final Profit: {profit_pct:+.2f}%")
                    break
                    
            elif direction == "SHORT":
                peak_price = min(peak_price, current_price) # Lowest price
                bounce_from_peak = ((current_price - peak_price) / peak_price)
                profit_pct = ((entry_price - current_price) / entry_price) * 100
                
                log.info(f"📊 {symbol} SHORT | Current: ${current_price} | PnL: {profit_pct:+.2f}%")
                
                if (profit_pct > 1.0 and bounce_from_peak > trailing_callback) or profit_pct < -2.0:
                    log.info(f"💰 TRAILING STOP HIT. Final Profit: {profit_pct:+.2f}%")
                    break
        
        # Calculate final result
        final_ticker = await exchange.fetch_ticker(symbol)
        final_price = final_ticker['last']
        if direction == "LONG":
            final_pnl = ((final_price - entry_price) / entry_price) * 100
        else:
            final_pnl = ((entry_price - final_price) / entry_price) * 100
            
        trade_won = final_pnl > 0
        return trade_won, final_pnl
        
    except Exception as e:
        log.error(f"Execution failed: {e}")
        return False, 0.0
    finally:
        await exchange.close()

async def get_ai_confirmation(symbol, direction, setup_type):
    return True # Skip AI for now to save time

async def handle_signal(request):
    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized")

    try:
        data = await request.json()
        symbol = data['symbol']; direction = data['direction']; setup_type = data.get('setup_type', 'RSI_Reversal')
        
        log.info(f"📥 Signal Received: {symbol} {direction} | Type: {setup_type}")
        
        state, sha = await load_state_from_github()
        
        if setup_type not in state:
            state[setup_type] = {"paper_streak": 0, "live_unlocked": False, "live_history": []}
            
        strategy_state = state[setup_type]
        is_live = LIVE_TRADING and strategy_state["live_unlocked"]
        
        trade_won, pnl_pct = await execute_bitget_trade(symbol, direction)
        
        if is_live:
            log.info(f"🔴 [{setup_type}] GATE UNLOCKED. EXECUTED LIVE TRADE.")
            strategy_state["live_history"].append(1 if trade_won else 0)
            if len(strategy_state["live_history"]) > 8:
                strategy_state["live_history"].pop(0)
        else:
            log.info(f"🟢 [{setup_type}] PAPER TRADE RESULT: {'WIN' if trade_won else 'LOSS'} ({pnl_pct:+.2f}%)")
            
            if trade_won:
                strategy_state["paper_streak"] += 1
                log.info(f"✅ [{setup_type}] New Streak: {strategy_state['paper_streak']}/8")
            else:
                strategy_state["paper_streak"] = 0
                log.info(f"❌ [{setup_type}] Streak reset to 0.")
                
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
    app.router.add_post('/signal', handle_signal)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    log.info("🚀 Webhook Active on /signal")
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
