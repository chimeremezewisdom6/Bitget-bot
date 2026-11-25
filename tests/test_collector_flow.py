import unittest

from collector.flow import collect_flow, flow_snapshot

from fakes import FakeClient


def fills(now_ms, count=100, buy_ratio=0.7, span_ms=120_000):
    rows = []
    for index in range(count):
        side = "buy" if index / max(1, count) < buy_ratio else "sell"
        rows.append({
            "side": side,
            "size": "1.0",
            "price": "100.0",
            "ts": str(now_ms - span_ms + int(span_ms * index / max(1, count))),
        })
    return rows


class FlowTests(unittest.IsolatedAsyncioTestCase):
    def test_imbalance_and_coverage_are_reported(self):
        now = 1_800_000_000_000
        row = flow_snapshot({"code": "00000", "data": fills(now)}, "BTCUSDT", now_ms=now)
        self.assertGreater(row["imbalance"], 0)
        self.assertGreater(row["coverage_pct"], 20)
        self.assertEqual(row["quality"], "ADEQUATE")

    def test_empty_fills_are_explicit(self):
        row = flow_snapshot({"code": "00000", "data": []}, "BTCUSDT", now_ms=1)
        self.assertEqual(row["quality"], "EMPTY")
        self.assertIsNone(row["imbalance"])

    def test_stale_fills_are_flagged(self):
        now = 1_800_000_000_000
        row = flow_snapshot(
            {"code": "00000", "data": fills(now - 200_000, count=10)},
            "BTCUSDT", now_ms=now,
        )
        self.assertEqual(row["quality"], "STALE")

    def test_error_payload_is_flagged(self):
        row = flow_snapshot(RuntimeError("boom"), "BTCUSDT")
        self.assertEqual(row["quality"], "ERROR")
        self.assertEqual(row["error"], "RuntimeError")

    async def test_collect_flow_preserves_symbol_order(self):
        now = 1_800_000_000_000
        client = FakeClient({
            "/api/v3/market/fills": lambda params: {
                "code": "00000", "data": fills(now, count=20, span_ms=10_000),
            },
        })
        rows = await collect_flow(client, ["BTCUSDT", "ETHUSDT"], now_ms=now)
        self.assertEqual([row["symbol"] for row in rows], ["BTCUSDT", "ETHUSDT"])


if __name__ == "__main__":
    unittest.main()
