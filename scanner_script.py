import requests
import json
import os
import asyncio
import aiohttp
import ccxt.async_support as ccxt_async

MEGA_COINS = {
    'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 
    'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'
}

async def fetch_okx_candles(session, sem, sym):
    async with sem:
        try:
            url = f"https://www.okx.com/api/v5/market/candles?instId={sym}-USDT&bar=1m&limit=12"
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = (await resp.json()).get('data', [])
                if len(data) < 10: return None
                data.reverse()
                return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
        except Exception:
            return None

async def get_bitget_tradable_symbols():
    exchange = ccxt_async.bitget({'options': {'defaultType': 'swap', 'uta': True}})
    try:
        markets = await exchange.load_markets()
        return set(m['base'] for m in markets.values() if m.get('active') and m.get('swap') and m.get('linear') and m.get('quote') == 'USDT')
    except Exception:
        return set()
    finally:
        await exchange.close()

async def process_bot_chunk(bot_id, symbols_chunk, session, sem):
    """Each bot analyzes its assigned coins and returns the best swing."""
    best_in_chunk = None
    highest_score = -1

    for sym in symbols_chunk:
        candles = await fetch_okx_candles(session, sem, sym)
        if not candles: continue
        
        last_10 = candles[-10:]
        open_price = last_10[0][1]
        high_price = max(c[2] for c in last_10)
        low_price = min(c[3] for c in last_10)
        close_price = last_10[-1][4]
        
        up_move = ((high_price - open_price) / open_price) * 100
        down_move = ((open_price - low_price) / open_price) * 100
        
        direction = None
        
        # Priority 1: The strict 2% up / 1% down rule (or vice versa)
        if up_move >= 2.0 and down_move >= 1.0 and close_price > open_price:
            direction = "LONG"
            score = up_move * down_move * 2 # Give a bonus to strict matches
        elif down_move >= 2.0 and up_move >= 1.0 and close_price < open_price:
            direction = "SHORT"
            score = up_move * down_move * 2 # Give a bonus to strict matches
        # Fallback: Just pick the highest two-sided volatility
        elif up_move > 0.5 and down_move > 0.5:
            direction = "LONG" if close_price > open_price else "SHORT"
            score = up_move * down_move

        if direction and score > highest_score:
            highest_score = score
            best_in_chunk = {"symbol": sym, "direction": direction, "score": score}

    return best_in_chunk

async def run_market_scan():
    print("🌐 Fetching global volume (CoinGecko)...")
    valid_coins = []
    
    try:
        for page in range(1, 5): # Fetch top 1000 coins
            url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}"
            res = requests.get(url, timeout=15)
            if res.status_code != 200: break
            for coin in res.json():
                sym = coin['symbol'].upper()
                if sym in MEGA_COINS or coin.get('current_price', 0) > 10.0: continue
                if coin.get('total_volume', 0) >= 1_000_000:
                    valid_coins.append(sym)
    except Exception as e:
        print(f"CoinGecko failed: {e}")
        return None

    bitget_bases = await get_bitget_tradable_symbols()
    final_symbols = list(set([c for c in valid_coins if c in bitget_bases]))
    
    print(f"📊 Found {len(final_symbols)} tradable coins with >$1M volume.")

    if not final_symbols:
        return None

    # DIVIDE INTO 50 BOTS
    chunk_size = max(1, len(final_symbols) // 50)
    chunks = [final_symbols[i:i + chunk_size] for i in range(0, len(final_symbols), chunk_size)]
    print(f"👨‍🎓 Spawned {len(chunks)} bots to analyze their coins.")

    sem = asyncio.Semaphore(20) # 20 concurrent requests to OKX to avoid rate limits
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    
    if not valid_winners:
        print("❌ All bots failed to find a valid swing.")
        return None

    print(f"🏆 Gathered {len(valid_winners)} winners. The bots are voting...")

    # MAIN PATH VOTE: Pick the absolute best fingerprint
    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    
    print(f"🔥 THE WINNER IS: {best['symbol']} ({best['direction']}) Score: {best['score']:.4f}")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
