import ccxt.async_support as ccxt_async
import asyncio
import requests
import logging

logger = logging.getLogger("depth_aggregator")

EXCHANGES = ['binance', 'okx', 'bybit', 'bitget', 'kucoin', 'coinbase', 'hyperliquid', 'bingx']

exchanges = {}
for ex_id in EXCHANGES:
    try:
        exchanges[ex_id] = getattr(ccxt_async, ex_id)({'enableRateLimit': True, 'timeout': 3000})
    except Exception as e:
        logger.error(f"Could not initialize {ex_id}: {e}")

async def _fetch_one_exchange(exchange_id, symbol):
    if exchange_id not in exchanges: return None
    exchange = exchanges[exchange_id]
    try:
        try:
            ob = await asyncio.wait_for(exchange.fetch_order_book(symbol, limit=50), timeout=2.0)
        except (Exception, asyncio.TimeoutError):
            swap_symbol = f"{symbol.split('/')[0]}/{symbol.split('/')[1]}:USDT" if ':' not in symbol else symbol
            ob = await asyncio.wait_for(exchange.fetch_order_book(swap_symbol, limit=50), timeout=2.0)
        
        if not ob['bids'] or not ob['asks']: return None
        
        mid_price = (ob['bids'][0][0] + ob['asks'][0][0]) / 2.0
        if mid_price <= 0: return None
        
        bid_usd = sum(p * s for p, s in ob['bids'] if p >= mid_price * 0.99)
        ask_usd = sum(p * s for p, s in ob['asks'] if p <= mid_price * 1.01)
        return {'exchange': exchange_id, 'bids_usd': bid_usd, 'asks_usd': ask_usd}
    except Exception:
        return None

async def get_aggregated_ratio(symbol):
    base_symbol = symbol.split(':')[0] if ':' in symbol else symbol
    tasks = [_fetch_one_exchange(ex_id, base_symbol) for ex_id in EXCHANGES]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_bids, total_asks = 0.0, 0.0
    successful = 0
    for res in results:
        if isinstance(res, Exception) or res is None: continue
        total_bids += res['bids_usd']
        total_asks += res['asks_usd']
        successful += 1
        
    if total_asks <= 0: return 1.0
    return total_bids / total_asks

async def passes_volume_check(coin_symbol):
    base_coin = coin_symbol.split('/')[0].split(':')[0]
    pair = f"{base_coin}/USDT"
    local_vol = 0.0
    for ex_id in EXCHANGES:
        if ex_id not in exchanges: continue
        try:
            ticker = await asyncio.wait_for(exchanges[ex_id].fetch_ticker(pair), timeout=2.0)
            if ticker and ticker.get('quoteVolume'): local_vol += ticker['quoteVolume']
        except Exception: pass

    if local_vol == 0: return False
    try:
        res = requests.get("https://api.coinlore.net/api/tickers/", timeout=5)
        data = res.json().get('data', [])
        global_vol = 0.0
        for c in data:
            if c.get('symbol', '').upper() == base_coin: global_vol = float(c.get('volume24', 0)); break
        if global_vol == 0: return False
        ratio = global_vol / local_vol
        if ratio > 1.10: return False
        return True
    except Exception: return False

# --- NEW: DYNAMIC COIN FETCHER ---
def fetch_coins_above_1m_volume():
    """Fetches all coins with >$1M 24h volume from CoinLore (free, keyless)."""
    logger.info("🌐 Fetching all coins with >$1M 24h volume from CoinLore...")
    try:
        res = requests.get("https://api.coinlore.net/api/tickers/", timeout=10)
        data = res.json().get('data', [])
        
        target_coins = []
        for coin in data:
            vol = coin.get('volume24', 0)
            if vol is not None and vol >= 1_000_000:
                symbol = coin.get('symbol', '').upper()
                # Filter out wrapped tokens or weird symbols
                if symbol and len(symbol) <= 10:
                    target_coins.append(f"{symbol}/USDT:USDT")
        
        # Remove duplicates and return
        unique_coins = list(set(target_coins))
        logger.info(f"🎯 Found {len(unique_coins)} coins with >$1M volume.")
        return unique_coins
    except Exception as e:
        logger.error(f"Failed to fetch CoinLore volume list: {e}")
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"] # Fallback
