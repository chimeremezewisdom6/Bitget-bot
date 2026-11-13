import requests
import json
import os
import asyncio
import aiohttp
import ccxt.async_support as ccxt_async

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

async def get_bitget_tradable_symbols():
    # FIXED: Using ccxt_async for await support
    exchange = ccxt_async.bitget({'options': {'defaultType': 'swap', 'uta': True}})
    try:
        markets = await exchange.load_markets()
        tradable = set()
        for sym, m in markets.items():
            if m.get('active') and m.get('swap') and m.get('linear') and m.get('quote') == 'USDT':
                tradable.add(m['base'])
        return tradable
    except Exception as e:
        print(f"Failed to load Bitget markets: {e}")
        return set()
    finally:
        await exchange.close()

async def run_market_scan():
    print("🌐 Fetching global 24h volume (CoinGecko)...")
    valid_coins = []
    
    # Use CoinGecko API (Free, Cloud-friendly, 250 coins per page)
    try:
        for page in range(1, 5): # Fetch top 1000 coins
            url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}"
            res = requests.get(url, timeout=15)
            if res.status_code != 200: break
            
            data = res.json()
            if not data: break
            
            for coin in data:
                vol = coin.get('total_volume', 0)
                if vol and vol >= 1_000_000:
                    valid_coins.append({
                        "symbol": coin['symbol'].upper(),
                        "vol_24h": vol,
                        "change_1h": coin.get('price_change_percentage_1h_in_currency', 0)
                    })
    except Exception as e:
        print(f"CoinGecko failed: {e}")

    # FALLBACK: If CoinGecko fails, use CoinPaprika
    if not valid_coins:
        print("🔄 CoinGecko failed. Falling back to CoinPaprika...")
        try:
            res = requests.get("https://api.coinpaprika.com/v1/tickers", timeout=15)
            for t in res.json():
                vol = t.get('quotes', {}).get('USD', {}).get('volume_24h', 0)
                if vol and vol >= 1_000_000:
                    valid_coins.append({
                        "symbol": t['symbol'].upper(),
                        "vol_24h": vol,
                        "change_1h": t.get('quotes', {}).get('USD', {}).get('percent_change_1h', 0)
                    })
        except Exception as e:
            print(f"CoinPaprika failed: {e}")

    if not valid_coins:
        print("❌ Could not fetch any coin data from APIs.")
        return None

    print(f"📊 Found {len(valid_coins)} coins with >= $1M volume.")

    # Sort by 1-hour change to get top 10 movers
    valid_coins.sort(key=lambda x: abs(x['change_1h']), reverse=True)
    top_10_movers = valid_coins[:10]

    # Filter to Bitget
    bitget_bases = await get_bitget_tradable_symbols()
    top_bitget_movers = [c for c in top_10_movers if c['symbol'] in bitget_bases]
    
    if not top_bitget_movers:
        print("❌ None of the top 10 movers are on Bitget.")
        return None

    print(f"🎯 Top 10 movers on Bitget: {[c['symbol'] for c in top_bitget_movers]}")

    # Fetch candles ONLY for the top 10 to calculate the 10-min fingerprint
    best_winner = None
    highest_score = -1
    sem = asyncio.Semaphore(5)
    
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
        print(f"🔥 THE WINNER IS: {best_winner['symbol']} ({best_winner['direction']}) Score: {best_winner['score']:.4f}")
    else:
        print("❌ No valid candles found for the top movers.")
        
    return best_winner

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin:
            json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else:
            json.dump({}, f)
