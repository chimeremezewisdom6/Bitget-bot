# market_math.py
import asyncio
import aiohttp

class MarketMath:
    @staticmethod
    def parse_flow_candles(candles: list) -> dict:
        """
        Calculates:
        1. Minute-by-minute true acceleration (V5 > V4, late > early).
        2. Redmi A7 supply lock: net accumulated volume over 15 minutes.
        Candle structure: [ts, open, high, low, close, vol, close_time, quote_vol, trades, taker_base, taker_quote, _]
        """
        if not candles or len(candles) < 5:
            return None

        minute_buys = []
        minute_sells = []
        minute_deltas = []
        minute_moves = []

        for c in candles:
            open_p, close_p = float(c[1]), float(c[4])
            quote_vol = float(c[7])
            taker_buy_usd = float(c[10])
            taker_sell_usd = max(0.0, quote_vol - taker_buy_usd)

            net_force = taker_buy_usd - taker_sell_usd
            pct_move = ((close_p - open_p) / open_p) * 100.0

            minute_buys.append(taker_buy_usd)
            minute_sells.append(taker_sell_usd)
            minute_deltas.append(net_force)
            minute_moves.append(pct_move)

        total_5m_move = sum(minute_moves[-5:])
        v5 = minute_moves[-5:]
        b5 = minute_buys[-5:]

        # True acceleration: late stage velocity > early stage, and current minute accelerating
        is_accelerating = (
            (total_5m_move >= 1.20) and
            (v5[-1] > v5[-2]) and
            (b5[-1] + b5[-2] > b5[0] + b5[1]) and
            (minute_deltas[-1] > 0)
        )

        # 15-Minute Redmi A7 inventory squeeze ratio
        total_vol = sum(minute_buys) + sum(minute_sells)
        net_locked = sum(minute_deltas)
        squeeze_ratio = (net_locked / max(total_vol, 1.0)) * 100.0

        return {
            "is_accelerating": is_accelerating,
            "total_5m_move": round(total_5m_move, 2),
            "squeeze_ratio": round(squeeze_ratio, 2),
            "last_minute_buy_force": b5[-1],
            "last_minute_net_force": minute_deltas[-1]
        }

    @staticmethod
    def aggregate_8_exchanges(venues_data: list, current_run_rate: float) -> dict:
        """
        Sums resting order book limit orders within +1.5% across all 8 exchanges.
        Calculates clearance ratio and limit order vacuum gaps.
        """
        total_ask_usd = 0.0
        total_bid_usd = 0.0
        all_gaps = []
        reporting_venues = []

        for name, bids, asks in venues_data:
            if not bids or not asks:
                continue

            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            mid = (best_bid + best_ask) / 2.0
            upper_bound = mid * 1.015

            valid_asks = [[float(p), float(q)] for p, q in asks if float(p) <= upper_bound]
            valid_bids = [[float(p), float(q)] for p, q in bids if float(p) >= mid * 0.985]

            total_ask_usd += sum(p * q for p, q in valid_asks)
            total_bid_usd += sum(p * q for p, q in valid_bids)
            reporting_venues.append(name)

            if len(valid_asks) > 1:
                prices = [p for p, _ in valid_asks]
                gaps = [abs(prices[i+1] - prices[i]) / prices[i] * 100.0 for i in range(len(prices) - 1)]
                all_gaps.append(sum(gaps) / len(gaps))

        projected_2m_flow = current_run_rate * 2.0
        clearance_ratio = projected_2m_flow / max(total_ask_usd, 1.0)
        avg_gap = sum(all_gaps) / max(len(all_gaps), 1)

        can_sweep = (clearance_ratio >= 1.25) and (len(reporting_venues) >= 2)

        return {
            "can_sweep": can_sweep,
            "clearance_ratio": round(clearance_ratio, 2),
            "total_ask_usd": round(total_ask_usd, 2),
            "total_bid_usd": round(total_bid_usd, 2),
            "avg_gap": round(avg_gap, 4),
            "venues_count": len(reporting_venues),
            "reporting_venues": reporting_venues
        }


class EightExchangeProbe:
    """Non-blocking parallel order book reader for the Big 8 exchanges (<250ms)."""
    def __init__(self, session: aiohttp.ClientSession):
        self.s = session

    async def _binance(self, base: str):
        try:
            url = f"https://fapi.binance.com/fapi/v1/depth?symbol={base}USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = await r.json()
                    return ("binance", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _okx(self, base: str):
        try:
            url = f"https://www.okx.com/api/v5/market/books?instId={base}-USDT-SWAP&sz=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", [{}])[0]
                    return ("okx", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _bybit(self, base: str):
        try:
            url = f"https://api.bybit.com/v5/market/orderbook?category=linear&symbol={base}USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("result", {})
                    return ("bybit", d.get("b", []), d.get("a", []))
        except Exception: pass
        return None

    async def _gate(self, base: str):
        try:
            url = f"https://api.gateio.ws/api/v4/futures/usdt/order_book?contract={base}_USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = await r.json()
                    return ("gate", [[x["p"], x["s"]] for x in d.get("bids", [])], [[x["p"], x["s"]] for x in d.get("asks", [])])
        except Exception: pass
        return None

    async def _mexc(self, base: str):
        try:
            url = f"https://contract.mexc.com/api/v1/contract/depth/{base}_USDT?limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    return ("mexc", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _kucoin(self, base: str):
        try:
            url = f"https://api-futures.kucoin.com/api/v1/level2/depth20?symbol={base}USDTM"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    return ("kucoin", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _bingx(self, base: str):
        try:
            url = f"https://open-api.bingx.com/openApi/swap/v2/quote/depth?symbol={base}-USDT&limit=20"
            async with self.s.get(url, timeout=0.8) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    return ("bingx", d.get("bids", []), d.get("asks", []))
        except Exception: pass
        return None

    async def _hyperliquid(self, base: str):
        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "l2Book", "coin": base}
            async with self.s.post(url, json=payload, timeout=0.8) as r:
                if r.status == 200:
                    d = await r.json()
                    levels = d.get("levels", [[], []])
                    return ("hyperliquid", [[x["px"], x["sz"]] for x in levels[0]], [[x["px"], x["sz"]] for x in levels[1]])
        except Exception: pass
        return None

    async def query_all_venues(self, base: str) -> list:
        tasks = [
            self._binance(base), self._okx(base), self._bybit(base), self._gate(base),
            self._mexc(base), self._kucoin(base), self._bingx(base), self._hyperliquid(base)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, tuple) and r is not None]
