import requests
import json
import os
import asyncio
import time
import statistics
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}
MIN_PRICE_MOVE = 0.22
MIN_AVG_FLUCTUATION = 0.15

MAJOR_EXCHANGES = ['binance', 'okx', 'bybit', 'bitget', 'kucoin', 'gate', 'mexc', 'htx', 'bingx', 'crypto', 'coinbase', 'kraken']

async def fetch_ccxt_candles(exchange, sym, sem):
    async with sem:
        try:
            market_sym = f"{sym}/USDT:USDT"
            if not exchange.has.get('fetchOHLCV'): return None
            ohlcv = await exchange.fetch_ohlcv(market_sym, timeframe='1m', limit=15)
            if not ohlcv or len(ohlcv) < 10: return None
            
            # SAFEGUARD: Ensure all candle data is valid floats
            clean_candles = []
            for c in ohlcv:
                if c[1] is None or c[2] is None or c[3] is None or c[4] is None or c[5] is None:
                    continue
                clean_candles.append([int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])])
                
            return clean_candles if len(clean_candles) >= 10 else None
        except Exception:
            return None

def fetch_coinmetrics_volume(assets):
    base_url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    volumes = {}
    for i in range(0, min(len(assets), 100), 50):
        try:
            res = requests.get(base_url, params={"assets": ",".join([a.lower() for a in assets[i:i+50]]), "metrics": "volume_trusted_spot_usd_1d", "frequency": "1d", "page_size": 10000}, timeout=15)
            for entry in res.json().get("data", []):
                val = entry.get("volume_trusted_spot_usd_1d")
                if val is not None:
                    volumes[entry["asset"].upper()] = float(val)
        except Exception: pass
        time.sleep(0.5)
    return volumes

async def run_market_scan():
    exchanges = {}
    try:
        for ex_id in MAJOR_EXCHANGES:
            try:
                exchanges[ex_id] = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
                await exchanges[ex_id].load_markets()
            except Exception: pass

        ticker_tasks = [ex.fetch_tickers() for ex in exchanges.values()]
        all_tickers_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)
        
        exchange_tickers, exchange_volumes = {}, {}
        for i, ex_id in enumerate(exchanges.keys()):
            if isinstance(all_tickers_results[i], dict):
                exchange_tickers[ex_id] = all_tickers_results[i]
                for sym, ticker in all_tickers_results[i].items():
                    if sym.endswith("USDT:USDT"):
                        base = sym.split('/')[0]
                        # SAFEGUARD: Handle None volumes
                        vol = ticker.get('quoteVolume')
                        vol = float(vol) if vol is not None else 0.0
                        exchange_volumes[base] = exchange_volumes.get(base, 0) + vol

        cm_volumes = fetch_coinmetrics_volume(list(exchange_volumes.keys()))
        validated_global_volumes = {}
        
        for sym, ex_vol in exchange_volumes.items():
            if sym in MEGA_COINS: continue
            sources = [cm_volumes.get(sym, 0), ex_vol]
            sources = [s for s in sources if s > 0]
            if sources and statistics.median(sources) >= 1_000_000:
                validated_global_volumes[sym] = statistics.median(sources)

        bitget_tickers = exchange_tickers.get('bitget', {})
        valid_coins = [sym for sym in validated_global_volumes.keys() if f"{sym}/USDT:USDT" in bitget_tickers]
        
        sem_fast = asyncio.Semaphore(50)
        sem_agg = asyncio.Semaphore(20)
        
        async def check_fluctuation(sym):
            candles = await fetch_ccxt_candles(exchanges.get('bitget'), sym, sem_fast)
            if not candles: return None
            fluct = [((c[2] - c[3]) / c[3]) * 100 for c in candles[-10:]]
            return sym if (sum(fluct) / len(fluct)) >= MIN_AVG_FLUCTUATION else None

        candidates = [s for s in await asyncio.gather(*(check_fluctuation(sym) for sym in valid_coins)) if s]
        all_ranked_candidates = []

        for sym in candidates:
            market_sym = f"{sym}/USDT:USDT"
            holding_exchanges = []
            
            for ex_id, tickers in exchange_tickers.items():
                if market_sym in tickers:
                    # SAFEGUARD: Handle None volumes safely
                    vol = tickers[market_sym].get('quoteVolume')
                    vol = float(vol) if vol is not None else 0.0
                    if vol > 0:
                        holding_exchanges.append((ex_id, vol))
                        
            if not holding_exchanges: continue
            
            holding_exchanges.sort(key=lambda x: x[1], reverse=True)
            top_10_exchanges = holding_exchanges[:10]
            vol_captured_pct = (sum(x[1] for x in top_10_exchanges) / validated_global_volumes[sym]) * 100
            
            if vol_captured_pct < 95.0: continue
                
            tasks = [fetch_ccxt_candles(exchanges[ex_id], sym, sem_agg) for ex_id, _ in top_10_exchanges]
            valid_candles = [r for r in await asyncio.gather(*tasks) if r]
            if not valid_candles: continue
            
            sum_green, sum_red, sum_price, sum_fluct = 0, 0, 0, 0
            count = len(valid_candles)
            
            for ex_data in valid_candles:
                last_10 = ex_data[-10:]
                green = sum(c[5] for c in last_10 if c[4] > c[1])
                red = sum(c[5] for c in last_10 if c[4] < c[1])
                if green + red == 0: continue
                sum_green += (green / (green + red))
                sum_red += (red / (green + red))
                sum_price += ((last_10[-1][4] - last_10[0][1]) / last_10[0][1]) * 100
                sum_fluct += sum([((c[2] - c[3]) / c[3]) * 100 for c in last_10]) / 10

            avg_green, avg_red = sum_green / count, sum_red / count
            avg_price, avg_fluct = sum_price / count, sum_fluct / count
            
            direction = "LONG" if avg_price > 0 else "SHORT"
            win_vol = avg_green if direction == "LONG" else avg_red
            lose_vol = avg_red if direction == "LONG" else avg_green
            
            score = abs(avg_price) / (win_vol + 0.01)
            if win_vol > 0.50: score *= 0.2
            if win_vol < 0.35: score *= 3.0
                
            # Extract the raw 10m sequence from the highest volume exchange
            best_candles = valid_candles[0][-10:]
            sequence = [{"o": c[1], "h": c[2], "l": c[3], "c": c[4], "v": c[5]} for c in best_candles]

            all_ranked_candidates.append({
                "symbol": sym, "direction": direction, "score": score,
                "move": avg_price, "win_vol": win_vol, "lose_vol": lose_vol,
                "vol_captured": vol_captured_pct, "entry_price": best_candles[-1][4],
                "sequence": sequence
            })

        if not all_ranked_candidates: 
            print("❌ No valid candidates found.")
            return None
            
        all_ranked_candidates.sort(key=lambda x: x['score'], reverse=True)
        best = all_ranked_candidates[0]
        print(f"🔥 BEST CANDIDATE: {best['symbol']} ({best['direction']}) | Score: {best['score']:.2f}")
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
