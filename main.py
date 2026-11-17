import asyncio
import base64
import json
import logging
import os

import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("render_executor")

# --- CONFIGURATION ---
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change_me_secret")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "NO").upper() == "YES"
WIN_THRESHOLD = 8
LOSS_DEMOTION_STREAK = 3
MAX_LEVERAGE = 5

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
STATE_FILE_PATH = "state.json"

HF_READY_URL = os.environ.get("HF_READY_URL", "")
POLLINATIONS_API_KEY = os.environ.get("POLLINATIONS_API_KEY", "")
POLLINATIONS_URL = "https://text.pollinations.ai/openai"

PORT = int(os.environ.get("PORT", 10000))

ALL_SETUPS = [
    "RSI_Standard", "RSI_Extreme", "Sweep_20", "Sweep_50",
    "Squeeze_Tight", "Squeeze_Extreme", "Volume_RSI",
    "Wick_Rejection", "Momentum", "EMA_Cross"
]

# --- CONCURRENCY LOCKS ---
trade_lock = asyncio.Lock()
github_lock = asyncio.Lock()
is_trading = False


def default_state_schema():
    return {
        name: {"paper_streak": 0, "live_unlocked": False, "live_history": []}
        for name in ALL_SETUPS
    }


# --- GITHUB PERSISTENT STATE (Survives Render Restarts) ---
def get_github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }


async def load_state_from_github():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return default_state_schema(), None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE_PATH}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=get_github_headers(), timeout=15) as res:
                if res.status == 200:
                    payload = await res.json()
                    raw = base64.b64decode(payload["content"]).decode("utf-8")
                    loaded = json.loads(raw)
                    for name in ALL_SETUPS:
                        if name not in loaded:
                            loaded[name] = {
                                "paper_streak": 0,
                                "live_unlocked": False,
                                "live_history": []
                            }
                    return loaded, payload["sha"]
    except Exception as e:
        log.error(f"GitHub load_state error: {e}")
    return default_state_schema(), None


async def save_state_to_github(state, sha):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log.warning("Missing GITHUB_TOKEN or GITHUB_REPO; skipping state persistence.")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE_PATH}"
    encoded = base64.b64encode(json.dumps(state, indent=2).encode("utf-8")).decode("utf-8")
    body = {"message": "Update trading streak state", "content": encoded}
    if sha:
        body["sha"] = sha

    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=get_github_headers(), json=body, timeout=15) as res:
                if res.status in (200, 201):
                    log.info("Saved state.json to GitHub.")
                    return True
                log.error(f"GitHub save_state HTTP {res.status}: {await res.text()}")
    except Exception as e:
        log.error(f"GitHub save_state error: {e}")
    return False


