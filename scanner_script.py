import requests
import json
import os
import asyncio
import aiohttp

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
    """Each bot analyzes its 10 coins and picks the best price fingerprint."""
    best_in_chunk = None
    highest_score = -1

    for sym in symbols_chunk:
        candles = await fetch_binance_candles(session, sem, sym)
        if not candles: continue
        
        # Look at the last 10 minutes (11 candles to get the open of the 1st minute)
        last_10 = candles[-11:]
        start_price = last_10[0][1] # Open of first candle
        end_price = last_10[-1][4]  # Close of last candle
        
        # 1. Total Percentage Move
        total_move_pct = abs((end_price - start_price) / start_price) * 100
        
        # 2. Efficiency (Smoothness of the move)
        # Sum of absolute movements between each minute's close
        total_distance = sum(abs(last_10[i][4] - last_10[i-1][4]) for i in range(1, len(last_10)))
        net_distance = abs(end_price - start_price)
        
        # If there's no movement at all, skip
        if total_distance == 0: continue
            
        efficiency = net_distance / total_distance # 1.0 = perfectly straight line
        
        # 3. The Fingerprint Score
        score = total_move_pct * efficiency

        if score > highest_score:
            highest_score = score
            best_in_chunk = {
                "bot_id": bot_id,
                "symbol": sym, 
                "direction": "LONG" if end_price > start_price else "SHORT",
                "move_pct": total_move_pct,
                "efficiency": efficiency,
                "score": score
            }
            
    return best_in_chunk

async def run_market_scan():
    print("🌐 Fetching 500+ coins globally...")
    try:
        res = requests.get("https://api.coinpaprika.com/v1/tickers", timeout=15)
        tickers = res.json()
    except Exception as e:
        print(f"CoinPaprika failed: {e}")
        return None

    valid_symbols = []
    for t in tickers:
        vol = t.get('quotes', {}).get('USD', {}).get('volume_24h', 0)
        if vol and vol >= 1_000_000:
            valid_symbols.append(t['symbol'])

    print(f"📊 Found {len(valid_symbols)} coins. Dividing into 50 bots...")

    # DIVIDE INTO 50 CHUNKS
    chunk_size = max(1, len(valid_symbols) // 50)
    chunks = [valid_symbols[i:i + chunk_size] for i in range(0, len(valid_symbols), chunk_size)]
    
    print(f"👨‍🎓 Spawned {len(chunks)} bots to analyze their 10 coins.")

    sem = asyncio.Semaphore(20) # Limit to 20 concurrent requests to Binance
    async with aiohttp.ClientSession() as session:
        tasks = [process_bot_chunk(i, chunk, session, sem) for i, chunk in enumerate(chunks)]
        winners = await asyncio.gather(*tasks)

    valid_winners = [w for w in winners if w is not None]
    
    if not valid_winners:
        print("❌ No valid winners found.")
        return None

    print(f"🏆 Gathered {len(valid_winners)} winners. The bots are voting...")

    # MAIN PATH: Pick the absolute best fingerprint from the 50 winners
    valid_winners.sort(key=lambda x: x['score'], reverse=True)
    absolute_best = valid_winners[0]

    print(f"🔥 THE VOTED BEST FINGERPRINT IS: {absolute_best['symbol']} ({absolute_best['direction']})")
    print(f"   Move: {absolute_best['move_pct']:.2f}% | Efficiency: {absolute_best['efficiency']:.2f} | Score: {absolute_best['score']:.2f}")
    return absolute_best

if __name__ == "__main__":
    try:
        best_coin = asyncio.run(run_market_scan())
        if best_coin:
            with open("candidate.json", "w") as f:
                json.dump({
                    "symbol": best_coin['symbol'],
                    "direction": best_coin['direction'],
                    "score": best_coin['score']
                }, f, indent=2)
            print("✅ Saved to candidate.json")
        else:
            with open("candidate.json", "w") as f: json.dump({}, f)
    except Exception as e:
        print(f"❌ CRASHED: {e}")
        with open("candidate.json", "w") as f: json.dump({}, f)
