"""Stage 1 & 2: Global Momentum Scanner via Bybit REST and Bitget Mapping."""
from __future__ import annotations

import logging
import requests
from typing import TYPE_CHECKING, Optional

from config import Config
from models import Coin, CoinImbalance

if TYPE_CHECKING:
    from exchange_hub import ExchangeHub

log = logging.getLogger("scanner")

def fetch_global_movers():
    """Fetch top volume coins from Bybit public API and find 10-min momentum."""
    log.info("🌐 Fetching global data from Bybit API...")
    try:
        # 1. Get 24h tickers from Bybit (Spot market for general volume)
        res = requests.get("https://api.bybit.com/v5/market/tickers?category=spot", timeout=10)
        tickers = res.json().get('result', {}).get('list', [])
        
        valid_coins = []
        for t in tickers:
            sym = t['symbol']
            if sym.endswith("USDT") and float(t.get('turnover24h', 0)) >= 1_000_000:
                valid_coins.append(sym)
        
        # Sort by turnover (already sorted by Bybit, but just in case) and take top 40 to save time
        valid_coins = valid_coins[:40]
        
        top_movers = []
        for sym in valid_coins:
            try:
                # 2. Fetch last 60 minutes of 1m candles
                url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={sym}&interval=1&limit=60"
                kres = requests.get(url, timeout=5).json().get('result', {}).get('list', [])
                if len(kres) < 60: continue
                
                # Bybit returns newest first, so reverse it
                kres.reverse()
                
                # 3. Calculate 10-minute price change
                open_10m = float(kres[-11][1]) # 11th from the end
                close_now = float(kres[-1][4])
                price_change_pct = ((close_now - open_10m) / open_10m) * 100
                
                # 4. Calculate volume surge
                vol_10m = sum(float(k[5]) for k in kres[-10:]) / 10
                vol_50m = sum(float(k[5]) for k in kres[:-10]) / 50
                
                vol_surge = vol_10m / vol_50m if vol_50m > 0 else 1
                
                # 5. Momentum score
                score = abs(price_change_pct) * vol_surge
                
                top_movers.append({
                    "base": sym.replace("USDT", ""),
                    "price_change": price_change_pct,
                    "score": score
                })
            except Exception:
                continue
                
        if not top_movers:
            return None
            
        # Pick the highest score
        top_movers.sort(key=lambda x: x['score'], reverse=True)
        return top_movers[0]
    except Exception as e:
        log.error(f"Failed global fetch: {e}")
        return None

async def build_universe(hub: "ExchangeHub", cfg: Config) -> list[Coin]:
    """Bypassed. We handle logic in stage2."""
    return []

async def measure(hub: "ExchangeHub", coin: Coin, cfg: Config, priority: str = "scan") -> Optional[CoinImbalance]:
    return None

async def stage1(hub: "ExchangeHub", cfg: Config, coins: list[Coin]):
    """Bypassed."""
    return [], 0

async def stage2(hub: "ExchangeHub", cfg: Config, top: list[CoinImbalance]):
    """Find the best global mover and map it to Bitget."""
    best_mover = fetch_global_movers()
    if not best_mover:
        log.warning("scan produced no candidate (global fetch failed)")
        return None, {}

    base = best_mover['base']
    price_change = best_mover['price_change']
    
    # Check if Bitget has this coin in its execution markets (USDT perps)
    symbol = None
    for sym in hub.exec_map:
        if sym.startswith(base):
            symbol = sym
            break
            
    if not symbol:
        log.warning(f"Coin {base} not found on Bitget execution markets.")
        return None, {}

    # Force the direction based on the 10m price move
    if price_change > 0:
        ci = CoinImbalance(base, bid_usd=100, ask_usd=10, n_venues=1) # Forces LONG
        log.info(f"🚀 GLOBAL MOVER: {base} pumped {price_change:.2f}% in 10m! Forcing LONG.")
    else:
        ci = CoinImbalance(base, bid_usd=10, ask_usd=100, n_venues=1) # Forces SHORT
        log.info(f"📉 GLOBAL MOVER: {base} dumped {price_change:.2f}% in 10m! Forcing SHORT.")

    return ci, {base: best_mover['score']}
