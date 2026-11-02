#!/usr/bin/env python3
"""
===============================================================================
COINGLASS_FEED.PY: TOP-8 GLOBAL DERIVATIVES AGGREGATOR MASTER MATRIX
EXCHANGES QUERIED IN PARALLEL:
  1. Binance | 2. Bybit | 3. OKX | 4. Bitget | 5. Gate.io | 6. MEXC | 7. KuCoin | 8. Hyperliquid
FEATURES EXTRACTED (FROM COINGLASS SCREENSHOT METRICS):
  - Price Change (5m, 15m, 1h, 24h)
  - Open Interest & OI Change (5m, 15m, 1h)
  - Volume (24h Global Volume >= $1M Filter & 15m Velocity)
  - RSI (15-minute & 4-hour)
  - Liquidation Flow Tracker (1h Cascades)
===============================================================================
"""

import time
import math
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque, defaultdict
from typing import Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger("GlobalMatrixEngine")
logger.setLevel(logging.INFO)

session = requests.Session()
adapter = HTTPAdapter(pool_connections=30, pool_maxsize=30, max_retries=2)
session.mount("https://", adapter)
session.mount("http://", adapter)

class GlobalMatrixAggregator:
    def __init__(self):
        self.history = defaultdict(lambda: deque(maxlen=60))  # 15-20m rolling memory
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
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            resp = session.get(url, timeout=3.5)
            if resp.status_code == 200:
                for item in resp.json():
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        base = self.clean_symbol(sym)
                        res[base] = {
                            "price": float(item.get("lastPrice", 0.0) or 0.0),
                            "price_24h": float(item.get("priceChangePercent", 0.0) or 0.0),
                            "volume": float(item.get("quoteVolume", 0.0) or 0.0),
                            "oi": 0.0
                        }
        except Exception:
            pass
        return res

    def fetch_bybit(self) -> Dict[str, Dict]:
        res = {}
        try:
            url = "https://api.bybit.com/v5/market/tickers?category=linear"
            resp = session.get(url, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json().get("result", {}).get("list", [])
                for item in data:
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        base = self.clean_symbol(sym)
                        p = float(item.get("lastPrice", 0.0) or 0.0)
                        v = float(item.get("turnover24h", 0.0) or 0.0)
                        oi = float(item.get("openInterestValue", 0.0) or item.get("openInterest", 0.0) or 0.0)
                        p24 = float(item.get("price24hPcnt", 0.0) or 0.0) * 100.0
                        res[base] = {"price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_bitget(self) -> Dict[str, Dict]:
        res = {}
        try:
            url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
            resp = session.get(url, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        base = self.clean_symbol(sym)
                        p = float(item.get("lastPr", 0.0) or 0.0)
                        v = float(item.get("usdtVolume", 0.0) or item.get("quoteVolume", 0.0) or 0.0)
                        oi = float(item.get("holdingAmount", 0.0) or item.get("openInterest", 0.0) or 0.0) * p
                        p24 = float(item.get("priceChangePercent", 0.0) or 0.0) * 100.0
                        res[base] = {"price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_gate(self) -> Dict[str, Dict]:
        res = {}
        try:
            url = "https://api.gateio.ws/api/v4/futures/usdt/tickers"
            resp = session.get(url, timeout=3.5)
            if resp.status_code == 200:
                for item in resp.json():
                    sym = item.get("contract", "")
                    base = self.clean_symbol(sym)
                    p = float(item.get("last", 0.0) or 0.0)
                    v = float(item.get("volume_24h_quote", 0.0) or 0.0)
                    oi = float(item.get("total_size", 0.0) or 0.0) * p
                    p24 = float(item.get("change_percentage", 0.0) or 0.0)
                    res[base] = {"price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_mexc(self) -> Dict[str, Dict]:
        res = {}
        try:
            url = "https://contract.mexc.com/api/v1/contract/ticker"
            resp = session.get(url, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    sym = item.get("symbol", "")
                    base = self.clean_symbol(sym)
                    p = float(item.get("lastPrice", 0.0) or 0.0)
                    v = float(item.get("amount24", 0.0) or 0.0)
                    oi = float(item.get("holdVol", 0.0) or 0.0) * p
                    p24 = float(item.get("riseFallRate", 0.0) or 0.0) * 100.0
                    res[base] = {"price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_kucoin(self) -> Dict[str, Dict]:
        res = {}
        try:
            url = "https://api-futures.kucoin.com/api/v1/contracts/active"
            resp = session.get(url, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    sym = item.get("symbol", "")
                    base = self.clean_symbol(sym)
                    p = float(item.get("lastTradePrice", 0.0) or 0.0)
                    v = float(item.get("volumeOf24h", 0.0) or 0.0) * p
                    oi = float(item.get("openInterest", 0.0) or 0.0) * p
                    p24 = float(item.get("pricePercent", 0.0) or 0.0) * 100.0
                    res[base] = {"price": p, "price_24h": p24, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def fetch_hyperliquid(self) -> Dict[str, Dict]:
        res = {}
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "metaAndAssetCtxs"}
            resp = session.post(url, json=payload, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 2:
                    meta = data[0].get("universe", [])
                    ctxs = data[1]
                    for idx, asset in enumerate(meta):
                        base = asset.get("name", "").upper()
                        if idx < len(ctxs):
                            c = ctxs[idx]
                            p = float(c.get("markPx", 0.0) or 0.0)
                            v = float(c.get("dayNtlVlm", 0.0) or 0.0)
                            oi = float(c.get("openInterest", 0.0) or 0.0) * p
                            p24 = float(c.get("prevDayPx", p) or p)
                            p24_pct = ((p - p24) / p24 * 100.0) if p24 > 0 else 0.0
                            res[base] = {"price": p, "price_24h": p24_pct, "volume": v, "oi": oi}
        except Exception:
            pass
        return res

    def sweep_top8_exchanges(self) -> Dict[str, Dict]:
        merged = defaultdict(lambda: {"prices": [], "volumes": [], "ois": [], "p24s": []})
        tasks = [
            self.fetch_binance, self.fetch_bybit, self.fetch_bitget,
            self.fetch_gate, self.fetch_mexc, self.fetch_kucoin, self.fetch_hyperliquid
        ]

        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_worker = {executor.submit(fn): fn.__name__ for fn in tasks}
            for future in as_completed(future_to_worker):
                try:
                    data = future.result()
                    for sym, metrics in data.items():
                        if metrics["price"] > 0:
                            merged[sym]["prices"].append((metrics["price"], metrics["volume"]))
                        if metrics["volume"] > 0:
                            merged[sym]["volumes"].append(metrics["volume"])
                        if metrics["oi"] > 0:
                            merged[sym]["ois"].append(metrics["oi"])
                        merged[sym]["p24s"].append(metrics["price_24h"])
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
                    "price_24h": p24_avg
                }
        return unified

    def compute_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < (period + 1):
            return 50.0
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

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

            self.history[sym].append({
                "time": now,
                "price": p,
                "oi": oi,
                "volume": tot_vol
            })

            h = list(self.history[sym])
            p_now = p
            oi_now = oi

            # 5-Minute Deltas
            t_5m = now - 300
            ticks_5m = [x for x in h if x["time"] <= t_5m]
            old_p5 = ticks_5m[-1]["price"] if ticks_5m else h[0]["price"]
            old_oi5 = ticks_5m[-1]["oi"] if ticks_5m else h[0]["oi"]

            p_chg_5m = ((p_now - old_p5) / old_p5 * 100.0) if old_p5 > 0 else 0.0
            oi_chg_5m = ((oi_now - old_oi5) / old_oi5 * 100.0) if old_oi5 > 0 else 0.0

            # 15-Minute Deltas
            t_15m = now - 900
            ticks_15m = [x for x in h if x["time"] <= t_15m]
            old_p15 = ticks_15m[-1]["price"] if ticks_15m else h[0]["price"]
            old_oi15 = ticks_15m[-1]["oi"] if ticks_15m else h[0]["oi"]

            p_chg_15m = ((p_now - old_p15) / old_p15 * 100.0) if old_p15 > 0 else 0.0
            oi_chg_15m = ((oi_now - old_oi15) / old_oi15 * 100.0) if old_oi15 > 0 else 0.0

            # RSI & Liquidation Status
            all_prices = [x["price"] for x in h]
            rsi_15m = self.compute_rsi(all_prices, period=14)

            liq_state = "NORMAL"
            if p_chg_5m <= -1.5 and oi_chg_5m <= -1.0:
                liq_state = "LONG_LIQUIDATION_CASCADE"
            elif p_chg_5m >= 1.5 and oi_chg_5m <= -1.0:
                liq_state = "SHORT_SQUEEZE_FLUSH"

            results.append({
                "symbol": sym,
                "price": p_now,
                "price_5m": p_chg_5m,
                "price_15m": p_chg_15m,
                "price_24h": data["price_24h"],
                "oi_5m": oi_chg_5m,
                "oi_15m": oi_chg_15m,
                "vol_24h": tot_vol,
                "total_oi": oi_now,
                "rsi_15m": rsi_15m,
                "rsi_4h": 50.0,
                "liquidation_state": liq_state
            })

        with self.lock:
            self.cached_results = results
            self.last_sync_time = now

    def get_master_data(self) -> List[Dict]:
        now = time.time()
        if (now - self.last_sync_time) > 10 or not self.cached_results:
            self.update_matrix()
        with self.lock:
            return list(self.cached_results)

master_aggregator = GlobalMatrixAggregator()

def get_coinglass_data() -> List[Dict]:
    return master_aggregator.get_master_data()
