import time
import json
import threading
import requests
import asyncio
import aiohttp
import logging
from collections import deque

logger = logging.getLogger("FeedAggregator")
logger.setLevel(logging.INFO)

def normalize_base(symbol: str) -> str:
    """Normalizes symbols like 1000PEPE, 1000000MOG, 1000BONK to PEPE, MOG, BONK."""
    s = symbol.upper()
    for prefix in ["10000000", "1000000", "100000", "10000", "1000", "K", "1M"]:
        if s.startswith(prefix) and len(s) > len(prefix) + 2:
            return s[len(prefix):]
    return s

def get_coinglass_data():
    return {}

class GlobalFeedAggregator:
    """
    Lightweight, thread-safe global market aggregator.
    Streams Binance Futures WebSocket volume + polls OKX, Bybit, and Bitget tickers/OI.
    Tracks 5-minute price expansion curves and Open Interest trajectories.
    RAM consumption strictly < 18MB.
    """
    def __init__(self, update_interval: int = 10):
        self.update_interval = update_interval
        self.running = False
        self.thread = None
        self.ws_thread = None
        self.lock = threading.Lock()
        self.session = requests.Session()
        
        self._price_history = {}      # base -> deque([(ts, price)], maxlen=45)
        self._oi_history = {}         # base -> deque([(ts, oi)], maxlen=45)
        self._global_volume = {}      # base -> 24h USD volume
        self._binance_volume = {}     # base -> Binance 24h volume
        self._last_seen = {}
        self._consecutive_hits = {}   # base -> count of consecutive qualifications

    def start(self):
        self.running = True
        self.ws_thread = threading.Thread(target=self._run_binance_ws, daemon=True)
        self.ws_thread.start()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Global Feed Aggregator started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.session.close()

    def _run_binance_ws(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._binance_ws_loop())

    async def _binance_ws_loop(self):
        url = "wss://fstream.binance.com/ws/!miniTicker@arr"
        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=20.0) as ws:
                        async for msg in ws:
                            if not self.running:
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                now = time.time()
                                with self.lock:
                                    for item in data:
                                        sym = item.get("s", "")
                                        if sym.endswith("USDT"):
                                            clean = normalize_base(sym[:-4])
                                            self._binance_volume[clean] = float(item.get("q", 0.0))
                                            self._last_seen[clean] = now
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
            except Exception:
                await asyncio.sleep(5)

    def _run_loop(self):
        while self.running:
            try:
                self._poll_secondary_tickers()
                self._prune_stale()
            except Exception as e:
                logger.error(f"Feed poll error: {e}")
            time.sleep(self.update_interval)

    def _poll_secondary_tickers(self):
        now = time.time()
        temp_volumes = {}
        temp_prices = {}
        temp_ois = {}

        # 1. OKX USDT Swaps
        try:
            r = self.session.get("https://www.okx.com/api/v5/market/tickers?instType=SWAP", timeout=3.5)
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    inst_id = item.get("instId", "")
                    if inst_id.endswith("-USDT-SWAP"):
                        clean = normalize_base(inst_id.split("-")[0])
                        temp_volumes[clean] = temp_volumes.get(clean, 0.0) + float(item.get("volCcy24h", 0.0))
        except Exception:
            pass

        # 2. Bybit Linear
        try:
            r = self.session.get("https://api.bybit.com/v5/market/tickers?category=linear", timeout=3.5)
            if r.status_code == 200:
                for item in r.json().get("result", {}).get("list", []):
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        clean = normalize_base(sym[:-4])
                        temp_volumes[clean] = temp_volumes.get(clean, 0.0) + float(item.get("turnover24h", 0.0))
        except Exception:
            pass

        # 3. Bitget USDT Futures (Execution Anchor & OI Source)
        try:
            r = self.session.get("https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures", timeout=3.5)
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        clean = normalize_base(sym[:-4])
                        temp_volumes[clean] = temp_volumes.get(clean, 0.0) + float(item.get("usdtVolume", 0.0))
                        price = float(item.get("lastPr", 0.0))
                        oi = float(item.get("holdingAmount", 0.0) or item.get("openInterest", 0.0))
                        if price > 0:
                            temp_prices[clean] = price
                        if oi > 0:
                            temp_ois[clean] = oi
        except Exception:
            pass

        with self.lock:
            for base, vol in temp_volumes.items():
                b_vol = self._binance_volume.get(base, 0.0)
                self._global_volume[base] = vol + b_vol
                self._last_seen[base] = now

            for base, price in temp_prices.items():
                if base not in self._price_history:
                    self._price_history[base] = deque(maxlen=45)
                self._price_history[base].append((now, price))

            for base, oi in temp_ois.items():
                if base not in self._oi_history:
                    self._oi_history[base] = deque(maxlen=45)
                self._oi_history[base].append((now, oi))

    def _prune_stale(self):
        now = time.time()
        with self.lock:
            stale = [b for b, ts in self._last_seen.items() if now - ts > 900]
            for b in stale:
                self._global_volume.pop(b, None)
                self._binance_volume.pop(b, None)
                self._price_history.pop(b, None)
                self._oi_history.pop(b, None)
                self._last_seen.pop(b, None)
                self._consecutive_hits.pop(b, None)

    def get_candidate_coins(self, min_vol: float = 1_000_000.0) -> list:
        """
        Filters coins for:
        1. Global Volume >= $1,000,000.
        2. Inception age strictly 220s to 300s (4 to 5 minutes old).
        3. Accelerating velocity (last 2m >= 52% of 5m move).
        4. Strict Asymmetric OI check:
           - LONG requires +OI expansion (>= +0.40%).
           - SHORT requires PANIC WATERFALL with collapsing OI (<= -1.20%).
        """
        now = time.time()
        candidates = []

        with self.lock:
            for base, vol in self._global_volume.items():
                if vol < min_vol:
                    continue

                hist = self._price_history.get(base)
                if not hist or len(hist) < 22:
                    continue

                hist_copy = list(hist)
                curr_time, curr_price = hist_copy[-1]

                if now - curr_time > 35.0:
                    continue

                t_300s = now - 300.0
                t_120s = now - 120.0
                p_5m_ago = None
                p_2m_ago = None

                for t, p in hist_copy:
                    if t >= t_300s and p_5m_ago is None:
                        p_5m_ago = p
                    if t >= t_120s and p_2m_ago is None:
                        p_2m_ago = p

                if not p_5m_ago:
                    p_5m_ago = hist_copy[0][1]
                if not p_2m_ago:
                    p_2m_ago = hist_copy[int(len(hist_copy) * 0.6)][1]

                vel_5m = ((curr_price - p_5m_ago) / p_5m_ago) * 100.0
                vel_2m = ((curr_price - p_2m_ago) / p_2m_ago) * 100.0

                if abs(vel_5m) < 1.20 or abs(vel_5m) > 4.50:
                    continue

                if (vel_5m > 0 and vel_2m <= 0) or (vel_5m < 0 and vel_2m >= 0):
                    continue

                accel_ratio = abs(vel_2m) / abs(vel_5m)
                if accel_ratio < 0.52:
                    continue

                first_ts = hist_copy[0][0]
                wave_age = now - first_ts

                if not (220.0 <= wave_age <= 300.0):
                    continue

                # 5-Minute Open Interest Delta
                oi_hist = self._oi_history.get(base)
                oi_5m_delta_pct = 0.0
                if oi_hist and len(oi_hist) >= 12:
                    old_oi = oi_hist[0][1]
                    now_oi = oi_hist[-1][1]
                    if old_oi > 0:
                        oi_5m_delta_pct = ((now_oi - old_oi) / old_oi) * 100.0

                # PROTOCOL A: LONG requires positive OI expansion (+OI)
                is_valid_long = (vel_5m >= 1.20) and (oi_5m_delta_pct >= 0.40)

                # PROTOCOL B: SHORT strictly requires PANIC WATERFALL with collapsing OI (-OI)
                is_panic_waterfall_short = (vel_5m <= -1.50) and (oi_5m_delta_pct <= -1.20) and (accel_ratio >= 0.55)

                if is_valid_long or is_panic_waterfall_short:
                    hits = self._consecutive_hits.get(base, 0) + 1
                    self._consecutive_hits[base] = hits
                    candidates.append({
                        "base": base,
                        "global_vol": vol,
                        "vel_5m": round(vel_5m, 2),
                        "vel_2m": round(vel_2m, 2),
                        "oi_5m_delta": round(oi_5m_delta_pct, 2),
                        "accel_ratio": round(accel_ratio, 2),
                        "side_allowed": "buy" if is_valid_long else "sell",
                        "wave_age": int(wave_age),
                        "consecutive_hits": hits,
                        "current_price": curr_price
                    })

        return candidates