# --- AI RISK CONFIRMATION ---
async def get_ai_confirmation(symbol, direction, setup_type, rsi, move_1h, move_5m):
    if any(k in setup_type for k in ("Sweep", "Squeeze", "Wick")):
        log.info(f"Structural setup ({setup_type}) auto-approved.")
        return True

    prompt = (
        f"Risk Manager check: Symbol={symbol}, Direction={direction}, Setup={setup_type}, "
        f"RSI={rsi}, 1H={move_1h}%, 5M={move_5m}%. Safe to take? Reply YES or NO."
    )
    payload = {"model": "openai", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
    headers = {"Content-Type": "application/json"}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(POLLINATIONS_URL, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"].strip().upper()
                    log.info(f"Pollinations AI decision: {text}")
                    return "YES" in text
    except Exception as e:
        log.warning(f"AI check failed ({e}); defaulting to YES.")
    return True


# --- FADE DETECTION HELPER ---
async def check_momentum_fade(exchange, symbol, direction, profit_pct):
    try:
        candles = await exchange.fetch_ohlcv(symbol, "1m", limit=5)
        if not candles or len(candles) < 4:
            return False

        closed = candles[-2]
        prev_2 = candles[-4:-2]
        o, h, l, c, v = closed[1], closed[2], closed[3], closed[4], closed[5]
        candle_range = h - l
        body_ratio = abs(c - o) / candle_range if candle_range > 0 else 0.0
        avg_prev_vol = sum(x[5] for x in prev_2) / 2.0

        # Hold when solid momentum body persists (> 0.70)
        if body_ratio > 0.70:
            is_aligned = (direction == "LONG" and c > o) or (direction == "SHORT" and c < o)
            if is_aligned:
                return False

        # Exit on fade when profitable and candle collapses into wicks with volume drop
        if profit_pct > 0.25 and body_ratio < 0.20 and avg_prev_vol > 0 and v < (avg_prev_vol * 0.50):
            log.info(
                f"Fade detected on {symbol}: body_ratio={body_ratio:.2f}, "
                f"vol={v:.1f} vs prev_avg={avg_prev_vol:.1f}"
            )
            return True
    except Exception:
        pass
    return False


# --- BITGET UTA SINGLE-TRADE EXECUTION (5x Leverage, One-Way, reduceOnly) ---
async def execute_trade(symbol, direction, use_live):
    exchange = ccxt.bitget({
        "apiKey": os.environ.get("BITGET_API_KEY", ""),
        "secret": os.environ.get("BITGET_SECRET", ""),
        "password": os.environ.get("BITGET_PASSPHRASE", ""),
        "enableRateLimit": True,
        "options": {"defaultType": "swap", "uta": True}
    })

    live_order_opened = False
    order_amount = 0.0
    entry_side = "buy" if direction == "LONG" else "sell"
    exit_side = "sell" if direction == "LONG" else "buy"

    try:
        await exchange.load_markets()
        ticker = await exchange.fetch_ticker(symbol)
        entry_price = float(ticker["last"])
        market = exchange.market(symbol)
        min_amount = float(market.get("limits", {}).get("amount", {}).get("min") or 0.0)

        if use_live:
            balance = await exchange.fetch_balance(params={"uta": True})
            usdt_free = float(balance.get("USDT", {}).get("free") or 0.0)
            if usdt_free < 1.0:
                log.error(f"Live balance too low (${usdt_free:.2f}). Falling back to paper simulation.")
                use_live = False
            else:
                await exchange.set_leverage(MAX_LEVERAGE, symbol, params={"uta": True})
                usable_margin = usdt_free * 0.90
                notional = usable_margin * MAX_LEVERAGE
                raw_amount = notional / entry_price
                if raw_amount < min_amount:
                    log.error(f"Calculated size {raw_amount:.6f} below Bitget min {min_amount}. Aborting live order.")
                    return False

                order_amount = float(exchange.amount_to_precision(symbol, raw_amount))
                # One-Way Mode UTA entry (reduceOnly=False, no hedge posSide)
                entry_order = await exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=entry_side,
                    amount=order_amount,
                    params={"uta": True, "reduceOnly": False}
                )
                live_order_opened = True
                log.info(
                    f"[LIVE UTA 5x] Opened {direction} {symbol} | Amount={order_amount} | "
                    f"Entry=${entry_price} | Order={entry_order.get('id')}"
                )
        else:
            log.info(f"[PAPER] Opened {direction} {symbol} @ ${entry_price} | Max Leverage={MAX_LEVERAGE}x")

        peak_price = entry_price
        trailing_callback = 0.005
        final_profit_pct = 0.0

        for minute in range(120):
            await asyncio.sleep(60)
            try:
                ticker = await exchange.fetch_ticker(symbol)
                current_price = float(ticker["last"])
            except Exception:
                continue

            if direction == "LONG":
                peak_price = max(peak_price, current_price)
                pullback = (peak_price - current_price) / peak_price
                final_profit_pct = ((current_price - entry_price) / entry_price) * 100.0
            else:
                peak_price = min(peak_price, current_price)
                pullback = (current_price - peak_price) / peak_price
                final_profit_pct = ((entry_price - current_price) / entry_price) * 100.0

            log.info(f"[{minute + 1}m] {symbol} {direction} | Price=${current_price} | PnL={final_profit_pct:+.2f}%")

            trailing_hit = final_profit_pct > 1.0 and pullback >= trailing_callback
            hard_stop_hit = final_profit_pct <= -2.0
            fade_hit = await check_momentum_fade(exchange, symbol, direction, final_profit_pct)

            if trailing_hit or hard_stop_hit or fade_hit:
                reason = "Hard Stop" if hard_stop_hit else ("Fade Exit" if fade_hit else "Trailing Stop")
                log.info(f"{reason} triggered on {symbol} | Final PnL: {final_profit_pct:+.2f}%")
                break

        if live_order_opened and order_amount > 0:
            # Close One-Way Mode position strictly with reduceOnly=True
            close_order = await exchange.create_order(
                symbol=symbol,
                type="market",
                side=exit_side,
                amount=order_amount,
                params={"uta": True, "reduceOnly": True}
            )
            log.info(f"[LIVE CLOSED reduceOnly] {symbol} | Order={close_order.get('id')}")

        return final_profit_pct > 0.0

    except Exception as e:
        log.error(f"Trade execution error for {symbol}: {e}")
        if live_order_opened and order_amount > 0:
            try:
                await exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=exit_side,
                    amount=order_amount,
                    params={"uta": True, "reduceOnly": True}
                )
                log.info(f"Emergency reduceOnly close succeeded for {symbol}.")
            except Exception as close_err:
                log.critical(f"Emergency close failed for {symbol}: {close_err}")
        return False
    finally:
        await exchange.close()


