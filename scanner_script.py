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

def build_momentum_timeline(candles, duration):
    """Extracts the minute-by-minute data for the duration of the run."""
    if duration == 0: return []
    
    run_candles = candles[-duration:]
    timeline = []
    
    for i, c in enumerate(run_candles):
        open_p, high_p, low_p, close_p, vol = c[1], c[2], c[3], c[4], c[5]
        move_pct = ((close_p - open_p) / open_p) * 100
        total_range = high_p - low_p
        body_ratio = abs(close_p - open_p) / total_range if total_range > 0 else 0
        
        timeline.append({
            "minute": i + 1,
            "move_pct": round(move_pct, 3),
            "body_ratio": round(body_ratio, 2),
            "volume": round(vol, 2)
        })
        
    return timeline

def calculate_momentum_duration(candles):
    if len(candles) < 20: return 0, None, 0
    
    fluct = [((c[2] - c[3]) / c[3]) * 100 for c in candles[-10:]]
    avg_fluct = sum(fluct) / len(fluct)
    if avg_fluct < MIN_AVG_VOLATILITY:
        return 0, None, avg_fluct
        
    current_dir = None
    duration = 0
    
    for c in reversed(candles):
        is_green = c[4] > c[1]
        is_red = c[4] < c[1]
        
        if current_dir is None:
            if is_green: current_dir = "LONG"
            elif is_red: current_dir = "SHORT"
            else: continue
            
        if current_dir == "LONG" and is_green:
            duration += 1
        elif current_dir == "SHORT" and is_red:
            duration += 1
        else:
            break 
            
    return duration, current_dir, round(avg_fluct, 3)

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
        print(f"📊 {len(valid_coins)} coins >$1M 24h volume. Measuring Momentum Duration...")

        sem_fast = asyncio.Semaphore(50)
        
        async def analyze_coin(sym):
            candles = await fetch_ccxt_candles(exchanges.get('bitget'), sym, sem_fast, limit=60)
            if not candles or len(candles) < 20: return None
            
            duration, direction, avg_fluct = calculate_momentum_duration(candles)
            if duration >= 3 and direction:
                return {
                    "symbol": sym, 
                    "direction": direction, 
                    "duration": duration,
                    "avg_fluct": avg_fluct
                }
            return None

        results = await asyncio.gather(*(analyze_coin(sym) for sym in valid_coins))
        winners = [r for r in results if r is not None]
        
        if not winners:
            print(f"❌ No sustained momentum found. (Scan took {time.time() - start_time:.1f}s)")
            return None
            
        winners.sort(key=lambda x: (x["duration"], x["avg_fluct"]), reverse=True)
        best = winners[0]
        
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

        best_candles = await fetch_ccxt_candles(exchanges.get('bitget'), sym, sem_fast, limit=60)
        
        # BUILD THE MINUTE-BY-MINUTE TIMELINE
        timeline = build_momentum_timeline(best_candles, best["duration"])
        
        best["timeline"] = timeline
        best["vol_captured"] = vol_captured_pct
        
        print(f"🔥 LONGEST MOMENTUM: {best['symbol']} ({best['direction']}) | Duration: {best['duration']} MINUTES")
        print(f"   📊 Volatility: {best['avg_fluct']}%")
        
        # PRINT THE FULL TIMELINE IN THE GITHUB LOGS
        print(f"   ⏱️ MOMENTUM TIMELINE (What happened during these {best['duration']} minutes):")
        for t in timeline:
            print(f"      Min {t['minute']}: Move={t['move_pct']:+.2f}% | Body Ratio={t['body_ratio']} | Vol={t['volume']}")
            
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
