import requests
import json
import os
import asyncio
import aiohttp
import ccxt.async_support as ccxt_async

# THE DAVID RULES
MIN_PRICE_MOVE = 0.22
MAX_WINNING_DOMINANCE = 0.50
MIN_AVG_FLUCTUATION = 0.10

async def fetch_okx_candles(session, sem, sym):
    async with sem:
        try:
            url = f"https://www.okx.com/api/v5/market/candles?instId={sym}-USDT&bar=1m&limit=15"
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = (await resp.json()).get('data', [])
                if len(data) < 10: return None
                data.reverse()
                return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
        except Exception:
            return None

async def get_bitget_full_universe():
    """Fetches ALL Bitget markets via CCXT and filters for >$1M volume."""
    exchange = ccxt_async.bitget({'options': {'defaultType': 'swap', 'uta': True}})
    try:
        print("📥 Loading all Bitget markets via CCXT...")
        markets = await exchange.load_markets()
        
        print("📊 Fetching all tickers from Bitget...")
        tickers = await exchange.fetch_tickers()
        
        valid_coins = []
        for sym, ticker in tickers.items():
            # Only USDT perpetuals
            if not sym.endswith("USDT"): continue
            market = markets.get(sym)
            if not market or not market.get('swap') or not market.get('linear'): continue
            
            # Volume filter: >$1M 24h quote volume
            vol = ticker.get('quoteVolume', 0) or 0
            if vol >= 1_000_000:
                base = sym.split("/")[0]
                valid_coins.append(base)
                
        print(f"✅ Found {len(valid_coins)} Bitget coins with >$1M volume.")
        return list(set(valid_coins)) # Remove duplicates
    except Exception as e:
        print(f"❌ Bitget CCXT failed: {e}")
        return []
    finally:
        await exchange.close()

async def process_bot_chunk(bot_id, symbols_chunk, session, sem):
    best_in_chunk = None
    highest_score = -1

    for sym in symbols_chunk:
        candles = await fetch_okx_candles(session, sem, sym)
        if not candles: continue
        
        last_10 = candles[-10:]
        
        # 1. Check Average Fluctuation (>= 0.1% per minute)
        fluctuations = [((c[2] - c[3]) / c[3]) * 100 for c in last_10]
        avg_fluctuation = sum(fluctuations) / len(fluctuations)
        if avg_fluctuation < MIN_AVG_FLUCTUATION: continue
            
        # 2. Calculate Volume Dominance
        green_vol = sum(c[5] for c in last_10 if c[4] > c[1])
        red_vol = sum(c[5] for c in last_10 if c[4] < c[1])
        total_vol = green_vol + red_vol
        if total_vol == 0: continue
        
        green_dominance = green_vol / total_vol
        red_dominance = red_vol / total_vol
        
        # 3. Calculate Price Change
        open_price = last_10[0][1]
        close_price = last_10[-1][4]
        price_change_pct = ((close_price - open_price) / open_price) * 100
        
        direction = None
        winning_dominance = 0
        
        # DAVID SETUP 1: Long (Aggressive Buyers)
        if price_change_pct >= MIN_PRICE_MOVE and green_dominance <= MAX_WINNING_DOMINANCE and green_dominance > 0:
            direction = "LONG"
            winning_dominance = green_dominance
            
        # DAVID SETUP 2: Short (Aggressive Sellers)
        elif price_change_pct <= -MIN_PRICE_MOVE and red_dominance <= MAX_WINNING_DOMINANCE and red_dominance > 0:
            direction = "SHORT"
            winning_dominance = red_dominance

        if direction:
            score = abs(price_change_pct) / winning_dominance
            if score > highest_score:
                highest_score = score
                best_in_chunk = {
                    "symbol": sym, "direction": direction, "score": score,
                    "move": price_change_pct, "volume_pct": winning_dominance,
                    "avg_fluct": avg_fluctuation
                }

    return best_in_chunk

async def run_market_scan():
    # Use CCXT to get the full Bitget universe
    final_symbols = await get_bitget_full_universe()
    
    if not final_symbols: 
        print("❌ No tradable coins found.")
        return None

    # DIVIDE INTO 100 BOTS
    chunk_size = max(1, len(final_symbols) // 100)
    chunks = [final_symbols[i:i + chunk_size] for i in range(0, len(final_symbols), chunk_size)]
    print(f"👨‍🎓 Spawned {len(chunks)} bots to hunt for DAVID setups.")

    sem = asyncio.Semaphore(30)
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    
    if not valid_winners:
        print("❌ No David setups found. The market is behaving normally.")
        return None

    print(f"🏆 Gathered {len(valid_winners)} David setups. The bots are voting...")

    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    
    print(f"🔥 THE BIGGEST DAVID IS: {best['symbol']} ({best['direction']})")
    print(f"   Price Move: {best['move']:.2f}%")
    print(f"   Winning Volume: {best['volume_pct']*100:.1f}% (The minority side pushed the price!)")
    print(f"   Average Fluctuation: {best['avg_fluct']:.2f}%/min")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
