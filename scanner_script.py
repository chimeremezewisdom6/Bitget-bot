import requests
import json
import os
import asyncio
import time
import statistics
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# THE 24-HOUR VOLUME RULE
MIN_24H_VOLUME_USD = 1_000_000  
MAX_FINALISTS = 10         

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
    """Fetches the trusted 24-HOUR volume from Coin Metrics."""
    base_url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    volumes = {}
    for i in range(0, min(len(assets), 150), 50):
        try:
            # frequency: 1d ensures we are getting exactly the 24-hour volume
            res = requests.get(base_url, params={"assets": ",".join([a.lower() for a in assets[i:i+50]]), "metrics": "volume_trusted_spot_usd_1d", "frequency": "1d", "page_size": 10000}, timeout=15)
            for entry in res.json().get("data", []):
                val = entry.get("volume_trusted_spot_usd_1d")
                if val is not None: volumes[entry["asset"].upper()] = float(val)
        except Exception: pass
        time.sleep(0.5)
    return volumes

def calculate_coin_score(candles):
    """
    Scores a coin based on exhaustion and reversal.
    No strict pass/fail. Just relative points.
    """
    if len(candles) < 30: return 0, None, 0
    
    start_30 = candles[-30][1]
    current_p = candles[-1][4]
    
    # 1. Trend Size (Base points)
    trend_move_pct = ((current_p - start_30) / start_30) * 100
    trend_score = abs(trend_move_pct) * 15  
    
    # 2. Volatility (10m avg)
    fluct = [((c[2] - c[3]) / c[3]) * 100 for c in candles[-10:]]
    avg_fluct = sum(fluct) / len(fluct)
    vol_score = avg_fluct * 100 
    
    # 3. Efficiency of the last candle
    c = candles[-1]
    open_p, high_p, low_p, close_p = c[1], c[2], c[3], c[4]
    total_range = high_p - low_p
    if total_range == 0: return 0, None, 0
    
    body_size = abs(close_p - open_p)
    body_ratio = body_size / total_range
    move_pct = (body_size / open_p) * 100
    eff_score = body_ratio * 50 
    
    # Determine expected direction based on 30m trend
    if trend_move_pct < 0:
        expected_dir = "LONG" 
    else:
        expected_dir = "SHORT" 
        
    # 4. The Exhaustion Reversal Bonus
    reversal_score = 0
    actual_dir = "LONG" if close_p > open_p else "SHORT"
    
    if actual_dir == expected_dir and move_pct >= 0.15 and body_ratio >= 0.65:
        if expected_dir == "LONG":
            lowest = min(c[3] for c in candles[-10:])
            reversal_pct = ((current_p - lowest) / lowest) * 100
        else:
            highest = max(c[2] for c in candles[-10:])
            reversal_pct = ((highest - current_p) / highest) * 100
            
        if reversal_pct <= 0.60: 
            reversal_score = 100 
        else:
            reversal_score = 20 
            
    total_score = trend_score + vol_score + eff_score + reversal_score
    trade_direction = "LONG" if close_p > open_p else "SHORT"
    
    return total_score, trade_direction, trend_move_pct