# --- TWO-WAY CALLBACK TO HUGGING FACE ---
async def notify_hf_ready():
    if not HF_READY_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HF_READY_URL, json={"status": "ready"}, timeout=10) as resp:
                log.info(f"Notified Hugging Face /ready -> HTTP {resp.status}")
    except Exception as e:
        log.warning(f"Failed to notify Hugging Face /ready: {e}")


# --- FULL TRADE LIFECYCLE TASK ---
async def process_trade_lifecycle(data):
    global is_trading
    symbol = data["symbol"]
    direction = data["direction"]
    setup_type = data.get("setup_type", "Momentum")

    try:
        async with github_lock:
            state, _ = await load_state_from_github()
        setup_state = state.get(setup_type, {"paper_streak": 0, "live_unlocked": False, "live_history": []})
        use_live = LIVE_TRADING and bool(setup_state.get("live_unlocked", False))

        won = await execute_trade(symbol, direction, use_live=use_live)

        async with github_lock:
            state, sha = await load_state_from_github()
            entry = state.setdefault(setup_type, {"paper_streak": 0, "live_unlocked": False, "live_history": []})

            if use_live:
                entry["live_history"].append(bool(won))
                entry["live_history"] = entry["live_history"][-20:]
                if len(entry["live_history"]) >= LOSS_DEMOTION_STREAK and not any(entry["live_history"][-LOSS_DEMOTION_STREAK:]):
                    entry["live_unlocked"] = False
                    entry["paper_streak"] = 0
                    log.warning(f"{setup_type} hit {LOSS_DEMOTION_STREAK} live losses. Demoted back to paper mode.")
            else:
                if won:
                    entry["paper_streak"] += 1
                    log.info(f"{setup_type} paper streak: {entry['paper_streak']}/{WIN_THRESHOLD}")
                    if entry["paper_streak"] >= WIN_THRESHOLD:
                        entry["live_unlocked"] = True
                        log.info(f"8-WIN GATE UNLOCKED for {setup_type}!")
                else:
                    entry["paper_streak"] = 0
                    log.info(f"{setup_type} paper loss. Streak reset to 0.")

            await save_state_to_github(state, sha)
    finally:
        async with trade_lock:
            is_trading = False
        await notify_hf_ready()


# --- WEB SERVER HANDLERS ---
async def handle_health(request):
    return web.Response(status=200, text="Bot is alive and running!")


async def handle_signal(request):
    global is_trading
    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        log.warning("Unauthorized webhook rejected.")
        return web.Response(status=401, text="Unauthorized")

    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    symbol = data.get("symbol")
    direction = data.get("direction")
    setup_type = data.get("setup_type", "Momentum")
    if not symbol or direction not in ("LONG", "SHORT"):
        return web.Response(status=400, text="Missing symbol or invalid direction")

    async with trade_lock:
        if is_trading:
            log.info(f"Trade already active. Returning 429 for {symbol}.")
            return web.Response(status=429, text="Executor busy")

        approved = await get_ai_confirmation(
            symbol,
            direction,
            setup_type,
            data.get("macro_rsi", 50),
            data.get("move_1h", 0),
            data.get("move_5m", 0)
        )
        if not approved:
            log.info(f"Pollinations AI rejected {symbol} ({setup_type}).")
            return web.Response(status=200, text="Rejected by AI")

        is_trading = True
        asyncio.create_task(process_trade_lifecycle(data))

    return web.Response(status=200, text="Accepted")


async def main():
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_post("/signal", handle_signal)
    app.router.add_post("/", handle_signal)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info(f"Render Single-Trade Executor listening on port {PORT} (LIVE_TRADING={LIVE_TRADING})")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
