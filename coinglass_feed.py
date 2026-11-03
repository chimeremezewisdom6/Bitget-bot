#!/usr/bin/env python3
"""
===============================================================================
COINGLASS_FEED.PY: TOP-8 GLOBAL DERIVATIVES AGGREGATOR (PRODUCTION READY)
EXCHANGES: Binance, Bybit, Bitget, Gate.io, MEXC, KuCoin, Hyperliquid
FEEDS TO BOT.PY:
  - 2-Minute Velocity (Price & OI Deltas with Cold-Start Protection)
  - 5-Minute and 24-Hour Macro Context
  - Cross-Exchange Directional Consensus % (>= 75% Agreement Across Venues)
===============================================================================
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque, defaultdict
from typing import Dict, List
import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger("GlobalMatrixEngine")
logger.setLevel(logging.INFO)

session = requests.Session()
adapter = HTTPAdapter(pool_connections=40, pool_maxsize=40, max_retries=2)
session.mount("https://", adapter)
session.mount("http://", adapter)

class GlobalMatrixAggregator:
    def __init__(self):
        self.history = defaultdict(lambda: deque(maxlen=360))
        self.cached_results: List[Dict] = []
        self.last_sync_time = 0.0
        self.lock = threading.Lock()

    def clean_symbol(self, raw_sym: str) -> str:
        s = raw_sym.upper().replace("-", "").replace("_", "")
        for suffix in ["USDT:USDT", ":USDT", "USDT", "USDC", "USD", "PERP", "SWAP"]:
            if s.endswith(suffix):
                s = s[:-len(suffix)]
                break
        return s

    def fetch_binance(self) -> Dict[str, Dict]:
        res = {}
        try:
            resp = session.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=2.5)
            if resp.status_code == 200:
                for item in resp.json():
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        base = self.clean_symbol(sym)
                        p = float(item.get("lastPrice", 0.0) or 0.0)
                        v = float(item.get("quoteVolume", 0.0) or 0.0)
                        p24 = float(item.get("priceChangePercent", 0.0) or 0.0)
                        res[base] = {"exchange": "BINANCE", "price": p, "price_24h": p24, "volume": v, "oi": 0.0}
        except Exception:
            pass
        return res

    def fetch_bybit(self) -> Dict[str, Dict]:
        res = {}
        try:
            resp = session.get("https://api.bybit.com/v5/market/tickers?category=linear", timeout=2.5)
            if resp.status_code == 200:
                for item in resp.json().get("result", {}).get("list", []):
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        base = self.clean_symbol(sym)
                        p = float(item.get("lastPrice", 0.0) or 0.0)
                        v = float(item.get("turnover24h", 0.0) or 0.0)
                        oi = float(item.get("openInterestValue", 0.0) or item.get("openInterest", 0.0) or 0.0)
                        p24 = float(item.get("price24hPcnt", 0.0) or 0.0) * 100.0
                        res[base] = {"exchange": "BYBIT", "price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_bitget(self) -> Dict[str, Dict]:
        res = {}
        try:
            resp = session.get("https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES", timeout=2.5)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        base = self.clean_symbol(sym)
                        p = float(item.get("lastPr", 0.0) or 0.0)
                        v = float(item.get("usdtVolume", 0.0) or item.get("quoteVolume", 0.0) or 0.0)
                        oi = float(item.get("holdingAmount", 0.0) or item.get("openInterest", 0.0) or 0.0) * p
                        p24 = float(item.get("priceChangePercent", 0.0) or 0.0) * 100.0
                        res[base] = {"exchange": "BITGET", "price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_gate(self) -> Dict[str, Dict]:
        res = {}
        try:
            resp = session.get("https://api.gateio.ws/api/v4/futures/usdt/tickers", timeout=2.5)
            if resp.status_code == 200:
                for item in resp.json():
                    base = self.clean_symbol(item.get("contract", ""))
                    p = float(item.get("last", 0.0) or 0.0)
                    v = float(item.get("volume_24h_quote", 0.0) or 0.0)
                    oi = float(item.get("total_size", 0.0) or 0.0) * p
                    p24 = float(item.get("change_percentage", 0.0) or 0.0)
                    res[base] = {"exchange": "GATE", "price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_mexc(self) -> Dict[str, Dict]:
        res = {}
        try:
            resp = session.get("https://contract.mexc.com/api/v1/contract/ticker", timeout=2.5)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    base = self.clean_symbol(item.get("symbol", ""))
                    p = float(item.get("lastPrice", 0.0) or 0.0)
                    v = float(item.get("amount24", 0.0) or 0.0)
                    oi = float(item.get("holdVol", 0.0) or 0.0) * p
                    p24 = float(item.get("riseFallRate", 0.0) or 0.0) * 100.0
                    res[base] = {"exchange": "MEXC", "price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_kucoin(self) -> Dict[str, Dict]:
        res = {}
        try:
            resp = session.get("https://api-futures.kucoin.com/api/v1/contracts/active", timeout=2.5)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    base = self.clean_symbol(item.get("symbol", ""))
                    p = float(item.get("lastTradePrice", 0.0) or 0.0)
                    v = float(item.get("volumeOf24h", 0.0) or 0.0) * p
                    oi = float(item.get("openInterest", 0.0) or 0.0) * p
                    p24 = float(item.get("pricePercent", 0.0) or 0.0) * 100.0
                    res[base] = {"exchange": "KUCOIN", "price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_hyperliquid(self) -> Dict[str, Dict]:
        res = {}
        try:
            resp = session.post("https://api.hyperliquid.xyz/info", json={"type": "metaAndAssetCtxs"}, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 2:
                    meta, ctxs = data[0].get("universe", []), data[1]
                    for idx, asset in enumerate(meta):
                        base = asset.get("name", "").upper()
                        if idx < len(ctxs):
                            c = ctxs[idx]
                            p = float(c.get("markPx", 0.0) or 0.0)
                            v = float(c.get("dayNtlVlm", 0.0) or 0.0)
                            oi = float(c.get("openInterest", 0.0) or 0.0) * p
                            p24 = float(c.get("prevDayPx", p) or p)
                            p24_pct = ((p - p24) / p24 * 100.0) if p24 > 0 else 0.0
                            res[base] = {"exchange": "HYPERLIQUID", "price": p, "price_24h": p24_pct, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def sweep_top8_exchanges(self) -> Dict[str, Dict]:
        merged = defaultdict(lambda: {"ex_prices": {}, "prices": [], "volumes": [], "ois": [], "p24s": []})
        tasks = [
            self.fetch_binance, self.fetch_bybit, self.fetch_bitget,
            self.fetch_gate, self.fetch_mexc, self.fetch_kucoin, self.fetch_hyperliquid
        ]

        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_worker = {executor.submit(fn): fn.__name__ for fn in tasks}
            for future in as_completed(future_to_worker):
                try:
                    data = future.result()
                    for sym, m in data.items():
                        if m["price"] > 0:
                            merged[sym]["prices"].append((m["price"], m["volume"]))
                            merged[sym]["ex_prices"][m["exchange"]] = m["price"]
                        if m["volume"] > 0:
                            merged[sym]["volumes"].append(m["volume"])
                        if m["oi"] > 0:
                            merged[sym]["ois"].append(m["oi"])
                        merged[sym]["p24s"].append(m["price_24h"])
                except Exception:
                    pass

        unified = {}
        for sym, d in merged.items():
            tot_vol = sum(d["volumes"])
            tot_oi = sum(d["ois"])
            vwap = sum(p * v for p, v in d["prices"]) / sum(v for _, v in d["prices"] if v > 0) if sum(v for _, v in d["prices"] if v > 0) > 0 else (d["prices"][0][0] if d["prices"] else 0.0)
            p24_avg = sum(d["p24s"]) / len(d["p24s"]) if d["p24s"] else 0.0

            if vwap > 0:
                unified[sym] = {
                    "price": vwap,
                    "volume": tot_vol,
                    "oi": tot_oi,
                    "price_24h": p24_avg,
                    "ex_prices": d["ex_prices"],
                    "exchange_count": len(d["ex_prices"])
                }
        return unified

    def update_matrix(self):
        now = time.time()
        unified = self.sweep_top8_exchanges()
        results = []

        for sym, data in unified.items():
            tot_vol = data["volume"]
            if tot_vol < 1_000_000.0:  # $1M Global Volume Filter
                continue

            p = data["price"]
            oi = data["oi"]
            cur_ex_prices = data.get("ex_prices", {})

            self.history[sym].append({
                "time": now,
                "price": p,
                "oi": oi,
                "volume": tot_vol,
                "ex_prices": cur_ex_prices
            })

            h = list(self.history[sym])
            p_now = p
            oi_now = oi

            # 2-Minute Deltas with Cold-Start Guard
            t_2m = now - 120
            ticks_2m = [x for x in h if x["time"] <= t_2m]
            old_2m_tick = ticks_2m[-1] if ticks_2m else h[0]
            
            # Cold-start validation: ensure at least 60 seconds of history has accumulated
            time_span = now - old_2m_tick["time"]
            if time_span >= 60.0 and old_2m_tick["price"] > 0:
                p_chg_2m = ((p_now - old_2m_tick["price"]) / old_2m_tick["price"]) * 100.0
                old_oi = old_2m_tick["oi"]
                oi_chg_2m = ((oi_now - old_oi) / old_oi * 100.0) if old_oi > 0 else 0.0
            else:
                p_chg_2m = 0.0
                oi_chg_2m = 0.0

            # 5-Minute Deltas
            t_5m = now - 300
            ticks_5m = [x for x in h if x["time"] <= t_5m]
            old_5m_tick = ticks_5m[-1] if ticks_5m else h[0]
            p_chg_5m = ((p_now - old_5m_tick["price"]) / old_5m_tick["price"] * 100.0) if old_5m_tick["price"] > 0 else 0.0

            # Cross-Exchange Consensus
            old_ex_prices = old_2m_tick.get("ex_prices", {})
            aligned_count = 0
            eligible_exchanges = 0

            if abs(p_chg_2m) >= 0.10:
                is_bullish = p_chg_2m > 0
                for ex_name, current_p in cur_ex_prices.items():
                    if ex_name in old_ex_prices:
                        past_p = old_ex_prices[ex_name]
                        if past_p > 0:
                            eligible_exchanges += 1
                            ex_delta = (current_p - past_p) / past_p * 100.0
                            if (is_bullish and ex_delta >= 0) or (not is_bullish and ex_delta <= 0):
                                aligned_count += 1

            if eligible_exchanges > 0:
                consensus_pct = (aligned_count / eligible_exchanges) * 100.0
                aligned_str = f"{aligned_count}/{eligible_exchanges}"
            else:
                consensus_pct = 100.0
                aligned_str = f"{len(cur_ex_prices)}/{len(cur_ex_prices)}"

            results.append({
                "symbol": sym,
                "price": p_now,
                "price_2m": p_chg_2m,
                "oi_2m": oi_chg_2m,
                "price_5m": p_chg_5m,
                "price_24h": data["price_24h"],
                "vol_24h": tot_vol,
                "total_oi": oi_now,
                "exchange_count": len(cur_ex_prices),
                "consensus_pct": round(consensus_pct, 1),
                "exchanges_aligned": aligned_str
            })

        with self.lock:
            self.cached_results = results
            self.last_sync_time = now

    def get_master_data(self) -> List[Dict]:
        now = time.time()
        # 5.0s cache protects against shared-IP rate limiting on Render
        if (now - self.last_sync_time) > 5.0 or not self.cached_results:
            self.update_matrix()
        with self.lock:
            return list(self.cached_results)

master_aggregator = GlobalMatrixAggregator()

def get_coinglass_data() -> List[Dict]:
    return master_aggregator.get_master_data()
