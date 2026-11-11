import ccxt.async_support as ccxt_async
import asyncio
import requests
import logging

logger = logging.getLogger("depth_aggregator")
EXCHANGES = ['binance', 'bybit', 'okx', 'bitget', 'kucoin', 'gateio']

async def _fetch_one_exchange(exchange_id, symbol):
    exchange = None
    try:
        exchange_class = getattr(ccxt_async, exchange_id)
        exchange = exchange_class({'enableRateLimit': True, 'timeout': 5000})
        try:
            ob = await exchange.fetch_order_book(symbol, limit=50)
        except Exception:
            # Fallback to swap symbol if spot fails
            swap_symbol = f"{symbol.split('/')[0]}/{symbol.split('/')[1]}:USDT" if ':' not in symbol else symbol
            ob = await exchange.fetch_order_book(swap_symbol, limit=50)
        
        if not ob['bids'] or not ob['asks']:
            return None
        
        mid_price = (ob['bids'][0][0] + ob['asks'][0][0]) / 2.0
        if mid_price <= 0: return None
        
        # 1% range
        min_bid = mid_price * 0.99
        max_ask = mid_price * 1.01
        
        bid_usd = sum(p * s for p, s in ob['bids'] if p >= min_bid)
        ask_usd = sum(p * s for p, s in ob['asks'] if p <= max_ask)
        return {'bids_usd': bid_usd, 'asks_usd': ask_usd}
    except Exception:
        return None
    finally:
        if exchange:
            try: await exchange.close()
            except Exception: pass

async def get_aggregated_ratio(symbol):
    base_symbol = symbol.split(':')[0] if ':' in symbol else symbol
    tasks = [_fetch_one_exchange(ex_id, base_symbol) for ex_id in EXCHANGES]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_bids, total_asks = 0.0, 0.0
    for res in results:
        if isinstance(res, Exception) or res is None: continue
        total_bids += res['bids_usd']
        total_asks += res['asks_usd']
        
    if total_asks <= 0: return 1.0
    return total_bids / total_asks

async def passes_volume_check(coin_symbol):
    """The Skeptical Student Rule"""
    base_coin = coin_symbol.split('/')[0].split(':')[0]
    pair = f"{base_coin}/USDT"
    
    # 1. Local Volume (6 Exchanges)
    local_vol = 0.0
    for ex_id in EXCHANGES:
        exchange = None
        try:
            exchange = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'timeout': 5000})
            ticker = await exchange.fetch_ticker(pair)
            if ticker and ticker.get('quoteVolume'):
                local_vol += ticker['quoteVolume']
        except Exception:
            pass
        finally:
            if exchange:
                try: await exchange.close()
                except Exception: pass

    if local_vol == 0: return False

    # 2. Global Volume (CoinLore)
    try:
        res = requests.get("https://api.coinlore.net/api/tickers/", timeout=5)
        data = res.json().get('data', [])
        global_vol = 0.0
        for c in data:
            if c.get('symbol', '').upper() == base_coin:
                global_vol = float(c.get('volume24', 0))
                break
                
        if global_vol == 0: return False

        # 3. The Rule
        ratio = global_vol / local_vol
        if ratio > 1.10:
            logger.warning(f"🚫 [{base_coin}] REJECTED. Global Vol is {(ratio-1)*100:.1f}% higher than Local.")
            return False
        return True
    except Exception:
        return False
