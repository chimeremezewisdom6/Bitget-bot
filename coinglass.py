from __future__ import annotations

import logging
import os

import aiohttp

log = logging.getLogger("coinglass")

FIELD_SYMBOL = "symbol"
FIELD_BIDS = "bids_usd"
FIELD_ASKS = "asks_usd"

class CoinGlassClient:
    def __init__(self, api_key: str, url: str) -> None:
        self.api_key, self.url = api_key, url

    @classmethod
    def from_env(cls):
        key, url = os.getenv("COINGLASS_API_KEY"), os.getenv("COINGLASS_DEPTH_URL")
        return cls(key, url) if key and url else None

    async def aggregated_depth(self) -> dict | None:
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(self.url, headers={"CG-API-KEY": self.api_key, "accept": "application/json"}) as r:
                    r.raise_for_status()
                    payload = await r.json()
            out = {}
            for row in payload.get("data") or []:
                out[str(row[FIELD_SYMBOL]).upper()] = (float(row[FIELD_BIDS]), float(row[FIELD_ASKS]))
            return out or None
        except Exception as e:
            log.warning("CoinGlass unavailable, falling back to full CCXT scan: %s", e)
            return None
