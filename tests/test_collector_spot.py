import unittest

from collector import spot, universe

from fakes import FakeClient


def candles(start_ms, count=70, base=100.0, step=0.1):
    rows = []
    for index in range(count):
        price = base + index * step
        turnover = "5000" if index == count - 1 else str(1000 + index * 10)
        rows.append([
            str(start_ms + index * 60_000),
            str(price), str(price + 0.05), str(price - 0.05), str(price),
            "10", turnover,
        ])
    return rows


def perp(symbol, base):
    return universe.Perp(
        symbol=symbol, base=base, quote="USDT", turnover24h=10_000_000,
        last=100.0, bid=100.0, ask=100.1, spread_bps=10.0,
        bid_depth_usdt=50_000, ask_depth_usdt=50_000,
    )


class SpotTests(unittest.IsolatedAsyncioTestCase):
    def test_spot_instrument_map_excludes_stock_tokens(self):
        rows = [
            {"symbol": "BTCUSDT", "status": "online", "symbolType": "crypto", "quoteCoin": "USDT"},
            {"symbol": "STOCKUSDT", "status": "online", "symbolType": "stock", "quoteCoin": "USDT"},
        ]
        mapped = spot.spot_instruments_map(rows)
        self.assertIn("BTCUSDT", mapped)
        self.assertNotIn("STOCKUSDT", mapped)

    def test_map_spot_requires_exact_symbol(self):
        self.assertEqual(spot.map_spot("BTC", {"BTCUSDT": {}}), "BTCUSDT")
        self.assertIsNone(spot.map_spot("NOPE", {"BTCUSDT": {}}))

    async def test_snapshot_computes_returns_and_basis(self):
        now = 1_800_000_000_000
        routes = {
            "/api/v3/market/instruments": {"code": "00000", "data": [
                {"symbol": "BTCUSDT", "status": "online", "symbolType": "crypto", "quoteCoin": "USDT"},
            ]},
            "/api/v3/market/tickers": {"code": "00000", "data": [
                {"symbol": "BTCUSDT", "bid1Price": "99.0", "ask1Price": "99.1",
                 "lastPrice": "99.05", "turnover24h": "123456"},
            ]},
            "/api/v3/market/candles": {"code": "00000", "data": candles(now - 70 * 60_000)},
        }
        client = FakeClient(routes)
        rows = await spot.spot_snapshot(client, [perp("BTCUSDT", "BTC")], now_ms=now)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row.error)
        self.assertIsNotNone(row.ret_5m_pct)
        self.assertIsNotNone(row.turnover_z)
        self.assertAlmostEqual(row.basis_bps, (100.05 / 99.05 - 1) * 10_000, places=3)

    async def test_unmapped_spot_is_explicit(self):
        now = 1_800_000_000_000
        routes = {
            "/api/v3/market/instruments": {"code": "00000", "data": []},
            "/api/v3/market/tickers": {"code": "00000", "data": []},
        }
        client = FakeClient(routes)
        rows = await spot.spot_snapshot(client, [perp("NOPEUSDT", "NOPE")], now_ms=now)
        self.assertEqual(rows[0].error, "SPOT_UNMAPPED")
        self.assertIsNone(rows[0].basis_bps)


if __name__ == "__main__":
    unittest.main()
