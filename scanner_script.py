import requests
import json
import os
import asyncio
import aiohttp
import time
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# THE TRAPPED SELLER RULES
MIN_PRICE_MOVE = 0.22          # Must move up at least 0.22%
MAX_WINNING_VOLUME = 0.40      # Buy volume (the aggressor) must be < 40%
MIN_LOSING_VOLUME = 0.60       # Sell volume (the trapped) must be > 60%
MIN_AVG_FLUCTUATION = 0.20     # Average fluctuation per minute must be >= 0.2%

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

async def get_global_universe():
    print("🌐 Fetching full global universe from CoinLore...")
    all_coins = []
    start = 0
    limit = 100
    
    try:
        while True:
            url = f"https://api.coinlore.net/api/tickers/?start={start}&limit={limit}"
            res = requests.get(url, timeout=15)
            data = res.json().get('data', [])
            if not data: break
                
            for coin in data:
                sym = coin.get('symbol', '').upper()
                vol = coin.get('volume24', 0) or 0
                if vol >= 1_000_000 and sym not in MEGA_COINS:
                    all_coins.append(sym)
                    
            start += limit
            time.sleep(0.5)
            if start > 15000: break 
    except Exception as e:
        print(f"CoinLore failed: {e}")
        return []
        
    return list(set(all_coins))

async def process_bot_chunk(bot_id, symbols_chunk, session, sem):
    best_in_chunk = None
    highest_score = -1

    for sym in symbols_chunk:
        candles = await fetch_okx_candles(session, sem, sym)
        if not candles: continue
        
        last_10 = candles[-10:]
        
        # 1. Check Average Fluctuation (>= 0.2% per minute)
        fluctuations = [((c[2] - c[3]) / c[3]) * 100 for c in last_10]
        avg_fluctuation = sum(fluctuations) / len(fluctuations)
        if avg_fluctuation < MIN_AVG_FLUCTUATION: continue
            
        # 2. Calculate Volume Dominance
        green_vol = sum(c[5] for c in last_10 if c[4] > c[1])
        red_vol = sum(c[5] for c in last_10 if c[4] < c[1])
        total_vol = green_vol + red_vol
        if total_vol == 0: continue
        
        green_pct = green_vol / total_vol # Buy volume
        red_pct = red_vol / total_vol     # Sell volume
        
        # 3. Calculate Price Change
        open_price = last_10[0][1]
        close_price = last_10[-1][4]
        price_change_pct = ((close_price - open_price) / open_price) * 100
        
        # --- THE TRAP SETUP (LONG ONLY) ---
        # Price MUST go up
        # Buy volume MUST be < 40%
        # Sell volume MUST be > 60%
        if price_change_pct >= MIN_PRICE_MOVE:
            if green_pct <= MAX_WINNING_VOLUME and red_pct >= MIN_LOSING_VOLUME:
                
                # Score: Highest price gain divided by the lowest buy volume
                # Example: 1.5% gain on 25% volume = score of 6.0 (Amazing)
                # Example: 0.3% gain on 38% volume = score of 0.78 (Okay)
                score = price_change_pct / green_pct 
                
                if score > highest_score:
                    highest_score = score
                    best_in_chunk = {
                        "symbol": sym, 
                        "direction": "LONG", 
                        "score": score,
                        "move": price_change_pct,
                        "buy_vol": green_pct,
                        "sell_vol": red_pct
                    }

    return best_in_chunk

async def run_market_scan():
    global_coins = await get_global_universe()
    if not global_coins: return None

    bitget_bases = await get_bitget_tradable_symbols()
    final_symbols = list(set([c for c in global_coins if c in bitget_bases]))
    print(f"📊 Found {len(final_symbols)} global coins (>$1M vol) tradable on Bitget.")

    if not final_symbols: return None

    chunk_size = max(1, len(final_symbols) // 100)
    chunks = [final_symbols[i:i + chunk_size] for i in range(0, len(final_symbols), chunk_size)]
    print(f"👨‍🎓 Spawned {len(chunks)} bots to hunt for Trapped Sellers (LONG only, 0.2%+ Fluctuation).")

    sem = asyncio.Semaphore(30)
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    if not valid_winners:
        print("❌ No trapped sellers found. Market is normal.")
        return None

    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    
    print(f"🔥 TRAPPED SELLER DETECTED: {best['symbol']} ({best['direction']})")
    print(f"   Price Move: +{best['move']:.2f}%")
    print(f"   Aggressive Buyers (Winning): {best['buy_vol']*100:.1f}% Volume")
    print(f"   Trapped Sellers (Losing): {best['sell_vol']*100:.1f}% Volume")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
