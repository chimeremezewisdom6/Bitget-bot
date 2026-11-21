import time
import json
import asyncio
import aiohttp
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("buildup_backtester")

BIT_DOMAIN = "api." + "bitget" + ".com"
BITGET_TICKERS_URL = f"https://{BIT_DOMAIN}/api/v2/mix/market/tickers?productType=USDT-FUTURES"
BITGET_CANDLES_URL = f"https://{BIT_DOMAIN}/api/v2/mix/market/candles"

MIN_24H_VOLUME = 300000    # $300k+ Volume Filter
TARGET_PROFIT_PCT = 2.5    # +2.50% Take Profit
STOP_LOSS_PCT = 1.25       # -1.25% Stop Loss Guard
FORWARD_HOLD_MINUTES = 20  # Evaluate outcomes over next 20 minutes

async def fetch_tickers(session):
    try:
        async with session.get(BITGET_TICKERS_URL, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
    except Exception as e:
        log.error(f"Error fetching tickers: {e}")
    return []

async def fetch_historical_candles(session, symbol, limit=500):
    """Fetches up to 500 historical 1-minute OHLCV candles from Bitget."""
    params = {
        "symbol": symbol,
        "productType": "USDT-FUTURES",
        "granularity": "1m",
        "limit": str(limit)
    }
    for attempt in range(3):
        try:
            async with session.get(BITGET_CANDLES_URL, params=params, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("code") == "00000":
                        candles = data.get("data", [])
                        if candles:
                            # Reverse to chronological order (index 0 = oldest, index -1 = newest)
                            return list(reversed(candles))
                elif r.status in (429, 403):
                    await asyncio.sleep(0.2 * (attempt + 1))
        except Exception:
            await asyncio.sleep(0.1 * (attempt + 1))
    return []

def evaluate_forward_trade(candles_1m, entry_idx, direction, target_tp=2.5, max_sl=1.25, max_mins=20):
    """
    Evaluates whether an entry reaches +2.50% profit before -1.25% stop loss over max 20 minutes.
    """
    if entry_idx + max_mins >= len(candles_1m):
        return None

    entry_price = float(candles_1m[entry_idx][4])
    if entry_price <= 0:
        return None

    max_gain = 0.0
    max_dd = 0.0

    for m in range(1, max_mins + 1):
        c = candles_1m[entry_idx + m]
        high = float(c[2])
        low = float(c[3])

        if direction == "LONG":
            gain = ((high - entry_price) / entry_price) * 100.0
            drawdown = ((entry_price - low) / entry_price) * 100.0
        else:  # SHORT
            gain = ((entry_price - low) / entry_price) * 100.0
            drawdown = ((high - entry_price) / entry_price) * 100.0

        if gain > max_gain:
            max_gain = gain
        if drawdown > max_dd:
            max_dd = drawdown

        # Stop loss triggered
        if max_dd >= max_sl and max_gain < target_tp:
            return {"won": False, "max_gain": max_gain, "max_dd": max_dd, "exit_min": m}
        # Take profit hit
        if max_gain >= target_tp and max_dd < max_sl:
            return {"won": True, "max_gain": max_gain, "max_dd": max_dd, "exit_min": m}

    won = max_gain >= target_tp and max_dd < max_sl
    return {"won": won, "max_gain": max_gain, "max_dd": max_dd, "exit_min": max_mins}

def scan_symbol_buildup_patterns(candles_1m):
    """
    Scans a single coin's historical 1m candles for Small ~0.5% Build-Up to Big Move Expansion.
    """
    occurrences = []
    n_total = len(candles_1m)
    if n_total < 80:
        return occurrences

    for i in range(50, n_total - FORWARD_HOLD_MINUTES - 1):
        # Scan dynamic build-up window lengths N from 5 to 45 candles
        for n_window in range(5, 46):
            buildup_candles = candles_1m[i - n_window : i]
            if len(buildup_candles) < n_window:
                continue

            b_open = float(buildup_candles[0][1])
            b_high = max(float(c[2]) for c in buildup_candles)
            b_low = min(float(c[3]) for c in buildup_candles)
            b_close = float(buildup_candles[-1][4])

            if b_open <= 0 or b_low <= 0:
                continue

            # 1. SMALL BUILD-UP RANGE (~0.25% to 0.85%, target ~0.50%)
            buildup_range_pct = ((b_high - b_low) / b_open) * 100.0
            if buildup_range_pct < 0.20 or buildup_range_pct > 0.85:
                continue

            # 2. CANDLE COLOR CONSISTENCY (>= 65% same color)
            green_cnt = sum(1 for c in buildup_candles if float(c[4]) > float(c[1]))
            red_cnt = sum(1 for c in buildup_candles if float(c[4]) < float(c[1]))
            consistency = max(green_cnt, red_cnt) / float(n_window)

            if consistency < 0.65:
                continue

            # 3. VOLUME ACCELERATION
            b_vol_avg = sum(float(c[5]) for c in buildup_candles) / float(n_window)
            trig_vol = float(candles_1m[i][5])
            if b_vol_avg <= 0:
                continue

            vol_surge = trig_vol / b_vol_avg
            if vol_surge < 1.3:
                continue

            curr_close = float(candles_1m[i][4])
            is_bull_break = (curr_close > b_high) and (curr_close > b_open * 1.003)
            is_bear_break = (curr_close < b_low) and (curr_close < b_open * 0.997)

            if is_bull_break or is_bear_break:
                direction = "LONG" if is_bull_break else "SHORT"
                result = evaluate_forward_trade(candles_1m, i, direction, TARGET_PROFIT_PCT, STOP_LOSS_PCT, FORWARD_HOLD_MINUTES)

                if result:
                    result["n_window"] = n_window
                    result["buildup_range_pct"] = buildup_range_pct
                    result["direction"] = direction
                    result["vol_surge"] = vol_surge
                    occurrences.append(result)
                    break  # Avoid counting duplicate overlapping windows for same candle

    return occurrences

async def main():
    log.info("📊 Starting Bitget Historical Backtest: Small 0.5% Build-Up to Big Move Expansion...")

    async with aiohttp.ClientSession() as session:
        tickers = await fetch_tickers(session)
        if not tickers:
            log.error("Could not fetch Bitget tickers.")
            return

        valid_symbols = [
            t["symbol"] for t in tickers
            if float(t.get("quoteVolume", 0.0) or (float(t.get("baseVolume", 0.0)) * float(t.get("lastPr", 0.0)))) >= MIN_24H_VOLUME
        ]

        log.info(f"✅ Found {len(valid_symbols)} Bitget Futures pairs with ${MIN_24H_VOLUME/1e3:.0f}k+ Volume. Running 500-candle backtest...")

        all_occurrences = []
        semaphore = asyncio.Semaphore(12)

        async def worker(symbol):
            async with semaphore:
                candles_1m = await fetch_historical_candles(session, symbol, limit=500)
                if candles_1m:
                    res = scan_symbol_buildup_patterns(candles_1m)
                    all_occurrences.extend(res)

        tasks = [worker(sym) for sym in valid_symbols[:80]]  # Top 80 liquid pairs
        await asyncio.gather(*tasks)

        total_samples = len(all_occurrences)
        if total_samples > 0:
            wins = sum(1 for o in all_occurrences if o["won"])
            losses = total_samples - wins
            win_rate = (wins / total_samples) * 100.0
            avg_gain = sum(o["max_gain"] for o in all_occurrences) / total_samples
            avg_dd = sum(o["max_dd"] for o in all_occurrences) / total_samples
            avg_window = sum(o["n_window"] for o in all_occurrences) / total_samples

            log.info("====================================================================================================")
            log.info("📊 BITGET HISTORICAL BACKTEST SUMMARY (SMALL 0.5% BUILD-UP TO BIG MOVE EXPANSION):")
            log.info(f"   • TOTAL PATTERN OCCURRENCES   : {total_samples} Trade Setups")
            log.info(f"   • WINNING TRADES (+2.50% TP)   : {wins} Wins")
            log.info(f"   • LOSING TRADES (-1.25% SL)    : {losses} Losses")
            log.info(f"   • WIN RATE PERCENTAGE         : {win_rate:.2f}%")
            log.info(f"   • AVERAGE MAX GAIN PER TRADE  : +{avg_gain:.2f}%")
            log.info(f"   • AVERAGE DRAWDOWN PER TRADE  : -{avg_dd:.2f}%")
            log.info(f"   • AVERAGE BUILD-UP WINDOW (N) : {avg_window:.1f} 1m Candles")
            log.info("====================================================================================================")
        else:
            log.info("ℹ️ No build-up patterns matched in historical sample.")

if __name__ == "__main__":
    asyncio.run(main())
