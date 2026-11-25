import unittest

from collector import micro

from fakes import FakeClient, FakeClock, make_sleep


def book_payload(symbol):
    return {"code": "00000", "data": {
        "b": [[100.0, 10.0], [99.9, 10.0]],
        "a": [[100.1, 10.0], [100.2, 10.0]],
        "ts": "1800000000000",
    }}


def fills_payload(symbol):
    return {"code": "00000", "data": [
        {"side": "buy", "size": "1", "price": "100.0", "ts": "1800000000000"},
        {"side": "sell", "size": "0.5", "price": "100.0", "ts": "1800000000000"},
    ]}


class MicroTests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_bounded_samples_and_metrics(self):
        clock = FakeClock(1_800_000_000.0)
        client = FakeClient({
            "/api/v3/market/orderbook": lambda params: book_payload(params["symbol"]),
            "/api/v3/market/fills": lambda params: fills_payload(params["symbol"]),
        })
        result = await micro.capture(
            client, ["BTCUSDT", "ETHUSDT"],
            seconds=4, interval_s=2,
            now_fn=clock, sleep=make_sleep(clock),
        )
        self.assertEqual(result["target_samples"], 2)
        self.assertEqual(result["samples_ok"], 2)
        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(client.stats.requests, 8)
        self.assertEqual(result["metrics"]["max_gap_ms"], 2000.0)

    async def test_symbol_error_is_reported_without_stopping(self):
        clock = FakeClock(1_800_000_000.0)

        def book(params):
            if params["symbol"] == "ETHUSDT":
                return RuntimeError("book down")
            return book_payload(params["symbol"])

        client = FakeClient({
            "/api/v3/market/orderbook": book,
            "/api/v3/market/fills": lambda params: fills_payload(params["symbol"]),
        })
        result = await micro.capture(
            client, ["BTCUSDT", "ETHUSDT"],
            seconds=2, interval_s=2,
            now_fn=clock, sleep=make_sleep(clock),
        )
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["symbol"], "ETHUSDT")

    async def test_capture_is_limited_to_five_symbols(self):
        clock = FakeClock(1_800_000_000.0)
        client = FakeClient({
            "/api/v3/market/orderbook": lambda params: book_payload(params["symbol"]),
            "/api/v3/market/fills": lambda params: fills_payload(params["symbol"]),
        })
        symbols = ["A", "B", "C", "D", "E", "F", "G"]
        result = await micro.capture(
            client, symbols, seconds=2, interval_s=2,
            now_fn=clock, sleep=make_sleep(clock),
        )
        self.assertEqual(result["symbols"], symbols[:5])


if __name__ == "__main__":
    unittest.main()
