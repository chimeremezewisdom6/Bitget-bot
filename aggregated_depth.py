import ccxt.async_support as ccxt_async
import asyncio
import requests
import logging

logger = logging.getLogger("depth_aggregator")

# ALL 8 MAJOR EXCHANGES
EXCHANGES = ['binance', 'okx', 'bybit', 'bitget', 'kucoin', 'coinbase', 'hyperliquid', 'bingx']

# Create instances ONCE to prevent memory leaks and respect rate limits
exchanges = {}
for ex_id in EXCHANGES:
    try:
        # Some exchanges need specific options for perpetuals or spot
        exchanges[ex_id] = getattr(ccxt_async, ex_id)({
            'enableRateLimit': True, 
            'timeout': 3000 # 3 seconds max per exchange
        })
    except Exception as e:
        logger.error(f"Could not initialize {ex_id}: {e}")

async def _fetch_one_exchange(exchange_id, symbol):
    if exchange_id not in exchanges:
        return None
    exchange = exchanges[exchange_id]
    
    try:
        # Try spot first, then swap
        try:
            ob = await asyncio.wait_for(exchange.fetch_order_book(symbol, limit=50), timeout=2.0)
        except (Exception, asyncio.TimeoutError):
            swap_symbol = f"{symbol.split('/')[0]}/{symbol.split('/')[1]}:USDT" if ':' not in symbol else symbol
            ob = await asyncio.wait_for(exchange.fetch_order_book(swap_symbol, limit=50), timeout=2.0)
        
        if not ob['bids'] or not ob['asks']:
            return None
        
        mid_price = (ob['bids'][0][0] + ob['asks'][0][0]) / 2.0
        if mid_price <= 0: return None
        
        min_bid = mid_price * 0.99
        max_ask = mid_price * 1.01
        
        bid_usd = sum(p * s for p, s in ob['bids'] if p >= min_bid)
        ask_usd = sum(p * s for p, s in ob['asks'] if p <= max_ask)
        
        return {'exchange': exchange_id, 'bids_usd': bid_usd, 'asks_usd': ask_usd}
    except Exception:
        return None

async def get_aggregated_ratio(symbol):
    base_symbol = symbol.split(':')[0] if ':' in symbol else symbol
    tasks = [_fetch_one_exchange(ex_id, base_symbol) for ex_id in EXCHANGES]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_bids, total_asks = 0.0, 0.0
    successful_exchanges = 0
    for res in results:
        if isinstance(res, Exception) or res is None: continue
        total_bids += res['bids_usd']
        total_asks += res['asks_usd']
        successful_exchanges += 1
        
    if total_asks <= 0: return 1.0
    
    ratio = total_bids / total_asks
    logger.info(f"🔍 [{base_symbol}] Global Ratio: {ratio:.2f}x | Bids: ${total_bids:,.0f} | Asks: ${total_asks:,.0f} | Sources: {successful_exchanges}/{len(EXCHANGES)}")
    return ratio

async def passes_volume_check(coin_symbol):
    base_coin = coin_symbol.split('/')[0].split(':')[0]
    pair = f"{base_coin}/USDT"
    
    local_vol = 0.0
    for ex_id in EXCHANGES:
        if ex_id not in exchanges: continue
        try:
            ticker = await asyncio.wait_for(exchanges[ex_id].fetch_ticker(pair), timeout=2.0)
            if ticker and ticker.get('quoteVolume'):
                local_vol += ticker['quoteVolume']
        except Exception:
            pass

    if local_vol == 0: return False

    try:
        res = requests.get("https://api.coinlore.net/api/tickers/", timeout=5)
        data = res.json().get('data', [])
        global_vol = 0.0
        for c in data:
            if c.get('symbol', '').upper() == base_coin:
                global_vol = float(c.get('volume24', 0))
                break
                
        if global_vol == 0: return False

        ratio = global_vol / local_vol
        logger.info(f"⚖️ [{base_coin}] Volume Check | Local: ${local_vol:,.0f} | Global: ${global_vol:,.0f} | Ratio: {ratio:.2f}")
        
        if ratio > 1.10:
            logger.warning(f"🚫 [{base_coin}] REJECTED. Global Vol is {(ratio-1)*100:.1f}% higher than our local view.")
            return False
        return True
    except Exception as e:
        logger.error(f"CoinLore API error: {e}")
        return False
