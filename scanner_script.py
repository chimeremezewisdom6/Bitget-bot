import requests
import json
import os
import asyncio
import time
import statistics
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}
MIN_24H_VOLUME_USD = 1_000_000
MIN_AVG_VOLATILITY = 0.15

MAJOR_EXCHANGES = ['binance', 'okx', 'bybit', 'bitget', 'kucoin', 'gate', 'mexc', 'htx', 'bingx', 'crypto', 'coinbase', 'kraken', 'bitfinex', 'bitmex', 'deribit']

async def fetch_ccxt_candles(exchange, sym, sem, limit=60):
    async with sem:
        try:
            market_sym = f"{sym}/USDT:USDT"
            if not exchange.has.get('fetchOHLCV'): return None
            ohlcv = await exchange.fetch_ohlcv(market_sym, timeframe='1m', limit=limit)
            if not ohlcv or len(ohlcv) < limit: return None
            
            clean_candles = []
            for c in ohlcv:
                if None in c[1:6]: continue
                clean_candles.append([int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])])
            return clean_candles if len(clean_candles) >= limit else None
        except Exception:
            return None

def fetch_coinmetrics_24h_volume(assets):
    base_url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    volumes = {}
    for i in range(0, min(len(assets), 150), 50):
        try:
            res = requests.get(base_url, params={"assets": ",".join([a.lower() for a in assets[i:i+50]]), "metrics": "volume_trusted_spot_usd_1d", "frequency": "1d", "page_size": 10000}, timeout=15)
            for entry in res.json().get("data", []):
                val = entry.get("volume_trusted_spot_usd_1d")
                if val is not None: volumes[entry["asset"].upper()] = float(val)
        except Exception: pass
        time.sleep(0.5)
    return volumes

def analyze_momentum_lifecycle(candles):
    """
    Scans the 60-minute history to find momentum runs, 
    classifying how they started and how they died.
    """
    if len(candles) < 60: return None
    
    # 1. Check overall volatility in the last 10 mins
    fluct = [((c[2] - c[3]) / c[3]) * 100 for c in candles[-10:]]
    avg_fluct = sum(fluct) / len(fluct)
    if avg_fluct < MIN_AVG_VOLATILITY:
        return None
        
    # 2. Find the most recent momentum run (simplified mapping)
    # We look at the last 20 candles to define the prior run and current run.
    recent = candles[-20:]
    
    # Find where the trend changed direction
    trend_start_idx = 0
    current_dir = "LONG" if recent[-1][4] > recent[-1][1] else "SHORT"
    
    for i in range(len(recent)-1, 0, -1):
        is_green = recent[i][4] > recent[i][1]
        prev_is_green = recent[i-1][4] > recent[i-1][1]
        if is_green != prev_is_green:
            trend_start_idx = i
            break
            
    # Map the lifecycle of the run that just finished (The prior trend)
    # And check the start of the current run (The live trend)
    return {
        "avg_fluct": round(avg_fluct, 3),
        "current_direction": current_dir,
        "trend_start_idx": trend_start_idx
    }

def deep_analyze_record(candles):
    """
    Creates a full record of the last 2 momentum runs.
    Start Types: Accelerating, Slow, Normal
    Death Types: Acceleration Death, Deceleration Death, Normal Death
    """
    if len(candles) < 40: return None
    
    # Split the 40 candles into two 20-candle blocks to analyze prior vs current
    prior_run = candles[-40:-20]
    current_run = candles[-20:]
    
    # Analyze Prior Run (How it died)
    prior_bodies = [abs(c[4] - c[1]) for c in prior_run]
    prior_avg_body = sum(prior_bodies) / len(prior_bodies)
    
    death_type = "Normal Death"
    if prior_bodies[-1] > prior_avg_body * 2:
        death_type = "Acceleration Death (Blow-off)"
    elif prior_bodies[-1] < prior_avg_body * 0.5:
        death_type = "Deceleration Death (Fade)"
        
    # Analyze Current Run (How it started)
    current_bodies = [abs(c[4] - c[1]) for c in current_run]
    current_avg_body = sum(current_bodies) / len(current_bodies)
    
    start_type = "Normal Start"
    if current_bodies[0] > current_avg_body * 1.5:
        start_type = "Accelerating Start"
    elif current_bodies[0] < current_avg_body * 0.5:
        start_type = "Slower Start"
        
    return {
        "start_type": start_type,
        "death_type": death_type,
        "prior_move_pct": round(((prior_run[-1][4] - prior_run[0][1]) / prior_run[0][1]) * 100, 2),
        "current_move_pct": round(((current_run[-1][4] - current_run[0][1]) / current_run[0][1]) * 100, 2)
    }

