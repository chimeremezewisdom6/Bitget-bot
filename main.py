import os
import sys
import asyncio
import logging
import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_executor")

# --- ENVIRONMENT CONFIGURATION ---
PORT = int(os.environ.get("PORT", 10000))
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "").rstrip("/")
RENDER_WEBHOOK_SECRET = os.environ.get("RENDER_WEBHOOK_SECRET", "")
EX_KEY = os.environ.get("BITGET_API_KEY", "")
EX_SECRET = os.environ.get("BITGET_API_SECRET", "")
EX_PASS = os.environ.get("BITGET_PASSPHRASE", "")

# Execution parameters
MAX_LEVERAGE = 5          # Max 5x leverage depending on capital
TAKE_PROFIT_PCT = 5.0     # +5.0% Take Profit
STOP_LOSS_PCT = 1.5       # -1.5% Hard Stop Loss
MIN_BUFFER_PNL = 1.5      # +1.5% Minimum PnL before momentum exit activates
TRAILING_OFFSET = 0.5     # 0.5% momentum reversal drop from peak locks in profit

active_trade = None

async def notify_hf_ready(symbol=None, direction=None, won=False, pnl_pct=0.0):
    """Notifies Hugging Face Space with trade outcome and frees slot."""
    if not HF_SPACE_URL:
        log.warning("⚠️ HF_SPACE_URL is not configured. Skipping callback notification.")
        return
    ready_endpoint = f"{HF_SPACE_URL}/ready"
    log.info(f"🔔 Notifying Hugging Face Space at {ready_endpoint} with result...")
    payload = {
        "symbol": symbol,
        "direction": direction,
        "won": won,
        "pnl_pct": pnl_pct
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ready_endpoint, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    log.info("✅ Hugging Face notified successfully.")
                else:
                    log.error(f"❌ HF callback failed | Status: {resp.status}")
    except Exception as e:
        log.error(f"❌ Failed to notify Hugging Face: {e}")

async def configure_bitget_uta(exchange, symbol):
    """
    Configures Bitget Unified Trading Account (UTA):
    1. Sets One-Way Position Mode (hedged=False).
    2. Sets Leverage dynamically up to maximum 5x.
    """
    try:
        # Set position mode to One-Way (not Hedge)
        try:
            await exchange.set_position_mode(hedged=False, symbol=symbol)
            log.info(f"✅ One-Way Position Mode set for {symbol}")
        except Exception as e:
            log.info(f"Position mode notice for {symbol}: {e}")

        # Set Leverage to Max 5x
        try:
            await exchange.set_leverage(MAX_LEVERAGE, symbol=symbol)
            log.info(f"⚡ Leverage set to {MAX_LEVERAGE}x for {symbol}")
        except Exception as e:
            log.info(f"Leverage setup notice for {symbol}: {e}")
    except Exception as e:
        log.warning(f"UTA configuration notice: {e}")

async def monitor_and_execute_trade(symbol, direction):
    """
    Executes Long or Short position on Bitget UTA in One-Way Mode,
    using reduce-only orders for all position exits.
    """
    exchange = ccxt.bitget({
        "apiKey": EX_KEY,
        "secret": EX_SECRET,
        "password": EX_PASS,
        "options": {"defaultType": "swap", "uta": True}
    })
    try:
        await exchange.load_markets()
        await configure_bitget_uta(exchange, symbol)

        ticker = await exchange.fetch_ticker(symbol)
        entry_price = ticker.get("last", 0.0)
        if entry_price == 0.0:
            log.error(f"Could not fetch valid entry price for {symbol}")
            return False, 0.0

        log.info(f"📍 Entry Price for {symbol} ({direction}): {entry_price}")

        # Fetch Available Capital in Bitget UTA to determine position size (Max 5x leverage)
        try:
            balance = await exchange.fetch_balance({"type": "swap"})
            free_usdt = float(balance.get("USDT", {}).get("free", 10.0))
        except Exception:
            free_usdt = 10.0

        position_value_usdt = free_usdt * MAX_LEVERAGE * 0.95  # 95% of 5x leveraged capital
        qty = position_value_usdt / entry_price

        # Place Entry Order (One-Way Mode)
        entry_side = "buy" if direction == "LONG" else "sell"
        log.info(f"🚀 Placing {direction} Entry Market Order for {qty:.4f} {symbol}...")
        try:
            await exchange.create_order(symbol, "market", entry_side, qty)
            log.info("✅ Entry order executed.")
        except Exception as e:
            log.error(f"Entry order execution error: {e}")
            # Continue monitoring price movement even if test paper account

        peak_pnl = 0.0
        max_time_seconds = 14400  # 4-hour macro holding window
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < max_time_seconds:
            await asyncio.sleep(2)
            try:
                curr_ticker = await exchange.fetch_ticker(symbol)
                curr_price = curr_ticker.get("last", entry_price)

                # Calculate Current PnL %
                if direction == "LONG":
                    curr_pnl = ((curr_price - entry_price) / entry_price) * 100.0
                else:
                    curr_pnl = ((entry_price - curr_price) / entry_price) * 100.0

                if curr_pnl > peak_pnl:
                    peak_pnl = curr_pnl

                # Hard Take Profit (+5.0%)
                if curr_pnl >= TAKE_PROFIT_PCT:
                    log.info(f"🎯 Hard Take Profit (+{curr_pnl:.2f}%) Reached!")
                    await close_position_reduce_only(exchange, symbol, direction, qty)
                    return True, curr_pnl

                # Hard Stop Loss (-1.5%)
                if curr_pnl <= -STOP_LOSS_PCT:
                    log.info(f"🛑 Hard Stop Loss ({curr_pnl:.2f}%) Reached.")
                    await close_position_reduce_only(exchange, symbol, direction, qty)
                    return False, curr_pnl

                # Momentum Exhaustion Exit: Minimum +1.5% PnL Buffer + 0.5% Trailing Reversal
                if peak_pnl >= MIN_BUFFER_PNL and (peak_pnl - curr_pnl) >= TRAILING_OFFSET:
                    log.info(f"📈 Momentum Exhaustion Exit | Peak: +{peak_pnl:.2f}% | Exit: +{curr_pnl:.2f}%")
                    await close_position_reduce_only(exchange, symbol, direction, qty)
                    return True, curr_pnl

            except Exception as e:
                log.error(f"Price monitoring error: {e}")
                continue

        # 4-Hour Timeout Exit
        curr_ticker = await exchange.fetch_ticker(symbol)
        exit_price = curr_ticker.get("last", entry_price)
        pnl_pct = ((exit_price - entry_price) / entry_price * 100) if direction == "LONG" else ((entry_price - exit_price) / entry_price * 100)
        won = pnl_pct > 0
        log.info(f"⏰ 4-Hour Timeout Reached | PnL: {pnl_pct:+.2f}%")
        await close_position_reduce_only(exchange, symbol, direction, qty)
        return won, pnl_pct

    except Exception as e:
        log.error(f"Execution error: {e}")
        return False, 0.0
    finally:
        await exchange.close()

async def close_position_reduce_only(exchange, symbol, direction, qty):
    """
    Closes the open position using REDUCE-ONLY market orders to guarantee
    the exit never opens an unintended opposite position on Bitget UTA.
    """
    exit_side = "sell" if direction == "LONG" else "buy"
    log.info(f"🔒 Executing REDUCE-ONLY {exit_side.upper()} order to close {direction} position on {symbol}...")
    try:
        await exchange.create_order(
            symbol=symbol,
            type="market",
            side=exit_side,
            amount=qty,
            params={"reduceOnly": True}
        )
        log.info("✅ REDUCE-ONLY exit order completed.")
    except Exception as e:
        log.error(f"Reduce-only exit error: {e}")

async def process_trade(symbol, direction, setup_type):
    global active_trade
    try:
        log.info(f"⚙️ Executing {direction} trade on Bitget UTA for {symbol}...")
        trade_won, pnl_pct = await monitor_and_execute_trade(symbol, direction)
        log.info(f"📈 Trade Finished | Result: {'WIN' if trade_won else 'LOSS'} ({pnl_pct:+.2f}%)")
    finally:
        active_trade = None
        await notify_hf_ready(symbol, direction, trade_won, pnl_pct)

routes = web.RouteTableDef()

@routes.get("/")
@routes.get("/health")
async def health_check(request):
    return web.json_response({"status": "online", "active_trade": active_trade})

@routes.post("/signal")
async def handle_signal(request):
    global active_trade

    incoming_secret = request.headers.get("X-Webhook-Secret", "")
    if RENDER_WEBHOOK_SECRET and incoming_secret != RENDER_WEBHOOK_SECRET:
        log.warning("❌ Signal rejected: Invalid X-Webhook-Secret header.")
        return web.json_response({"error": "Unauthorized"}, status=401)

    if active_trade is not None:
        log.warning(f"⚠️ Signal rejected: Trade already in progress on {active_trade}.")
        return web.json_response({"error": "Busy", "active_trade": active_trade}, status=429)

    try:
        data = await request.json()
        symbol = data.get("symbol")
        direction = data.get("direction", "LONG")
        setup_type = data.get("setup_type", "24h_Exhaustion_Volume_Death_Reversal")

        if not symbol:
            return web.json_response({"error": "Missing symbol"}, status=400)

        active_trade = symbol
        log.info(f"📥 Signal Accepted from HF: {symbol} ({direction})")

        asyncio.create_task(process_trade(symbol, direction, setup_type))
        return web.json_response({"status": "accepted", "symbol": symbol, "direction": direction})
    except Exception as e:
        log.error(f"Error handling signal payload: {e}")
        return web.json_response({"error": str(e)}, status=400)

def main():
    app = web.Application()
    app.add_routes(routes)
    log.info(f"🚀 Render Web Service starting on port {PORT}...")
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
