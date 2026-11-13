import requests
import json
import os
import asyncio
import aiohttp
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# THE GOLDEN STANDARD (Based on ZRO)
TARGET_MOVE = 0.73    # 0.73% price move
TARGET_DOMINANCE = 0.608 # 60.8% volume dominance
MIN_SIMILARITY = 0.90 # Must be at least 90% similar to the target

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
    best_in_chunk = None
    highest_score = -1

    for sym in symbols_chunk:
        candles = await fetch_okx_candles(session, sem, sym)
        if not candles: continue
        
        last_10 = candles[-10:]
        
        # 1. Calculate Volume Dominance
        green_vol = sum(c[5] for c in last_10 if c[4] > c[1])
        red_vol = sum(c[5] for c in last_10 if c[4] < c[1])
        total_vol = green_vol + red_vol
        
        if total_vol == 0: continue
        
        red_dominance = red_vol / total_vol
        green_dominance = green_vol / total_vol
        
        # 2. Calculate Price Change
        open_price = last_10[0][1]
        close_price = last_10[-1][4]
        price_change_pct = ((close_price - open_price) / open_price) * 100
        
        direction = None
        similarity_score = 0
        score = 0
        
        # --- LONG SETUP (Weak Sell Side) ---
        if price_change_pct > 0:
            # Calculate similarity to Target (how close are we to 0.73% and 60.8%?)
            # We cap it at 1.0 so a 2% move isn't penalized for being "too good"
            move_sim = min(price_change_pct / TARGET_MOVE, 1.0)
            dom_sim = min(green_dominance / TARGET_DOMINANCE, 1.0)
            similarity_score = (move_sim + dom_sim) / 2
            
            if similarity_score >= MIN_SIMILARITY:
                direction = "LONG"
                score = similarity_score
                
        # --- SHORT SETUP (Weak Buy Side) ---
        elif price_change_pct < 0:
            move_sim = min(abs(price_change_pct) / TARGET_MOVE, 1.0)
            dom_sim = min(red_dominance / TARGET_DOMINANCE, 1.0)
            similarity_score = (move_sim + dom_sim) / 2
            
            if similarity_score >= MIN_SIMILARITY:
                direction = "SHORT"
                score = similarity_score

        if direction and score > highest_score:
            highest_score = score
            best_in_chunk = {
                "symbol": sym, 
                "direction": direction, 
                "score": score,
                "move": price_change_pct,
                "dominance": green_dominance if direction == "LONG" else red_dominance,
                "similarity": similarity_score
            }

    return best_in_chunk

async def run_market_scan():
    print("🌐 Fetching Top 1000 coins (CoinGecko)...")
    valid_coins = []
    
    try:
        for page in range(1, 5): 
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

    if not final_symbols: return None

    # DIVIDE INTO 100 BOTS
    chunk_size = max(1, len(final_symbols) // 100)
    chunks = [final_symbols[i:i + chunk_size] for i in range(0, len(final_symbols), chunk_size)]
    print(f"👨‍🎓 Spawned {len(chunks)} bots to hunt for 90%+ matches.")

    sem = asyncio.Semaphore(30)
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    
    if not valid_winners:
        print("❌ No coins met the 90% similarity threshold. No trade.")
        return None

    print(f"🏆 Gathered {len(valid_winners)} 90%+ matches. The bots are voting...")

    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    
    print(f"🔥 THE WINNER IS: {best['symbol']} ({best['direction']})")
    print(f"   Move: {best['move']:.2f}% | Dominance: {best['dominance']*100:.1f}% | Similarity: {best['similarity']*100:.1f}%")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
