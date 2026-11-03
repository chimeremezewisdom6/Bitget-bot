#!/usr/bin/env python3
"""
===============================================================================
COINGLASS_FEED.PY: TOP-8 GLOBAL DERIVATIVES AGGREGATOR (3M HIGH-RES ENGINE)
EXCHANGES: Binance, Bybit, Bitget, Gate.io, MEXC, KuCoin, Hyperliquid
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
        # 30-minute rolling buffer storing high-res ticks
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

            # 3-Minute Deltas
            t_3m = now - 180
            ticks_3m = [x for x in h if x["time"] <= t_3m]
            old_3m_tick = ticks_3m[-1] if ticks_3m else h[0]
            old_p3 = old_3m_tick["price"]
            old_oi3 = old_3m_tick["oi"]
            p_chg_3m = ((p_now - old_p3) / old_p3 * 100.0) if old_p3 > 0 else 0.0
            oi_chg_3m = ((oi_now - old_oi3) / old_oi3 * 100.0) if old_oi3 > 0 else 0.0

            # 5-Minute Deltas
            t_5m = now - 300
            ticks_5m = [x for x in h if x["time"] <= t_5m]
            old_5m_tick = ticks_5m[-1] if ticks_5m else h[0]
            old_p5 = old_5m_tick["price"]
            old_oi5 = old_5m_tick["oi"]
            p_chg_5m = ((p_now - old_p5) / old_p5 * 100.0) if old_p5 > 0 else 0.0
            oi_chg_5m = ((oi_now - old_oi5) / old_oi5 * 100.0) if old_oi5 > 0 else 0.0

            # 15-Minute Deltas
            t_15m = now - 900
            ticks_15m = [x for x in h if x["time"] <= t_15m]
            old_15m_tick = ticks_15m[-1] if ticks_15m else h[0]
            old_p15 = old_15m_tick["price"]
            old_oi15 = old_15m_tick["oi"]
            p_chg_15m = ((p_now - old_p15) / old_p15 * 100.0) if old_p15 > 0 else 0.0
            oi_chg_15m = ((oi_now - old_oi15) / old_oi15 * 100.0) if old_oi15 > 0 else 0.0

            # 3-Minute Price Trajectory Profile
            profile = []
            for dt in [180, 120, 60, 0]:
                pt = [x["price"] for x in h if x["time"] <= (now - dt)]
                val = pt[-1] if pt else p_now
                rel_pct = ((val - old_p3) / old_p3 * 100.0) if old_p3 > 0 else 0.0
                profile.append(round(rel_pct, 2))

            # ACCURATE 3-MINUTE CROSS-EXCHANGE CONSENSUS:
            # Compares the 3-minute price delta on each exchange individually
            old_ex_prices = old_3m_tick.get("ex_prices", {})
            aligned_count = 0
            eligible_exchanges = 0

            if abs(p_chg_3m) >= 0.10:
                is_bullish = p_chg_3m > 0
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
                "price_3m": p_chg_3m,
                "oi_3m": oi_chg_3m,
                "trajectory_3m": profile,
                "price_5m": p_chg_5m,
                "price_15m": p_chg_15m,
                "price_24h": data["price_24h"],
                "oi_5m": oi_chg_5m,
                "oi_15m": oi_chg_15m,
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
        if (now - self.last_sync_time) > 4 or not self.cached_results:
            self.update_matrix()
        with self.lock:
            return list(self.cached_results)

master_aggregator = GlobalMatrixAggregator()

def get_coinglass_data() -> List[Dict]:
    return master_aggregator.get_master_data()
