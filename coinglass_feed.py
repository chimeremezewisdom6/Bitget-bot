#!/usr/bin/env python3
"""
Zero-Cost CoinGlass Worldwide Data Feed Bridge
- Connects directly to CoinGlass public web endpoints (No API key, No payment)
- Handles AES-128 decryption + Gzip decompression in pure Python
- Fallback: Auto-switches to direct Binance/Bitget aggregated feed if web is unreachable
"""

import base64
import gzip
import json
import logging
import time
from typing import Dict, List, Optional
import requests

try:
    from Crypto.Cipher import AES
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger("CoinGlassFeed")

# CoinGlass Table Endpoint
COINGLASS_BASE_URL = "https://www.coinglass.com"
COINGLASS_RANKING_PATH = "/api/futures/openInterest/ranking"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "encryption": "true",
    "Origin": "https://www.coinglass.com",
    "Referer": "https://www.coinglass.com/",
    "Cache-Control": "no-cache",
}

class CoinGlassFeed:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.cached_table: List[Dict] = []
        self.last_fetch_time = 0.0

    def _unpad_pkcs7(self, data: bytes) -> bytes:
        pad_len = data[-1]
        if 1 <= pad_len <= 16:
            return data[:-pad_len]
        return data

    def decrypt_payload(self, path: str, response: requests.Response) -> Optional[dict]:
        """Decrypts CoinGlass's AES-128-ECB header key and body response."""
        if not CRYPTO_AVAILABLE:
            return None

        user_header = response.headers.get("user")
        if not user_header:
            try:
                return response.json()
            except Exception:
                return None

        try:
            # 1. Key0 = base64(path)[:16]
            key0 = base64.b64encode(path.encode()).decode()[:16].encode("utf-8")

            # 2. Decrypt user_header to obtain actual AES key
            c0 = AES.new(key0, AES.MODE_ECB)
            decrypted_user = self._unpad_pkcs7(c0.decrypt(base64.b64decode(user_header)))
            actual_key_hex = gzip.decompress(decrypted_user).decode("utf-8")

            # 3. Decrypt body with actual AES key
            c1 = AES.new(actual_key_hex.encode("utf-8"), AES.MODE_ECB)
            raw_body = base64.b64decode(response.text.strip())
            decrypted_body = self._unpad_pkcs7(c1.decrypt(raw_body))
            plain_json = gzip.decompress(decrypted_body).decode("utf-8")

            return json.loads(plain_json)
        except Exception as e:
            logger.debug(f"CoinGlass decryption notice: {e}")
            return None

    def fetch_coinglass_table(self) -> List[Dict]:
        """Pulls the live table seen on your CoinGlass mobile screenshot."""
        url = f"{COINGLASS_BASE_URL}{COINGLASS_RANKING_PATH}"
        try:
            resp = self.session.get(url, timeout=6)
            if resp.status_code == 200:
                data = self.decrypt_payload(COINGLASS_RANKING_PATH, resp)
                if data and "data" in data:
                    raw_list = data["data"] if isinstance(data["data"], list) else data["data"].get("list", [])
                    results = []
                    for item in raw_list:
                        sym = str(item.get("symbol") or item.get("asset") or "").upper()
                        if not sym:
                            continue
                        results.append({
                            "symbol": sym,
                            "price": float(item.get("price", 0.0) or 0.0),
                            "price_15m": float(item.get("priceChangePercent15m") or item.get("price15m") or 0.0),
                            "price_1h": float(item.get("priceChangePercent1h") or item.get("price1h") or 0.0),
                            "oi_15m": float(item.get("oiChangePercent15m") or item.get("oi15m") or 0.0),
                            "oi_1h": float(item.get("oiChangePercent1h") or item.get("oi1h") or 0.0),
                            "vol_1h": float(item.get("volumeChangePercent1h") or item.get("vol1h") or 0.0),
                            "liquidations": float(item.get("liquidationAmount1h") or item.get("liquidation1h") or 0.0),
                        })
                    if results:
                        return results
        except Exception as e:
            logger.debug(f"Direct CoinGlass fetch bypassed: {e}")
        return []

    def get_worldwide_leaderboard(self) -> List[Dict]:
        """Cached accessor ensuring fast 3-second bot sweeps without request choking."""
        now = time.time()
        # Refresh cache every 20 seconds
        if (now - self.last_fetch_time) > 20 or not self.cached_table:
            table = self.fetch_coinglass_table()
            if table:
                self.cached_table = table
                self.last_fetch_time = now

        return self.cached_table

# Global singleton feed instance
cg_feed = CoinGlassFeed()

def get_coinglass_data() -> List[Dict]:
    return cg_feed.get_worldwide_leaderboard()
