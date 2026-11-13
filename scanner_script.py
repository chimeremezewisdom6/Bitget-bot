import requests
import json
import os
import asyncio
import aiohttp
import ccxt

async def fetch_binance_candles(session, sem, sym):
    async with sem:
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=1m&limit=60"
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                if len(data) < 60: return None
                return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
        except Exception:
            return None

async def process_bot_chunk(bot_id, symbols_chunk, session, sem):
    best_in_chunk = None
    highest_score = -1
    for sym in symbols_chunk:
        candles = await fetch_binance_candles(session, sem, sym)
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
            best_in_chunk = {
                "bot_id": bot_id,
                "symbol": sym,
                "direction": "LONG" if end_price > start_price else "SHORT",
                "score": score
            }
    return best_in_chunk

async def get_bitget_tradable_symbols():
    exchange = ccxt.bitget({
        'options': {'defaultType': 'swap', 'uta': True}
    })
    markets = await exchange.load_markets()
    tradable = set()
    for sym, m in markets.items():
        if m.get('active') and m.get('swap') and m.get('linear'):
            if m.get('quote') == 'USDT':
                tradable.add(m['base'])
    await exchange.close()
    return tradable

async def run_market_scan():
    print("🌐 Fetching up to 5,000 coins from CoinMarketCap (Keyless API)...")
    
    # CMC Keyless Public API allows up to 5000 results
    url = "https://pro-api.coinmarketcap.com/public-api/v3/cryptocurrency/listings/latest"
    params = {
        "start": "1",
        "limit": "5000",  # Fetch maximum allowed
        "convert": "USD"
    }
    
    try:
        # No API key or special headers needed
        res = requests.get(url, params=params, timeout=30)
        data = res.json().get('data', [])
    except Exception as e:
        print(f"CoinMarketCap failed: {e}")
        return None

    if not data:
        print("❌ No data returned from CMC.")
        return None

    # FILTER: 24-HOUR VOLUME >= $1,000,000
    valid_bases = set()
    for coin in data:
        vol_24h = coin.get('quote', {}).get('USD', {}).get('volume_24h', 0)
        if vol_24h and vol_24h >= 1_000_000:
            valid_bases.add(coin['symbol'])
    
    print(f"📊 CoinMarketCap: Found {len(valid_bases)} bases with >= $1M 24h volume (from {len(data)} total coins).")
    
    # FILTER: MUST BE ON BITGET
    bitget_bases = await get_bitget_tradable_symbols()
    final_symbols = [b for b in valid_bases if b in bitget_bases]
    print(f"🏦 Bitget filter: {len(final_symbols)} tradable bases remain.")
    
    if not final_symbols:
        print("❌ No tradable coins found after filtering.")
        return None

    # DIVIDE INTO 50 BOTS
    chunk_size = max(1, len(final_symbols) // 50)
    chunks = [final_symbols[i:i + chunk_size] for i in range(0, len(final_symbols), chunk_size)]
    print(f"👨‍🎓 Spawned {len(chunks)} bots to analyze the coins.")
    
    sem = asyncio.Semaphore(20) # Keep concurrent requests safe
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)
    
    valid_winners = [w for w in winners if w is not None]
    if not valid_winners:
        print("❌ No valid winners found.")
        return None
    
    # MAIN PATH VOTE: Pick the absolute best fingerprint
    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    print(f"🔥 THE WINNER IS: {best['symbol']} ({best['direction']}) Score: {best['score']:.4f}")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin:
            json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else:
            json.dump({}, f)
