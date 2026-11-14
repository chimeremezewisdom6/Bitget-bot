import requests
import json
import os
import asyncio
import time
import statistics
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# THE RULES
MIN_PRICE_MOVE = 0.22
MAX_WINNING_VOLUME = 0.40
MIN_LOSING_VOLUME = 0.60
MIN_AVG_FLUCTUATION = 0.15

# THE 15 MAJOR EXCHANGES
MAJOR_EXCHANGES = [
    'binance', 'okx', 'bybit', 'bitget', 'kucoin', 
    'gate', 'mexc', 'htx', 'bingx', 'crypto', 
    'coinbase', 'kraken', 'bitfinex', 'bitmex', 'deribit'
]

CRYPTOCOMPARE_KEY = os.environ.get("CRYPTOCOMPARE_KEY", "")

async def fetch_ccxt_candles(exchange, sym, sem):
    async with sem:
        try:
            market_sym = f"{sym}/USDT:USDT"
            if not exchange.has.get('fetchOHLCV'): return None
            ohlcv = await exchange.fetch_ohlcv(market_sym, timeframe='1m', limit=15)
            if not ohlcv or len(ohlcv) < 10: return None
            return ohlcv
        except Exception:
            return None

def fetch_coinmetrics_volume(assets):
    print("  📊 Fetching Trusted Volume from Coin Metrics...")
    base_url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    volumes = {}
    for i in range(0, min(len(assets), 100), 50):
        batch = assets[i:i+50]
        params = {
            "assets": ",".join([a.lower() for a in batch]),
            "metrics": "volume_trusted_spot_usd_1d",
            "frequency": "1d",
            "page_size": 10000,
        }
        try:
            res = requests.get(base_url, params=params, timeout=15)
            for entry in res.json().get("data", []):
                asset = entry["asset"].upper()
                try: volumes[asset] = float(entry["volume_trusted_spot_usd_1d"])
                except (KeyError, ValueError): pass
        except Exception: pass
        time.sleep(0.5)
    return volumes

def fetch_cryptocompare_volume(assets):
    if not CRYPTOCOMPARE_KEY: return {}
    print("  📊 Fetching Aggregated Volume from CryptoCompare...")
    volumes = {}
    url = "https://min-api.cryptocompare.com/data/top/totalvolfull"
    for page in range(0, 5):
        try:
            params = {"limit": 100, "page": page, "tsym": "USD", "api_key": CRYPTOCOMPARE_KEY}
            res = requests.get(url, params=params, timeout=15)
            for entry in res.json().get("Data", []):
                sym = entry["CoinInfo"]["Name"].upper()
                try:
                    vol = float(entry["RAW"]["USD"].get("VOLUME24HOURTO", 0))
                    if vol > 0: volumes[sym] = vol
                except (KeyError, ValueError): pass
            time.sleep(0.2)
        except Exception: break
    return volumes

