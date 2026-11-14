import requests
import json
import os
import asyncio
import time
import ccxt.async_support as ccxt_async

MEGA_COINS = {'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'TON', 'DOGE', 'ADA', 'SHIB', 'AVAX', 'TRX', 'DOT', 'BCH', 'LINK', 'NEAR', 'MATIC', 'LTC'}

# We only require a basic fluctuation to filter out dead coins
MIN_AVG_FLUCTUATION = 0.15

# THE 15 MAJOR EXCHANGES
MAJOR_EXCHANGES = [
    'binance', 'okx', 'bybit', 'bitget', 'kucoin', 
    'gate', 'mexc', 'htx', 'bingx', 'crypto', 
    'coinbase', 'kraken', 'bitfinex', 'bitmex', 'deribit'
]

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

async def get_global_universe():
    print("🌐 Fetching Top 3000 coins from CoinLore...")
    all_coins = {}
    start = 0
    limit = 100
    
    try:
        for page in range(30):
            url = f"https://api.coinlore.net/api/tickers/?start={start}&limit={limit}"
            res = requests.get(url, timeout=15)
            data = res.json().get('data', [])
            if not data: break
                
            for coin in data:
                sym = coin.get('symbol', '').upper()
                vol = coin.get('volume24', 0) or 0
                if vol >= 1_000_000 and sym not in MEGA_COINS:
                    all_coins[sym] = vol
                    
            start += limit
            time.sleep(0.5)
    except Exception as e:
        print(f"CoinLore failed: {e}")
        return {}
        
    return all_coins

async def run_market_scan():
    # 1. Initialize Exchanges
    print("🔌 Initializing 15 Major Exchanges...")
    exchanges = {}
    for ex_id in MAJOR_EXCHANGES:
        try:
            exchanges[ex_id] = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
            await exchanges[ex_id].load_markets()
        except Exception:
            pass

    # 2. Fetch ALL Tickers across ALL exchanges simultaneously
    print("📊 Fetching 24h tickers from all exchanges concurrently...")
    ticker_tasks = [ex.fetch_tickers() for ex in exchanges.values()]
    all_tickers_results = await asyncio.gather(*ticker_tasks, return_exceptions=True)
    
    exchange_tickers = {}
    for i, ex_id in enumerate(exchanges.keys()):
        if isinstance(all_tickers_results[i], dict):
            exchange_tickers[ex_id] = all_tickers_results[i]
            
    print(f"✅ Loaded tickers from {len(exchange_tickers)} active exchanges.")

    # 3. Get Global Universe & Filter by Bitget
    global_dict = await get_global_universe()
    if not global_dict: return None

    bitget_tickers = exchange_tickers.get('bitget', {})
    valid_coins = []
    
    for sym, global_vol in global_dict.items():
        market_sym = f"{sym}/USDT:USDT"
        if market_sym in bitget_tickers:
            valid_coins.append(sym)
            
    print(f"📊 {len(valid_coins)} global coins (>$1M vol) are tradable on Bitget.")

    # 4. Stage 1: Fast Fluctuation Filter on Bitget (0.15%+)
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
    print(f"🎯 {len(candidates)} coins passed the Bitget 0.15% fluctuation filter.")

    if not candidates: return None

    # 5. Stage 2: Top 10 Exchange Verification & Ranked Averaging
    print("🔬 Stage 2: Verifying 95% volume coverage & ranking the best candidate...")
    sem_agg = asyncio.Semaphore(20)
    
    all_ranked_candidates = []

    for sym in candidates:
        market_sym = f"{sym}/USDT:USDT"
        global_vol = global_dict[sym]
        
        # Find which of the 15 exchanges hold this coin and their volumes
        holding_exchanges = []
        for ex_id, tickers in exchange_tickers.items():
            if market_sym in tickers:
                vol = tickers[market_sym].get('quoteVolume', 0) or 0
                if vol > 0:
                    holding_exchanges.append((ex_id, vol))
                    
        if not holding_exchanges: continue
        
        # Sort by volume and take the Top 10
        holding_exchanges.sort(key=lambda x: x[1], reverse=True)
        top_10_exchanges = holding_exchanges[:10]
        
        # Check 95% Volume Accuracy
        combined_24h_vol = sum(x[1] for x in top_10_exchanges)
        vol_captured_pct = (combined_24h_vol / global_vol) * 100
        
        if vol_captured_pct < 95.0:
            continue
            
        # Fetch 10m candles from these specific Top 10 exchanges
        tasks = [fetch_ccxt_candles(exchanges[ex_id], sym, sem_agg) for ex_id, _ in top_10_exchanges]
        candle_results = await asyncio.gather(*tasks)
        
        valid_candles = [r for r in candle_results if r is not None]
        if not valid_candles: continue
        
        # --- THE GENIUS AVERAGING METHOD ---
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
            
            ex_green_pct = green / total_vol
            ex_red_pct = red / total_vol
            
            open_price = last_10[0][1]
            close_price = last_10[-1][4]
            ex_price_change = ((close_price - open_price) / open_price) * 100
            
            fluct = [((c[2] - c[3]) / c[3]) * 100 for c in last_10]
            ex_fluct = sum(fluct) / len(fluct)
            
            sum_green_pct += ex_green_pct
            sum_red_pct += ex_red_pct
            sum_price_change += ex_price_change
            sum_fluct += ex_fluct
            count += 1
            
        if count == 0: continue
        
        avg_green_pct = sum_green_pct / count
        avg_red_pct = sum_red_pct / count
        avg_price_change = sum_price_change / count
        avg_fluct = sum_fluct / count

        # --- THE NEW RANKING LOGIC (No strict cutoffs) ---
        # We want the biggest price move with the smallest winning volume.
        # If price went up, we calculate Long score. If price went down, we calculate Short score.
        
        if avg_price_change > 0:
            # LONG: High price change, low buy volume
            score = avg_price_change / (avg_green_pct + 0.01) # 0.01 prevents div by zero
            direction = "LONG"
            win_vol = avg_green_pct
            lose_vol = avg_red_pct
        else:
            # SHORT: High negative price change, low sell volume
            score = abs(avg_price_change) / (avg_red_pct + 0.01)
            direction = "SHORT"
            win_vol = avg_red_pct
            lose_vol = avg_green_pct
            
        # Add a small bonus for high raw fluctuation to break ties
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

    # Pick the absolute best candidate from the entire list
    if not all_ranked_candidates:
        print("❌ No valid candidates found after 95% volume filtering.")
        return None
        
    all_ranked_candidates.sort(key=lambda x: x['score'], reverse=True)
    best_winner = all_ranked_candidates[0]

    print(f"🔥 BEST RELATIVE CANDIDATE: {best_winner['symbol']} ({best_winner['direction']})")
    print(f"   Price Move: {best_winner['move']:+.2f}%")
    print(f"   Winning Side Volume: {best_winner['win_vol']*100:.1f}% (Losing Side: {best_winner['lose_vol']*100:.1f}%)")
    print(f"   Aggregated across {best_winner['exchanges_used']} exchanges.")
    print(f"   Volume Accuracy: {best_winner['vol_captured']:.1f}% of Global")
    return best_winner

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
