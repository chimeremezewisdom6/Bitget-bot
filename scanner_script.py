import requests
import json
import os
import asyncio
import aiohttp
import ccxt

async def fetch_okx_candles(session, sem, sym):
    async with sem:
        try:
            url = f"https://www.okx.com/api/v5/market/candles?instId={sym}-USDT&bar=1m&limit=60"
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = (await resp.json()).get('data', [])
                if len(data) < 60: return None
                data.reverse()
                return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
        except Exception:
            return None

async def run_market_scan():
    print("🌐 Fetching 24h global volume from CoinMarketCap...")
    url = "https://pro-api.coinmarketcap.com/public-api/v3/cryptocurrency/listings/latest"
    params = {"start": "1", "limit": "5000", "convert": "USD"}
    
    try:
        res = requests.get(url, params=params, timeout=30)
        data = res.json().get('data', [])
    except Exception as e:
        print(f"CoinMarketCap failed: {e}")
        return None

    # 1. Filter for >$1M volume
    valid_coins = []
    for coin in data:
        quote = coin.get('quote', {}).get('USD', {})
        vol_24h = quote.get('volume_24h', 0)
        change_1h = quote.get('percent_change_1h', 0)
        
        if vol_24h and vol_24h >= 1_000_000:
            valid_coins.append({
                "symbol": coin['symbol'],
                "vol_24h": vol_24h,
                "change_1h": change_1h
            })
            
    print(f"📊 Found {len(valid_coins)} coins with >= $1M volume.")

    # 2. Instantly sort to find the Top 10 biggest 1-hour movers (No candles needed!)
    valid_coins.sort(key=lambda x: abs(x['change_1h']), reverse=True)
    top_10_movers = valid_coins[:10]

    # 3. Filter to ensure they are on Bitget
    exchange = ccxt.bitget({'options': {'defaultType': 'swap', 'uta': True}})
    markets = await exchange.load_markets()
    bitget_bases = set(m['base'] for m in markets.values() if m.get('swap') and m.get('linear') and m.get('quote') == 'USDT')
    await exchange.close()

    top_bitget_movers = [c for c in top_10_movers if c['symbol'] in bitget_bases]
    
    if not top_bitget_movers:
        print("❌ None of the top movers are tradable on Bitget.")
        return None

    print(f"🎯 Top 10 movers on Bitget: {[c['symbol'] for c in top_bitget_movers]}")

    # 4. Now we ONLY fetch candles for these Top 10 to calculate the 10-min fingerprint
    best_winner = None
    highest_score = -1
    sem = asyncio.Semaphore(5) # Only 10 coins, so 5 concurrent is plenty
    
    async with aiohttp.ClientSession() as session:
        for coin in top_bitget_movers:
            candles = await fetch_okx_candles(session, sem, coin['symbol'])
            if not candles: continue
            
            last_10 = candles[-11:]
            start_price = last_10[0][1]
            end_price = last_10[-1][4]
            
            total_move_pct = abs((end_price - start_price) / start_price) * 100
            total_distance = sum(abs(last_10[i][4] - last_10[i-1][4]) for i in range(1, len(last_10)))
            
            if total_distance == 0: continue
            efficiency = abs(end_price - start_price) / total_distance
            score = total_move_pct * efficiency

            if score > highest_score:
                highest_score = score
                best_winner = {
                    "symbol": coin['symbol'],
                    "direction": "LONG" if end_price > start_price else "SHORT",
                    "score": score
                }

    if best_winner:
        print(f"🔥 THE ABSOLUTE BEST: {best_winner['symbol']} ({best_winner['direction']}) Score: {best_winner['score']:.4f}")
    else:
        print("❌ No valid winners found among the top 10.")
        
    return best_winner

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin:
            json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else:
            json.dump({}, f)