async def run_market_scan():
    start_time = time.time()
    exchanges = {}
    
    try:
        print("🔌 Initializing 15 Major Exchanges...")
        for ex_id in MAJOR_EXCHANGES:
            try:
                exchanges[ex_id] = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
                await exchanges[ex_id].load_markets()
            except Exception: pass

        print("📊 Fetching 24-Hour tickers globally...")
        ticker_tasks = [ex.fetch_tickers() for ex in exchanges.values()]
        all_tickers_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)
        
        exchange_tickers, aggregated_24h_volumes = {}, {}
        for i, ex_id in enumerate(exchanges.keys()):
            if isinstance(all_tickers_results[i], dict):
                exchange_tickers[ex_id] = all_tickers_results[i]
                for sym, ticker in all_tickers_results[i].items():
                    if sym.endswith("USDT:USDT"):
                        base = sym.split('/')[0]
                        # 'quoteVolume' is the exact 24-hour rolling volume
                        vol_24h = ticker.get('quoteVolume')
                        if vol_24h: 
                            aggregated_24h_volumes[base] = aggregated_24h_volumes.get(base, 0) + float(vol_24h)

        print("🌐 Cross-Validating 24-Hour Global Volume...")
        cm_24h_volumes = fetch_coinmetrics_24h_volume(list(aggregated_24h_volumes.keys()))
        validated_24h_volumes = {}
        
        for sym, ex_24h_vol in aggregated_24h_volumes.items():
            if sym in MEGA_COINS: continue
            sources = [s for s in [cm_24h_volumes.get(sym, 0), ex_24h_vol] if s > 0]
            
            # THE 24-HOUR VOLUME FILTER
            if sources and statistics.median(sources) >= MIN_24H_VOLUME_USD:
                validated_24h_volumes[sym] = statistics.median(sources)

        bitget_tickers = exchange_tickers.get('bitget', {})
        valid_coins = [sym for sym in validated_24h_volumes.keys() if f"{sym}/USDT:USDT" in bitget_tickers]
        print(f"📊 {len(valid_coins)} coins have >$1M in 24-Hour Volume. Scoring all of them...")

        sem_fast = asyncio.Semaphore(50)
        
        async def analyze_coin(sym):
            candles = await fetch_ccxt_candles(exchanges.get('bitget'), sym, sem_fast, limit=60)
            if not candles or len(candles) < 30: return None
            
            score, direction, trend = calculate_coin_score(candles)
            if direction:
                return {"symbol": sym, "direction": direction, "score": score, "trend": trend}
            return None

        results = await asyncio.gather(*(analyze_coin(sym) for sym in valid_coins))
        stage_1_winners = [r for r in results if r is not None]
        
        # Sort by highest score, no matter what
        stage_1_winners.sort(key=lambda x: x["score"], reverse=True)
        finalists = stage_1_winners[:MAX_FINALISTS]
        
        print(f"🎯 Top {len(finalists)} highest scoring coins selected for deep verification...")

        all_ranked = []
        
        for finalist in finalists:
            sym = finalist["symbol"]
            market_sym = f"{sym}/USDT:USDT"
            
            holding_exchanges = []
            for ex_id, tickers in exchange_tickers.items():
                if market_sym in tickers:
                    vol_24h = tickers[market_sym].get('quoteVolume')
                    if vol_24h and float(vol_24h) > 0: 
                        holding_exchanges.append((ex_id, float(vol_24h)))
                    
            if not holding_exchanges: continue
            
            holding_exchanges.sort(key=lambda x: x[1], reverse=True)
            top_10_exchanges = holding_exchanges[:10]
            
            # Deep verify: Ensure top 10 exchanges hold 95% of the 24h volume
            vol_captured_pct = (sum(x[1] for x in top_10_exchanges) / validated_24h_volumes[sym]) * 100
            if vol_captured_pct < 95.0: continue

            tasks = [fetch_ccxt_candles(exchanges[ex_id], sym, sem_fast, limit=60) for ex_id, _ in top_10_exchanges]
            valid_candles = [r for r in await asyncio.gather(*tasks) if r]
            
            total_deep_score = 0
            count = 0
            for ex_data in valid_candles:
                s, d, t = calculate_coin_score(ex_data)
                if d == finalist["direction"]:
                    total_deep_score += s
                    count += 1

            if count > 0:
                avg_score = total_deep_score / count
                best_seq = valid_candles[0][-15:] 
                sequence = [{"o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": c[5]} for c in best_seq]
                
                all_ranked.append({
                    "symbol": sym, 
                    "direction": finalist["direction"], 
                    "score": avg_score,
                    "trend_30m": finalist["trend"],
                    "entry_price": best_seq[-1][4],
                    "sequence": sequence,
                    "exchanges_used": count,
                    "vol_captured": vol_captured_pct
                })

        if not all_ranked: 
            print(f"❌ No valid candidates found at all. (Scan took {time.time() - start_time:.1f}s)")
            return None
            
        all_ranked.sort(key=lambda x: x['score'], reverse=True)
        best = all_ranked[0]
        
        print(f"🔥 BEST AVAILABLE CANDIDATE: {best['symbol']} ({best['direction']}) | Score: {best['score']:.2f}")
        print(f"   30m Trend: {best['trend_30m']:.2f}% | 24h Vol Accuracy: {best['vol_captured']:.1f}%")
        print(f"   Total Scan Time: {time.time() - start_time:.1f}s")
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