async def run_market_scan():
    exchanges = {}
    try:
        print("🔌 Initializing 15 Major Exchanges...")
        for ex_id in MAJOR_EXCHANGES:
            try:
                exchanges[ex_id] = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
                await exchanges[ex_id].load_markets()
            except Exception: pass

        print("📊 Fetching 24h tickers from all exchanges concurrently...")
        ticker_tasks = [ex.fetch_tickers() for ex in exchanges.values()]
        all_tickers_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)
        
        exchange_tickers = {}
        exchange_volumes = {}
        
        for i, ex_id in enumerate(exchanges.keys()):
            if isinstance(all_tickers_results[i], dict):
                exchange_tickers[ex_id] = all_tickers_results[i]
                for sym, ticker in all_tickers_results[i].items():
                    if sym.endswith("USDT:USDT"):
                        base = sym.split('/')[0]
                        vol = ticker.get('quoteVolume', 0) or 0
                        exchange_volumes[base] = exchange_volumes.get(base, 0) + vol

        print("🌐 Cross-Validating Global Volume...")
        all_assets = list(exchange_volumes.keys())
        cm_volumes = fetch_coinmetrics_volume(all_assets)
        cc_volumes = fetch_cryptocompare_volume(all_assets)
        
        validated_global_volumes = {}
        
        for sym in all_assets:
            if sym in MEGA_COINS: continue
            sources = []
            if sym in cm_volumes and cm_volumes[sym] > 0: sources.append(cm_volumes[sym])
            if sym in cc_volumes and cc_volumes[sym] > 0: sources.append(cc_volumes[sym])
            if sym in exchange_volumes and exchange_volumes[sym] > 0: sources.append(exchange_volumes[sym])
            
            if not sources: continue
            consensus = statistics.median(sources)
            if consensus >= 1_000_000:
                validated_global_volumes[sym] = consensus

        print(f"✅ Found {len(validated_global_volumes)} coins with >$1M Cross-Validated Volume.")

        bitget_tickers = exchange_tickers.get('bitget', {})
        valid_coins = [sym for sym in validated_global_volumes.keys() if f"{sym}/USDT:USDT" in bitget_tickers]
        print(f"📊 {len(valid_coins)} tradable on Bitget.")

        if not valid_coins: return None

        print("⚡ Stage 1: Fast filter for 0.15% fluctuation on Bitget...")
        sem_fast = asyncio.Semaphore(50)
        bitget_ex = exchanges.get('bitget')
        
        async def check_fluctuation(sym):
            candles = await fetch_ccxt_candles(bitget_ex, sym, sem_fast)
            if not candles: return None
            last_10 = candles[-10:]
            fluct = [((c[2] - c[3]) / c[3]) * 100 for c in last_10]
            if (sum(fluct) / len(fluct)) >= MIN_AVG_FLUCTUATION:
                return sym
            return None

        fast_results = await asyncio.gather(*(check_fluctuation(sym) for sym in valid_coins))
        candidates = [s for s in fast_results if s is not None]
        print(f"🎯 {len(candidates)} coins passed the 0.15% fluctuation filter.")

        if not candidates: return None

        print("🔬 Stage 2: Verifying 95% volume coverage & ranking the best candidate...")
        sem_agg = asyncio.Semaphore(20)
        all_ranked_candidates = []

        for sym in candidates:
            market_sym = f"{sym}/USDT:USDT"
            global_vol = validated_global_volumes[sym]
            
            holding_exchanges = []
            for ex_id, tickers in exchange_tickers.items():
                if market_sym in tickers:
                    vol = tickers[market_sym].get('quoteVolume', 0) or 0
                    if vol > 0: holding_exchanges.append((ex_id, vol))
                        
            if not holding_exchanges: continue
            
            holding_exchanges.sort(key=lambda x: x[1], reverse=True)
            top_10_exchanges = holding_exchanges[:10]
            
            combined_24h_vol = sum(x[1] for x in top_10_exchanges)
            vol_captured_pct = (combined_24h_vol / global_vol) * 100
            
            if vol_captured_pct < 95.0: continue
                
            tasks = [fetch_ccxt_candles(exchanges[ex_id], sym, sem_agg) for ex_id, _ in top_10_exchanges]
            candle_results = await asyncio.gather(*tasks)
            
            valid_candles = [r for r in candle_results if r is not None]
            if not valid_candles: continue
            
            sum_green_pct = 0
            sum_red_pct = 0
            sum_price_change = 0
            sum_fluct = 0
            count = 0
            
            for ex_data in valid_candles:
                last_10 = ex_data[-10:]
                green = sum(c[5] for c in last_10 if c[4] > c[1])
                red = sum(c[5] for c in last_10 if c[4] < c[1])
                total_vol = green + red
                
                if total_vol == 0: continue
                
                sum_green_pct += (green / total_vol)
                sum_red_pct += (red / total_vol)
                
                open_price = last_10[0][1]
                close_price = last_10[-1][4]
                sum_price_change += ((close_price - open_price) / open_price) * 100
                
                fluct = [((c[2] - c[3]) / c[3]) * 100 for c in last_10]
                sum_fluct += sum(fluct) / len(fluct)
                count += 1
                
            if count == 0: continue
            
            avg_green_pct = sum_green_pct / count
            avg_red_pct = sum_red_pct / count
            avg_price_change = sum_price_change / count
            avg_fluct = sum_fluct / count

            if avg_price_change > 0:
                direction = "LONG"
                win_vol = avg_green_pct
                lose_vol = avg_red_pct
            else:
                direction = "SHORT"
                win_vol = avg_red_pct
                lose_vol = avg_green_pct
                
            score = abs(avg_price_change) / (win_vol + 0.01) 
            
            if win_vol > 0.50: score = score * 0.2
            if win_vol < 0.35: score = score * 3.0
                
            score += (avg_fluct * 0.1)
            
            # Extract the closing price of the first valid exchange for entry_price
            entry_price = valid_candles[0][-1][4] 

            all_ranked_candidates.append({
                "symbol": sym, "direction": direction, "score": score,
                "move": avg_price_change, "win_vol": win_vol, "lose_vol": lose_vol,
                "exchanges_used": count, "vol_captured": vol_captured_pct,
                "entry_price": entry_price
            })

        if not all_ranked_candidates:
            print("❌ No valid candidates found after filtering.")
            return None
            
        all_ranked_candidates.sort(key=lambda x: x['score'], reverse=True)
        best_winner = all_ranked_candidates[0]

        print(f"🔥 BEST CANDIDATE: {best_winner['symbol']} ({best_winner['direction']})")
        print(f"   Opening Price: {best_winner['entry_price']:.6f}")
        print(f"   Price Move: {best_winner['move']:+.2f}%")
        print(f"   Opening Volumes: Winning {best_winner['win_vol']*100:.1f}% | Losing {best_winner['lose_vol']*100:.1f}%")
        print(f"   Aggregated across {best_winner['exchanges_used']} exchanges.")
        print(f"   VOLUME ACCURACY: {best_winner['vol_captured']:.1f}% (Cross-Validated)")
        return best_winner

    finally:
        for ex in exchanges.values():
            try: await ex.close()
            except Exception: pass

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump(best_coin, f, indent=2)
        else: json.dump({}, f)
