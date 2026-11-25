import tempfile
import unittest
from pathlib import Path

from collector import cycle
from research.dataset import load_bundle

from fakes import FakeClient

NOW = 1_800_000_000_000
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def instruments(*, fee: bool = True):
    rows = []
    for symbol in SYMBOLS:
        row = {
            "symbol": symbol, "baseCoin": symbol.replace("USDT", ""), "quoteCoin": "USDT",
            "status": "online", "type": "perpetual", "instrumentType": "crypto",
            "symbolType": "crypto",
        }
        if fee:
            row["takerFeeRate"] = "0.0006"
        rows.append(row)
    return {"code": "00000", "data": rows}


def tickers():
    rows = []
    for index, symbol in enumerate(SYMBOLS):
        rows.append({
            "symbol": symbol,
            "turnover24h": str(50_000_000 - index * 10_000_000),
            "bid1Price": "99.99", "ask1Price": "100.01", "lastPrice": "100.0",
        })
    return {"code": "00000", "data": rows}


def spot_instruments():
    return {"code": "00000", "data": [
        {"symbol": symbol, "status": "online", "symbolType": "crypto", "quoteCoin": "USDT"}
        for symbol in SYMBOLS
    ]}


def spot_tickers():
    return {"code": "00000", "data": [
        {"symbol": symbol, "bid1Price": "99.0", "ask1Price": "99.1",
         "lastPrice": "99.05", "turnover24h": "1000000"}
        for symbol in SYMBOLS
    ]}


def candles_payload():
    rows = []
    for index in range(70):
        price = 100.0 + index * 0.5
        turnover = "5000" if index == 69 else "1000"
        rows.append([
            str(NOW - 70 * 60_000 + index * 60_000),
            str(price), str(price + 0.1), str(price - 0.1), str(price), "10", turnover,
        ])
    return {"code": "00000", "data": rows}


def oi_payload():
    rows = []
    for index in range(13):
        rows.append({
            "timestamp": str(NOW - (12 - index) * 300_000),
            "openInterest": str(1_000 + index * 10),
            "oneSideOpenInterest": str(500 + index * 5),
            "openInterestValue": str(100_000 + index * 1_000),
        })
    return {"code": "00000", "data": {"list": rows}}


def fills_payload():
    rows = []
    for index in range(100):
        rows.append({
            "side": "buy" if index < 70 else "sell",
            "size": "1", "price": "100.0",
            "ts": str(NOW - 120_000 + index * 1_000),
        })
    return {"code": "00000", "data": rows}


def book_payload():
    return {"code": "00000", "data": {
        "b": [[99.99, 1_000.0], [99.9, 500.0]],
        "a": [[100.01, 1_000.0], [100.1, 500.0]],
        "ts": str(NOW),
    }}


def make_client(fail_symbol="SOLUSDT", *, fee: bool = True):
    def candles_route(params):
        if params.get("category") == "SPOT":
            return candles_payload()
        if params.get("symbol") == fail_symbol:
            return RuntimeError("candles down")
        return candles_payload()

    return FakeClient({
        ("/api/v3/market/instruments", "USDT-FUTURES"): instruments(fee=fee),
        ("/api/v3/market/tickers", "USDT-FUTURES"): tickers(),
        ("/api/v3/market/instruments", "SPOT"): spot_instruments(),
        ("/api/v3/market/tickers", "SPOT"): spot_tickers(),
        "/api/v3/market/orderbook": book_payload(),
        "/api/v3/market/candles": candles_route,
        "/api/v3/market/fills": fills_payload(),
        "/api/v3/market/open-interest-history": oi_payload(),
        "/api/v3/market/liquidations": {"code": "00000", "data": {"list": []}},
    })


class CycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_cycle_writes_bundle_and_truthful_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = await cycle.run_cycle(
                client=make_client(),
                now_ms=NOW,
                config=cycle.Config(
                    top_n=10, max_spread_bps=100, min_depth_usdt=0,
                    spot_max_symbols=3, micro_enabled=False,
                ),
                out_dir=tmp,
            )
            self.assertEqual(result.outcome, "partial")
            self.assertEqual(result.symbols_requested, 3)
            self.assertEqual(result.symbols_ok, 2)
            self.assertEqual(result.symbols_failed, 1)
            self.assertTrue(Path(result.bundle_path).exists())
            self.assertEqual(result.manifest["counts"]["features"], 2)
            self.assertEqual(result.manifest["counts"]["universe"], 3)
            self.assertEqual(result.manifest["quality"]["symbols_ok"], 2)
            self.assertGreater(result.events, 0)
            self.assertGreater(result.metrics["requests"], 0)
            loaded = load_bundle(result.bundle_path)
            self.assertEqual(len(loaded["rows"]["features"]), 2)
            self.assertEqual(len(loaded["rows"]["candles"]), result.candles_new)

    async def test_public_fee_metadata_is_recorded_without_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = await cycle.run_cycle(
                client=make_client(),
                now_ms=NOW,
                config=cycle.Config(
                    top_n=10, max_spread_bps=100, min_depth_usdt=0,
                    spot_max_symbols=3, micro_enabled=False,
                ),
                out_dir=tmp,
            )
            loaded = load_bundle(result.bundle_path)
        self.assertEqual(loaded["meta"]["data_source"], "Bitget USDT-FUTURES public market data")
        self.assertEqual(loaded["meta"]["fee_estimated"], 0)
        self.assertEqual(result.metrics["fee_estimated"], 0)
        self.assertNotIn("auth_status", loaded["meta"])
        self.assertTrue(loaded["rows"]["features"])
        self.assertTrue(all(row["fee_status"] == "PROVIDED" for row in loaded["rows"]["features"]))
        for row in loaded["rows"]["features"]:
            self.assertAlmostEqual(row["taker_fee_bps"], 6.0, places=6)

    async def test_missing_public_fee_is_marked_fee_estimated(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = await cycle.run_cycle(
                client=make_client(fee=False),
                now_ms=NOW,
                config=cycle.Config(
                    top_n=10, max_spread_bps=100, min_depth_usdt=0,
                    spot_max_symbols=3, micro_enabled=False,
                ),
                out_dir=tmp,
            )
            loaded = load_bundle(result.bundle_path)
        self.assertEqual(loaded["meta"]["fee_estimated"], len(loaded["rows"]["features"]))
        self.assertEqual(result.metrics["fee_estimated"], len(loaded["rows"]["features"]))
        self.assertTrue(loaded["rows"]["features"])
        self.assertTrue(all(row["fee_status"] == "FEE_ESTIMATED" for row in loaded["rows"]["features"]))
        self.assertTrue(all(row["taker_fee_bps"] is None for row in loaded["rows"]["features"]))

    async def test_slot_is_aligned_to_five_minutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = await cycle.run_cycle(
                client=make_client(), now_ms=NOW + 123_456,
                config=cycle.Config(top_n=10, max_spread_bps=100, min_depth_usdt=0),
                out_dir=tmp,
            )
        self.assertEqual(result.slot_ms, ((NOW + 123_456) // cycle.SLOT_MS) * cycle.SLOT_MS)

    async def test_universe_failure_writes_error_bundle(self):
        client = FakeClient({
            ("/api/v3/market/instruments", "USDT-FUTURES"): RuntimeError("down"),
        })
        with tempfile.TemporaryDirectory() as tmp:
            result = await cycle.run_cycle(client=client, now_ms=NOW, out_dir=tmp)
            self.assertEqual(result.outcome, "failed")
            self.assertIsNotNone(result.bundle_path)
            loaded = load_bundle(result.bundle_path)
        self.assertEqual(loaded["rows"]["errors"][0]["source"], "cycle")

    async def test_truncation_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = await cycle.run_cycle(
                client=make_client(),
                now_ms=NOW,
                config=cycle.Config(
                    top_n=10, max_spread_bps=100, min_depth_usdt=0,
                    bundle_max_bytes=200,
                ),
                out_dir=tmp,
            )
        self.assertTrue(result.manifest["quality"]["truncated_sections"])


if __name__ == "__main__":
    unittest.main()
