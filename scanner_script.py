import requests
import json
import os
import asyncio
import time
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}
MIN_24H_VOLUME_USD = 1_000_000

async def run_market_scan():
    start_time = time.time()
    try:
        exchange = ccxt_async.bitget({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
        await exchange.load_markets()
        
        print("📊 Fetching 24-Hour tickers from Bitget...")
        tickers = await exchange.fetch_tickers()
        
        valid_coins = []
        for sym, ticker in tickers.items():
            if not sym.endswith("USDT:USDT"): continue
            base = sym.split('/')[0]
            if base in MEGA_COINS: continue
            
            vol_24h = ticker.get('quoteVolume')
            change = ticker.get('percentage', 0)
            
            # Filter by 24h Volume > $1M
            if vol_24h and float(vol_24h) >= MIN_24H_VOLUME_USD:
                valid_coins.append({"symbol": base, "vol": float(vol_24h), "change": abs(change)})
                
        # Sort by 24h percentage change to find the most volatile, take top 100
        valid_coins.sort(key=lambda x: x["change"], reverse=True)
        top_100 = [c["symbol"] for c in valid_coins[:100]]
        
        await exchange.close()
        
        print(f"🎯 Found {len(top_100)} high-volume volatile coins to watch.")
        
        with open("candidate.json", "w") as f:
            json.dump({"watchlist": top_100, "timestamp": time.time()}, f, indent=2)
            
        print(f"✅ Watchlist saved. Scan Time: {time.time() - start_time:.1f}s")
        
    except Exception as e:
        print(f"❌ Scanner failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_market_scan())
