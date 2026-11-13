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
            url = f"https://www.okx.com/api/v5/market/candles?instId={sym}-USDT&bar=1m&limit=15"
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = (await resp.json()).get('data', [])
                if len(data) < 12: return None
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

async def run_market_scan():
    print("🌐 Fetching global volume (CoinGecko)...")
    valid_coins = []
    
    try:
        for page in range(1, 4): 
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
    tradable_coins = list(set([c for c in valid_coins if c in bitget_bases]))[:50] # Check top 50
    
    print(f"🔎 Analyzing {len(tradable_coins)} tradable coins for aggressive dumps...")

    best_dump = None
    highest_score = -1
    sem = asyncio.Semaphore(5)
    
    async with aiohttp.ClientSession() as session:
        for sym in tradable_coins:
            candles = await fetch_okx_candles(session, sem, sym)
            if not candles: continue
            
            last_10 = candles[-10:]
            
            # 1. Calculate Volume & Red Candle Dominance
            total_vol = sum(c[5] for c in last_10)
            red_vol = sum(c[5] for c in last_10 if c[4] < c[1]) # Close < Open
            
            if total_vol == 0 or (red_vol / total_vol) < 0.6:
                continue # Skip if sellers don't dominate volume
                
            # 2. Calculate Drop & Ensure it's NOT going up
            start_price = last_10[0][1]
            end_price = last_10[-1][4]
            
            if end_price >= start_price:
                continue # Exclude Longs! Must be dumping.
                
            drop_pct = ((start_price - end_price) / start_price) * 100
            
            # 3. Check Volatility (Average fluctuation > 0.1%)
            fluctuations = [((c[2] - c[3]) / c[3]) * 100 for c in last_10]
            if (sum(fluctuations) / len(fluctuations)) < 0.1:
                continue
                
            # 4. Calculate Dump Efficiency (How straight is the dump?)
            total_distance = sum(abs(last_10[i][4] - last_10[i-1][4]) for i in range(1, len(last_10)))
            net_distance = start_price - end_price
            efficiency = net_distance / total_distance if total_distance > 0 else 0
            
            # Final Score: Big drop, straight line, heavy red volume
            score = drop_pct * efficiency * (red_vol / total_vol)

            if score > highest_score:
                highest_score = score
                best_dump = {"symbol": sym, "direction": "SHORT", "score": score}
                print(f"🩸 Found strong dump: {sym} | Drop: {drop_pct:.2f}% | Score: {score:.2f}")

    if best_dump:
        print(f"🔥 THE STRONGEST DUMP IS: {best_dump['symbol']} (Score: {best_dump['score']:.4f})")
    else:
        print("❌ No valid dumps found.")
        
    return best_dump

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
