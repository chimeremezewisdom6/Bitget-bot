import requests
import json
import os
import asyncio
import aiohttp
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# THE TARGET: Price Move >= 0.73% AND Volume Dominance <= 60.8%
MIN_PRICE_MOVE = 0.73
MAX_VOLUME_DOMINANCE = 0.608

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
        
        green_dominance = green_vol / total_vol
        
        # 2. Calculate Price Change
        open_price = last_10[0][1]
        close_price = last_10[-1][4]
        price_change_pct = ((close_price - open_price) / open_price) * 100
        
        # --- YOUR STRICT RULES ---
        if price_change_pct >= MIN_PRICE_MOVE and green_dominance <= MAX_VOLUME_DOMINANCE:
            
            # FIXED: Prevent ZeroDivisionError
            if green_dominance == 0:
                green_dominance = 0.0001 # Give it a massive score if there was zero buying volume but price went up
                
            score = price_change_pct / green_dominance
            
            if score > highest_score:
                highest_score = score
                best_in_chunk = {
                    "symbol": sym, 
                    "direction": "LONG", 
                    "score": score,
                    "move": price_change_pct,
                    "dominance": green_dominance
                }

    return best_in_chunk

async def run_market_scan():
    print("🌐 Fetching ALL coins from CoinPaprika (No Rate Limits)...")
    valid_coins = []
    
    try:
        # CoinPaprika returns 14,000+ coins in ONE request
        res = requests.get("https://api.coinpaprika.com/v1/tickers", timeout=30)
        data = res.json()
        
        # Sort by rank (Top 3000)
        data = [c for c in data if c.get('rank') and c.get('rank') <= 3000]
        
        for coin in data:
            sym = coin['symbol'].upper()
            if sym in MEGA_COINS: continue
            
            usd_data = coin.get('quotes', {}).get('USD', {})
            price = usd_data.get('price', 0)
            vol = usd_data.get('volume_24h', 0)
            
            # Filter: Price under $10 (for your $1.58 balance) and Volume > $1M
            if price <= 10.0 and vol >= 1_000_000:
                valid_coins.append(sym)
                
    except Exception as e:
        print(f"CoinPaprika failed: {e}")
        return None

    bitget_bases = await get_bitget_tradable_symbols()
    final_symbols = list(set([c for c in valid_coins if c in bitget_bases]))
    
    print(f"📊 Found {len(final_symbols)} tradable coins with >$1M volume.")

    if not final_symbols: return None

    # DIVIDE INTO 100 BOTS
    chunk_size = max(1, len(final_symbols) // 100)
    chunks = [final_symbols[i:i + chunk_size] for i in range(0, len(final_symbols), chunk_size)]
    print(f"👨‍🎓 Spawned {len(chunks)} bots to hunt for Thin-Book Pumps (>0.73% Move, <60.8% Vol).")

    sem = asyncio.Semaphore(30)
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    
    if not valid_winners:
        print("❌ No coins met the Thin-Book Pump criteria. No trade.")
        return None

    print(f"🏆 Gathered {len(valid_winners)} perfect matches. The bots are voting...")

    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    best = valid_winners[0]
    
    print(f"🔥 THE WINNER IS: {best['symbol']} ({best['direction']})")
    print(f"   Price Move: {best['move']:.2f}% (Target: 0.73%+)")
    print(f"   Volume Dominance: {best['dominance']*100:.1f}% (Target: 60.8%-)")
    return best

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
