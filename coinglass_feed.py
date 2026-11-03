import time
import threading
import requests
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

# Backward compatibility helper
def get_coinglass_data():
    return {}

class GlobalFeedAggregator:
    """
    Lightweight, thread-safe global market aggregator.
    Aggregates 24h volume and 2m velocity across Binance, Bybit, and Bitget.
    RAM consumption strictly < 15MB.
    """
    def __init__(self, update_interval: int = 15):
        self.update_interval = update_interval
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.session = requests.Session()
        
        # State stores: base_asset -> (volume, deque([(ts, price)], maxlen=30))
        self._price_history = {}
        self._global_volume = {}
        self._last_seen = {}

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Global Feed Aggregator started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
        self.session.close()

    def _run_loop(self):
        while self.running:
            try:
                self._poll_global_tickers()
                self._prune_stale_symbols()
            except Exception as e:
                logger.error(f"Feed poll error: {e}")
            time.sleep(self.update_interval)

    def _poll_global_tickers(self):
        now = time.time()
        temp_volumes = {}
        temp_prices = {}

        # 1. Binance USDT-M Futures
        try:
            r = self.session.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=3.5)
            if r.status_code == 200:
                for item in r.json():
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        clean_base = normalize_base(sym[:-4])
                        vol = float(item.get("quoteVolume", 0.0))
                        temp_volumes[clean_base] = temp_volumes.get(clean_base, 0.0) + vol
        except Exception:
            pass

        # 2. Bybit USDT-M Linear
        try:
            r = self.session.get("https://api.bybit.com/v5/market/tickers?category=linear", timeout=3.5)
            if r.status_code == 200:
                for item in r.json().get("result", {}).get("list", []):
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        clean_base = normalize_base(sym[:-4])
                        vol = float(item.get("turnover24h", 0.0))
                        temp_volumes[clean_base] = temp_volumes.get(clean_base, 0.0) + vol
        except Exception:
            pass

        # 3. Bitget USDT-M Futures (Execution Anchor)
        try:
            r = self.session.get("https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures", timeout=3.5)
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    sym = item.get("symbol", "")
                    if sym.endswith("USDT"):
                        clean_base = normalize_base(sym[:-4])
                        vol = float(item.get("usdtVolume", 0.0))
                        price = float(item.get("lastPr", 0.0))
                        temp_volumes[clean_base] = temp_volumes.get(clean_base, 0.0) + vol
                        if price > 0:
                            temp_prices[clean_base] = price
        except Exception:
            pass

        with self.lock:
            for base, vol in temp_volumes.items():
                self._global_volume[base] = vol
                self._last_seen[base] = now

            for base, price in temp_prices.items():
                if base not in self._price_history:
                    self._price_history[base] = deque(maxlen=30)
                self._price_history[base].append((now, price))

    def _prune_stale_symbols(self):
        """Evicts symbols unseen for >15 minutes to guarantee <15MB RAM."""
        now = time.time()
        with self.lock:
            stale = [b for b, ts in self._last_seen.items() if now - ts > 900]
            for b in stale:
                self._global_volume.pop(b, None)
                self._price_history.pop(b, None)
                self._last_seen.pop(b, None)

    def get_candidate_coins(self, min_vol: float = 1_000_000.0) -> list:
        now = time.time()
        candidates = []

        with self.lock:
            for base, vol in self._global_volume.items():
                if vol < min_vol:
                    continue

                hist = self._price_history.get(base)
                if not hist or len(hist) < 4:
                    continue

                # Thread-safe copy of deque snapshot
                hist_copy = list(hist)
                curr_time, curr_price = hist_copy[-1]

                # Stale price check (must be fresh within 45 seconds)
                if now - curr_time > 45.0:
                    continue

                target_time = now - 120.0
                old_price = None

                for t, p in hist_copy:
                    if t >= target_time:
                        old_price = p
                        break

                if not old_price or old_price <= 0:
                    old_price = hist_copy[0][1]

                vel_2m = ((curr_price - old_price) / old_price) * 100.0

                # Velocity sweet spot: between 0.25% and 1.95% (excluding blown-out wicks >2.0%)
                if 0.25 <= abs(vel_2m) <= 1.95:
                    candidates.append({
                        "base": base,
                        "global_vol": vol,
                        "velocity_2m": round(vel_2m, 3),
                        "current_price": curr_price
                    })

        return candidates
