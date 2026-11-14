import requests
import json
import os
import asyncio
import time
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
    print("📊 Fetching 24h tickers from all 15 exchanges concurrently...")
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

    # 5. Stage 2 & 3: Top 10 Exchange Verification & Averaged 10m Aggregation
    print("🔬 Stage 2: Verifying 95% volume coverage using the Top 10 exchanges per coin...")
    sem_agg = asyncio.Semaphore(20)
    best_winner = None
    highest_score = -1

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
        
        # Check if Top 10 accounts for 95%+ of the global volume
        combined_24h_vol = sum(x[1] for x in top_10_exchanges)
        vol_captured_pct = (combined_24h_vol / global_vol) * 100
        
        if vol_captured_pct < 95.0:
            continue # Reject if we don't have 95% of the market
            
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
            
            # Calculate individual exchange metrics
            ex_green_pct = green / total_vol
            ex_red_pct = red / total_vol
            
            open_price = last_10[0][1]
            close_price = last_10[-1][4]
            ex_price_change = ((close_price - open_price) / open_price) * 100
            
            fluct = [((c[2] - c[3]) / c[3]) * 100 for c in last_10]
            ex_fluct = sum(fluct) / len(fluct)
            
            # Sum them up
            sum_green_pct += ex_green_pct
            sum_red_pct += ex_red_pct
            sum_price_change += ex_price_change
            sum_fluct += ex_fluct
            count += 1
            
        if count == 0: continue
        
        # Divide by the number of exchanges (average dominance and price change)
        avg_green_pct = sum_green_pct / count
        avg_red_pct = sum_red_pct / count
        avg_price_change = sum_price_change / count
        avg_fluct = sum_fluct / count

        # Optional filter for aggregated fluctuation
        if avg_fluct < MIN_AVG_FLUCTUATION: continue

        # THE TRAP LOGIC (LONG ONLY)
        if avg_price_change >= MIN_PRICE_MOVE:
            if avg_green_pct <= MAX_WINNING_VOLUME and avg_red_pct >= MIN_LOSING_VOLUME:
                score = avg_price_change / avg_green_pct
                if score > highest_score:
                    highest_score = score
                    best_winner = {
                        "symbol": sym, 
                        "direction": "LONG", 
                        "score": score,
                        "move": avg_price_change,
                        "buy_vol": avg_green_pct,
                        "sell_vol": avg_red_pct,
                        "exchanges_used": count,
                        "vol_captured": vol_captured_pct
                    }

    # Cleanup
    for ex in exchanges.values():
        await ex.close()

    if best_winner:
        print(f"🔥 TRAPPED SELLER DETECTED: {best_winner['symbol']} (LONG)")
        print(f"   Average Price Move (Top 10 Ex): +{best_winner['move']:.2f}%")
        print(f"   Average Buy Vol (Top 10 Ex): {best_winner['buy_vol']*100:.1f}%")
        print(f"   Average Sell Vol (Top 10 Ex): {best_winner['sell_vol']*100:.1f}%")
        print(f"   Aggregated across {best_winner['exchanges_used']} exchanges.")
        print(f"   Volume Accuracy: {best_winner['vol_captured']:.1f}% of Global")
        return best_winner
    else:
        print("❌ No trapped sellers found in aggregated data.")
        return None

if __name__ == "__main__":
    best_coin = asyncio.run(run_market_scan())
    with open("candidate.json", "w") as f:
        if best_coin: json.dump({"symbol": best_coin['symbol'], "direction": best_coin['direction'], "score": best_coin['score']}, f, indent=2)
        else: json.dump({}, f)
