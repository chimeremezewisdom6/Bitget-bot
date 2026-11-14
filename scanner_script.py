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

# Optional: Add your CryptoCompare key here. If not provided, script relies on Coin Metrics + Exchanges.
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

# =====================================================================
# MULTI-SOURCE VOLUME VALIDATOR
# =====================================================================
def fetch_coinmetrics_volume(assets):
    """Fetches Trusted Volume from Coin Metrics (Institutional Grade, Keyless)."""
    print("  📊 Fetching Trusted Volume from Coin Metrics...")
    base_url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    volumes = {}
    # Batch requests to avoid URI too long
    for i in range(0, len(assets), 50):
        batch = assets[i:i+50]
        params = {
            "assets": ",".join([a.lower() for a in batch]),
            "metrics": "volume_trusted_spot_usd_1d",
            "frequency": "1d",
            "page_size": 10000,
        }
        try:
            res = requests.get(base_url, params=params, timeout=20)
            for entry in res.json().get("data", []):
                asset = entry["asset"].upper()
                try: volumes[asset] = float(entry["volume_trusted_spot_usd_1d"])
                except (KeyError, ValueError): pass
        except Exception: pass
        time.sleep(0.7) # Coin Metrics free tier limit
    return volumes

def fetch_cryptocompare_volume(assets):
    """Fetches Aggregated Volume from CryptoCompare (if key provided)."""
    if not CRYPTOCOMPARE_KEY: return {}
    print("  📊 Fetching Aggregated Volume from CryptoCompare...")
    volumes = {}
    # CryptoCompare top list only gives top 100 per request. We do multiple pages.
    url = "https://min-api.cryptocompare.com/data/top/totalvolfull"
    for page in range(0, 10):
        try:
            params = {"limit": 100, "page": page, "tsym": "USD", "api_key": CRYPTOCOMPARE_KEY}
            res = requests.get(url, params=params, timeout=20)
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
    # 1. Initialize Exchanges
    print("🔌 Initializing 15 Major Exchanges...")
    exchanges = {}
    for ex_id in MAJOR_EXCHANGES:
        try:
            exchanges[ex_id] = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
            await exchanges[ex_id].load_markets()
        except Exception: pass

    # 2. Fetch Exchange Tickers (This is our 3rd source of truth)
    print("📊 Fetching 24h tickers from all exchanges concurrently...")
    ticker_tasks = [ex.fetch_tickers() for ex in exchanges.values()]
    all_tickers_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)
    
    exchange_tickers = {}
    exchange_volumes = {} # Sum of all 15 exchanges per coin
    
    for i, ex_id in enumerate(exchanges.keys()):
        if isinstance(all_tickers_results[i], dict):
            exchange_tickers[ex_id] = all_tickers_results[i]
            for sym, ticker in all_tickers_results[i].items():
                if sym.endswith("USDT:USDT"):
                    base = sym.split('/')[0]
                    vol = ticker.get('quoteVolume', 0) or 0
                    exchange_volumes[base] = exchange_volumes.get(base, 0) + vol

    # 3. Cross-Validate Global Volume
    print("🌐 Cross-Validating Global Volume across multiple platforms...")
    # Get a master list of assets from the exchanges we track
    all_assets = list(exchange_volumes.keys())
    
    cm_volumes = fetch_coinmetrics_volume(all_assets)
    cc_volumes = fetch_cryptocompare_volume(all_assets)
    
    validated_global_volumes = {}
    
    for sym in all_assets:
        if sym in MEGA_COINS: continue
        
        sources = []
        if sym in cm_volumes: sources.append(cm_volumes[sym])
        if sym in cc_volumes: sources.append(cc_volumes[sym])
        if sym in exchange_volumes: sources.append(exchange_volumes[sym])
        
        # Need at least 2 sources to validate, otherwise skip to avoid bad data
        if len(sources) < 2: continue
        
        # If one source is a massive outlier (e.g., 50% higher than the median), drop it
        median_vol = statistics.median(sources)
        clean_sources = [v for v in sources if v < (median_vol * 1.5)]
        
        consensus = sum(clean_sources) / len(clean_sources)
        
        if consensus >= 1_000_000:
            validated_global_volumes[sym] = consensus

    print(f"✅ Found {len(validated_global_volumes)} coins with >$1M Cross-Validated Volume.")

    # 4. Filter by Bitget Tradability
    bitget_tickers = exchange_tickers.get('bitget', {})
    valid_coins = [sym for sym in validated_global_volumes.keys() if f"{sym}/USDT:USDT" in bitget_tickers]
    print(f"📊 {len(valid_coins)} tradable on Bitget.")

    # 5. Stage 1: Fast Fluctuation Filter on Bitget (0.15%+)
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

    # 6. Stage 2: Top 10 Exchange Verification & Ranked Averaging
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
                if vol > 0:
                    holding_exchanges.append((ex_id, vol))
                    
        if not holding_exchanges: continue
        
        # Take the Top 10 exchanges holding this coin
        holding_exchanges.sort(key=lambda x: x[1], reverse=True)
        top_10_exchanges = holding_exchanges[:10]
        
        # Calculate how much of the global volume these 10 exchanges hold
        combined_24h_vol = sum(x[1] for x in top_10_exchanges)
        vol_captured_pct = (combined_24h_vol / global_vol) * 100
        
        # 95% ACCURACY CHECK
        if vol_captured_pct < 95.0:
            continue
            
        # Fetch 10m candles from these specific Top 10 exchanges
        tasks = [fetch_ccxt_candles(exchanges[ex_id], sym, sem_agg) for ex_id, _ in top_10_exchanges]
        candle_results = await asyncio.gather(*tasks)
        
        valid_candles = [r for r in candle_results if r is not None]
        if not valid_candles: continue
        
        # --- THE GENIUS AVERAGING METHOD (Sum / 10) ---
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

        # --- THE STRICT DAVID RANKING LOGIC ---
        if avg_price_change > 0:
            direction = "LONG"
            win_vol = avg_green_pct
            lose_vol = avg_red_pct
        else:
            direction = "SHORT"
            win_vol = avg_red_pct
            lose_vol = avg_green_pct
            
        # Base score: Price move divided by winning volume
        score = abs(avg_price_change) / (win_vol + 0.01) 
        
        # PENALTY: If winning volume > 50%, slash score by 80% (Ignore Goliaths)
        if win_vol > 0.50:
            score = score * 0.2
            
        # BONUS: If winning volume < 35% (Extreme David), triple the score.
        if win_vol < 0.35:
            score = score * 3.0
            
        # Add a small bonus for high raw fluctuation
        score += (avg_fluct * 0.1)

        all_ranked_candidates.append({
            "symbol": sym, 
            "direction": direction, 
            "score": score,
            "move": avg_price_change,
            "win_vol": win_vol,
            "lose_vol": lose_vol,
            "exchanges_used": count,
            "vol_captured": vol_captured_pct
        })

    # Cleanup
    for ex in exchanges.values():
        await ex.close()

    if not all_ranked_candidates:
        print("❌ No valid candidates found after filtering.")
        return None
        
    all_ranked_candidates.sort(key=lambda x: x['score'], reverse=True)
    best_winner = all_ranked_candidates[0]

    print(f"🔥 BEST CANDIDATE: {best_winner['symbol']} ({best_winner['direction']})")
    print(f"   Price Move: {best_winner['move']:+.2f}%")
    print(f"   Winning Side Volume: {best_winner['win_vol']*100:.1f}% (Losing Side: {best_winner['lose_vol']*100:.1f}%)")
    print(f"   Aggregated across {best_winner['exchanges_used']} exchanges.")
    print(f"   VOLUME ACCURACY: {best_winner['vol_captured']:.1f}% (Cross-Validated Global Volume)")
    return best_winner

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin["symbol"], "direction": best_coin["direction"], "score": best_coin["score"]}, f, indent=2)
        else: json.dump({}, f)