async def run_market_scan():
    start_time = time.time()
    exchanges = {}
    
    try:
        print("🔌 Initializing Exchanges...")
        for ex_id in MAJOR_EXCHANGES:
            try:
                exchanges[ex_id] = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
                await exchanges[ex_id].load_markets()
            except Exception: pass

        print("📊 Fetching 24-Hour tickers...")
        ticker_tasks = [ex.fetch_tickers() for ex in exchanges.values()]
        all_tickers_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)
        
        exchange_tickers, aggregated_24h_volumes = {}, {}
        for i, ex_id in enumerate(exchanges.keys()):
            if isinstance(all_tickers_results[i], dict):
                exchange_tickers[ex_id] = all_tickers_results[i]
                for sym, ticker in all_tickers_results[i].items():
                    if sym.endswith("USDT:USDT"):
                        base = sym.split('/')[0]
                        vol_24h = ticker.get('quoteVolume')
                        if vol_24h: 
                            aggregated_24h_volumes[base] = aggregated_24h_volumes.get(base, 0) + float(vol_24h)

        print("🌐 Validating 24-Hour Volume...")
        cm_24h_volumes = fetch_coinmetrics_24h_volume(list(aggregated_24h_volumes.keys()))
        validated_24h_volumes = {}
        
        for sym, ex_24h_vol in aggregated_24h_volumes.items():
            if sym in MEGA_COINS: continue
            sources = [s for s in [cm_24h_volumes.get(sym, 0), ex_24h_vol] if s > 0]
            if sources and statistics.median(sources) >= MIN_24H_VOLUME_USD:
                validated_24h_volumes[sym] = statistics.median(sources)

        bitget_tickers = exchange_tickers.get('bitget', {})
        valid_coins = [sym for sym in validated_24h_volumes.keys() if f"{sym}/USDT:USDT" in bitget_tickers]
        print(f"📊 {len(valid_coins)} coins >$1M 24h volume. Filtering by 0.15% volatility...")

        sem_fast = asyncio.Semaphore(50)
        
        async def analyze_coin(sym):
            candles = await fetch_ccxt_candles(exchanges.get('bitget'), sym, sem_fast, limit=60)
            if not candles or len(candles) < 60: return None
            
            lifecycle = analyze_momentum_lifecycle(candles)
            if not lifecycle: return None
            
            record = deep_analyze_record(candles)
            
            # Score based on volatility and recent move
            score = lifecycle["avg_fluct"] * 100 + abs(record["current_move_pct"]) * 10
            
            return {
                "symbol": sym, 
                "direction": lifecycle["current_direction"], 
                "score": score,
                "record": record,
                "avg_fluct": lifecycle["avg_fluct"]
            }

        results = await asyncio.gather(*(analyze_coin(sym) for sym in valid_coins))
        winners = [r for r in results if r is not None]
        
        if not winners:
            print(f"❌ No valid volatile coins found. (Scan took {time.time() - start_time:.1f}s)")
            return None
            
        winners.sort(key=lambda x: x["score"], reverse=True)
        best = winners[0]
        
        # Deep Verification
        sym = best["symbol"]
        market_sym = f"{sym}/USDT:USDT"
        
        holding_exchanges = []
        for ex_id, tickers in exchange_tickers.items():
            if market_sym in tickers:
                vol_24h = tickers[market_sym].get('quoteVolume')
                if vol_24h and float(vol_24h) > 0: 
                    holding_exchanges.append((ex_id, float(vol_24h)))
                
        holding_exchanges.sort(key=lambda x: x[1], reverse=True)
        top_10_exchanges = holding_exchanges[:10]
        vol_captured_pct = (sum(x[1] for x in top_10_exchanges) / validated_24h_volumes[sym]) * 100
        
        if vol_captured_pct < 95.0:
            print("❌ Deep verification failed.")
            return None

        best_seq = (await fetch_ccxt_candles(exchanges.get('bitget'), sym, sem_fast, limit=15))[-15:]
        sequence = [{"o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": c[5]} for c in best_seq]
        
        best["entry_price"] = sequence[-1]["c"]
        best["sequence"] = sequence
        best["vol_captured"] = vol_captured_pct
        
        print(f"🔥 LIFECYCLE CANDIDATE: {best['symbol']} ({best['direction']}) | Score: {best['score']:.2f}")
        print(f"   📊 Volatility: {best['avg_fluct']}%")
        print(f"   📝 RECORD -> Start: {best['record']['start_type']} | Death: {best['record']['death_type']}")
        print(f"   📈 Prior Move: {best['record']['prior_move_pct']}% | Current Move: {best['record']['current_move_pct']}%")
        print(f"   Accuracy: {best['vol_captured']:.1f}% | Scan Time: {time.time() - start_time:.1f}s")
        return best

    finally:
        for ex in exchanges.values():
            try: await ex.close()
            except Exception: pass

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump(best_coin, f, indent=2)
        else: json.dump({}, f)
