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
    tradable_coins = list(set([c for c in valid_coins if c in bitget_bases]))[:60] # Check top 60
    
    print(f"🔎 Analyzing {len(tradable_coins)} coins for massive two-sided swings...")

    best_swing = None
    highest_score = -1
    sem = asyncio.Semaphore(5)
    
    async with aiohttp.ClientSession() as session:
        for sym in tradable_coins:
            candles = await fetch_okx_candles(session, sem, sym)
            if not candles: continue
            
            last_10 = candles[-10:]
            open_price = last_10[0][1]
            high_price = max(c[2] for c in last_10)
            low_price = min(c[3] for c in last_10)
            close_price = last_10[-1][4]
            
            # Calculate moves from the open price
            up_move = ((high_price - open_price) / open_price) * 100
            down_move = ((open_price - low_price) / open_price) * 100
            total_range = ((high_price - low_price) / low_price) * 100
            
            direction = None
            
            # Scenario 1: 2% Up Move and 1% Down Move
            if up_move >= 2.0 and down_move >= 1.0 and close_price > open_price:
                direction = "LONG"
                score = up_move * down_move
                
            # Scenario 2: 2% Down Move and 1% Up Move
            elif down_move >= 2.0 and up_move >= 1.0 and close_price < open_price:
                direction = "SHORT"
                score = up_move * down_move

            if direction and score > highest_score:
                highest_score = score
                best_swing = {"symbol": sym, "direction": direction, "score": score}
                print(f"⚡ Found Swing: {sym} ({direction}) | Up: {up_move:.2f}% | Down: {down_move:.2f}% | Range: {total_range:.2f}%")

    if best_swing:
        print(f"🔥 THE BEST SWING IS: {best_swing['symbol']} ({best_swing['direction']}) Score: {best_swing['score']:.4f}")
    else:
        print("❌ No coins met the 2%-1% swing criteria in this scan.")
        
    return best_swing

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
