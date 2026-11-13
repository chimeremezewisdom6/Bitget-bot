import requests
import json
import os
import asyncio
import aiohttp
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

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
        open_price = last_10[0][1]
        close_price = last_10[-1][4]
        
        total_vol = sum(c[5] for c in last_10)
        price_change_pct = ((close_price - open_price) / open_price) * 100
        
        # Scenario A: Aggressive Dump
        if price_change_pct < -1.0 and total_vol > 0:
            score = abs(price_change_pct) * (total_vol / 1000) 
            if score > highest_score:
                highest_score = score
                best_in_chunk = {"symbol": sym, "direction": "SHORT", "score": score, "type": "Aggressive Dump"}
                
        # Scenario B: Quiet Dump
        elif price_change_pct < -0.5 and price_change_pct > -3.0 and total_vol > 0:
            score = abs(price_change_pct) / (total_vol / 1000) 
            if score > highest_score:
                highest_score = score
                best_in_chunk = {"symbol": sym, "direction": "SHORT", "score": score, "type": "Quiet Dump"}
                
        # Scenario C: Aggressive Buy
        elif price_change_pct > 1.0 and total_vol > 0:
            score = abs(price_change_pct) * (total_vol / 1000)
            if score > highest_score:
                highest_score = score
                best_in_chunk = {"symbol": sym, "direction": "LONG", "score": score, "type": "Aggressive Buy"}

    return best_in_chunk

async def run_market_scan():
    valid_coins = []
    
    # TRY COINMARKETCAP FIRST
    print("🌐 Fetching Top 2000 coins (CoinMarketCap)...")
    url = "https://pro-api.coinmarketcap.com/public-api/v3/cryptocurrency/listings/latest"
    params = {"start": "1", "limit": "2000", "convert": "USD"}
    
    try:
        res = requests.get(url, params=params, timeout=20)
        res_json = res.json()
        
        # FIX: Check if it's a dictionary before calling .get()
        if isinstance(res_json, dict):
            data = res_json.get('data', [])
            for coin in data:
                sym = coin['symbol'].upper()
                if sym in MEGA_COINS or coin.get('quote', {}).get('USD', {}).get('price', 0) > 10.0: continue
                if coin.get('quote', {}).get('USD', {}).get('volume_24h', 0) >= 1_000_000:
                    valid_coins.append(sym)
        else:
            print(f"⚠️ CMC returned a list (likely rate limit). Falling back to CoinGecko...")
    except Exception as e:
        print(f"⚠️ CMC failed: {e}. Falling back to CoinGecko...")

    # FALLBACK TO COINGECKO IF CMC FAILS
    if not valid_coins:
        try:
            for page in range(1, 5): # Fetch top 1000 coins
                cg_url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}"
                cg_res = requests.get(cg_url, timeout=15)
                if cg_res.status_code != 200: break
                for coin in cg_res.json():
                    sym = coin['symbol'].upper()
                    if sym in MEGA_COINS or coin.get('current_price', 0) > 10.0: continue
                    if coin.get('total_volume', 0) >= 1_000_000:
                        valid_coins.append(sym)
            print(f"✅ Successfully fetched {len(valid_coins)} coins from CoinGecko.")
        except Exception as e:
            print(f"❌ CoinGecko also failed: {e}")
            return None

    bitget_bases = await get_bitget_tradable_symbols()
    final_symbols = list(set([c for c in valid_coins if c in bitget_bases]))
    
    print(f"📊 Found {len(final_symbols)} tradable coins with >$1M volume on Bitget.")

    if not final_symbols: return None

    # DIVIDE INTO 100 BOTS
    chunk_size = max(1, len(final_symbols) // 100)
    chunks = [final_symbols[i:i + chunk_size] for i in range(0, len(final_symbols), chunk_size)]
    print(f"👨‍🎓 Spawned {len(chunks)} bots to hunt for extremes.")

    sem = asyncio.Semaphore(30)
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    
    if not valid_winners:
        print("❌ No extreme scenarios found.")
        return None

    print(f"🏆 Gathered {len(valid_winners)} winners. The bots are voting...")

    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    
    print(f"🔥 THE ABSOLUTE EXTREME IS: {best['symbol']} ({best['direction']}) | Type: {best['type']} | Score: {best['score']:.4f}")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
