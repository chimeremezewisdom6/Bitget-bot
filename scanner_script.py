import requests
import json
import os
import asyncio
import time
import statistics
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# THE WICK HUNTER RULES
MIN_PRICE_MOVE = 0.30      
MIN_BODY_RATIO = 0.70      
MIN_AVG_FLUCTUATION = 0.15 # 0.15% minimum per minute volatility
MAX_FINALISTS = 10         # Deep verify the top 10 that pass Stage 1

MAJOR_EXCHANGES = ['binance', 'okx', 'bybit', 'bitget', 'kucoin', 'gate', 'mexc', 'htx', 'bingx', 'crypto', 'coinbase', 'kraken', 'bitfinex', 'bitmex', 'deribit']

async def fetch_ccxt_candles(exchange, sym, sem):
    async with sem:
        try:
            market_sym = f"{sym}/USDT:USDT"
            if not exchange.has.get('fetchOHLCV'): return None
            ohlcv = await exchange.fetch_ohlcv(market_sym, timeframe='1m', limit=15)
            if not ohlcv or len(ohlcv) < 10: return None
            
            clean_candles = []
            for c in ohlcv:
                if None in c[1:6]: continue
                clean_candles.append([int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])])
            return clean_candles if len(clean_candles) >= 10 else None
        except Exception:
            return None

def fetch_coinmetrics_volume(assets):
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

def check_volatility(candles):
    if len(candles) < 10: return 0.0
    fluct = [((c[2] - c[3]) / c[3]) * 100 for c in candles[-10:]]
    return sum(fluct) / len(fluct)

def check_efficiency_candle(candles):
    last_3 = candles[-3:]
    best_score = 0
    direction = None
    
    for c in last_3:
        open_p, high_p, low_p, close_p = c[1], c[2], c[3], c[4]
        total_range = high_p - low_p
        if total_range == 0: continue
        
        body_size = abs(close_p - open_p)
        body_ratio = body_size / total_range
        move_pct = (body_size / open_p) * 100
        
        if move_pct >= MIN_PRICE_MOVE and body_ratio >= MIN_BODY_RATIO:
            score = move_pct * body_ratio
            if score > best_score:
                best_score = score
                direction = "LONG" if close_p > open_p else "SHORT"
                
    return best_score, direction

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

        print("📊 Fetching 24h tickers globally...")
        ticker_tasks = [ex.fetch_tickers() for ex in exchanges.values()]
        all_tickers_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)
        
        exchange_tickers, exchange_volumes = {}, {}
        for i, ex_id in enumerate(exchanges.keys()):
            if isinstance(all_tickers_results[i], dict):
                exchange_tickers[ex_id] = all_tickers_results[i]
                for sym, ticker in all_tickers_results[i].items():
                    if sym.endswith("USDT:USDT"):
                        base = sym.split('/')[0]
                        vol = ticker.get('quoteVolume')
                        if vol: exchange_volumes[base] = exchange_volumes.get(base, 0) + float(vol)

        print("🌐 Cross-Validating Global Volume...")
        cm_volumes = fetch_coinmetrics_volume(list(exchange_volumes.keys()))
        validated_global_volumes = {}
        
        for sym, ex_vol in exchange_volumes.items():
            if sym in MEGA_COINS: continue
            sources = [s for s in [cm_volumes.get(sym, 0), ex_vol] if s > 0]
            if sources and statistics.median(sources) >= 1_000_000:
                validated_global_volumes[sym] = statistics.median(sources)

        bitget_tickers = exchange_tickers.get('bitget', {})
        valid_coins = [sym for sym in validated_global_volumes.keys() if f"{sym}/USDT:USDT" in bitget_tickers]
        print(f"📊 {len(valid_coins)} coins >$1M volume found. Checking volatility for ALL of them...")

        # --- STAGE 1: CHECK VOLATILITY & EFFICIENCY FOR EVERY COIN ---
        sem_fast = asyncio.Semaphore(50)
        
        async def analyze_coin(sym):
            candles = await fetch_ccxt_candles(exchanges.get('bitget'), sym, sem_fast)
            if not candles: return None
            
            avg_fluct = check_volatility(candles)
            if avg_fluct < MIN_AVG_FLUCTUATION: return None
            
            score, direction = check_efficiency_candle(candles)
            if direction:
                return {"symbol": sym, "direction": direction, "score": score, "fluct": avg_fluct}
            return None

        results = await asyncio.gather(*(analyze_coin(sym) for sym in valid_coins))
        stage_1_winners = [r for r in results if r is not None]
        
        stage_1_winners.sort(key=lambda x: x["score"], reverse=True)
        finalists = stage_1_winners[:MAX_FINALISTS]
        
        print(f"🎯 {len(stage_1_winners)} coins passed Stage 1. Deep verifying top {len(finalists)}...")

        # --- STAGE 2: DEEP VERIFICATION ---
        all_ranked = []
        
        for finalist in finalists:
            sym = finalist["symbol"]
            market_sym = f"{sym}/USDT:USDT"
            
            holding_exchanges = []
            for ex_id, tickers in exchange_tickers.items():
                if market_sym in tickers:
                    vol = tickers[market_sym].get('quoteVolume')
                    if vol and float(vol) > 0: holding_exchanges.append((ex_id, float(vol)))
                    
            if not holding_exchanges: continue
            
            holding_exchanges.sort(key=lambda x: x[1], reverse=True)
            top_10_exchanges = holding_exchanges[:10]
            
            vol_captured_pct = (sum(x[1] for x in top_10_exchanges) / validated_global_volumes[sym]) * 100
            if vol_captured_pct < 95.0: continue

            tasks = [fetch_ccxt_candles(exchanges[ex_id], sym, sem_fast) for ex_id, _ in top_10_exchanges]
            valid_candles = [r for r in await asyncio.gather(*tasks) if r]
            
            sum_body_ratio, sum_move_pct, valid_sequences = 0, 0, 0
            for ex_data in valid_candles:
                s, d = check_efficiency_candle(ex_data)
                if d == finalist["direction"]:
                    c = ex_data[-1]
                    tr = c[2] - c[3]
                    br = abs(c[4] - c[1]) / tr if tr > 0 else 0
                    mp = (abs(c[4] - c[1]) / c[1]) * 100
                    sum_body_ratio += br
                    sum_move_pct += mp
                    valid_sequences += 1

            if valid_sequences > 0:
                avg_body = sum_body_ratio / valid_sequences
                avg_move = sum_move_pct / valid_sequences
                
                if avg_body >= MIN_BODY_RATIO:
                    best_seq = valid_candles[0][-10:]
                    sequence = [{"o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": c[5]} for c in best_seq]
                    
                    all_ranked.append({
                        "symbol": sym, 
                        "direction": finalist["direction"], 
                        "score": avg_move * avg_body,
                        "entry_price": best_seq[-1][4],
                        "sequence": sequence,
                        "exchanges_used": len(valid_candles),
                        "vol_captured": vol_captured_pct
                    })

        if not all_ranked: 
            print(f"❌ No True Efficiency Candles found. (Scan took {time.time() - start_time:.1f}s)")
            return None
            
        all_ranked.sort(key=lambda x: x['score'], reverse=True)
        best = all_ranked[0]
        
        print(f"🔥 TRUE BEST CANDIDATE: {best['symbol']} ({best['direction']}) | Score: {best['score']:.2f}")
        print(f"   Aggregated across {best['exchanges_used']} exchanges | Accuracy: {best['vol_captured']:.1f}%")
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
