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
    """Each bot analyzes its coins and finds the one with the weakest side."""
    best_in_chunk = None
    highest_weakness = -1

    for sym in symbols_chunk:
        candles = await fetch_okx_candles(session, sem, sym)
        if not candles: continue
        
        last_10 = candles[-10:]
        
        # 1. Calculate Volume Dominance
        green_vol = sum(c[5] for c in last_10 if c[4] > c[1]) # Close > Open
        red_vol = sum(c[5] for c in last_10 if c[4] < c[1])   # Close < Open
        total_vol = green_vol + red_vol
        
        if total_vol == 0: continue
        
        red_dominance = red_vol / total_vol
        green_dominance = green_vol / total_vol
        
        # 2. Calculate Price Change (Last 10 mins)
        open_price = last_10[0][1]
        close_price = last_10[-1][4]
        price_change_pct = ((close_price - open_price) / open_price) * 100
        
        direction = None
        weakness_score = 0
        
        # Scenario A: Weak Buy Side (Price dropping, Red volume dominating)
        # If red dominance is >60% and price is down, the buy side is collapsing.
        if price_change_pct < -0.5 and red_dominance > 0.60:
            direction = "SHORT"
            # The higher the red dominance and the steeper the drop, the weaker the buy side.
            weakness_score = abs(price_change_pct) * red_dominance 
            
        # Scenario B: Weak Sell Side (Price pumping, Green volume dominating)
        # If green dominance is >60% and price is up, the sell side is collapsing.
        elif price_change_pct > 0.5 and green_dominance > 0.60:
            direction = "LONG"
            weakness_score = abs(price_change_pct) * green_dominance

        if direction and weakness_score > highest_weakness:
            highest_weakness = weakness_score
            best_in_chunk = {
                "symbol": sym, 
                "direction": direction, 
                "score": weakness_score,
                "price_change": price_change_pct,
                "dominance": red_dominance if direction == "SHORT" else green_dominance
            }

    return best_in_chunk

async def run_market_scan():
    print("🌐 Fetching Top 1000 coins (CoinGecko)...")
    valid_coins = []
    
    # Using CoinGecko to avoid CMC API blocks
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
    print(f"👨‍🎓 Spawned {len(chunks)} bots to hunt for the weakest side.")

    sem = asyncio.Semaphore(30)
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    
    if not valid_winners:
        print("❌ No weak sides found. The market is balanced.")
        return None

    print(f"🏆 Gathered {len(valid_winners)} weak sides. The bots are voting...")

    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    
    print(f"🔥 THE WEAKEST SIDE IS: {best['symbol']} ({best['direction']})")
    print(f"   Price Move: {best['price_change']:.2f}% | Volume Dominance: {best['dominance']*100:.1f}%")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
