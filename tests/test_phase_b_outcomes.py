import unittest

from research import outcomes


START = 1_800_000_000_000


def candles(count=180, *, start=START):
    rows = []
    price = 100.0
    for index in range(count):
        price = 100.0 + index * 0.1
        rows.append({
            "ts": start + index * 60_000,
            "open": price,
            "high": price + 0.05,
            "low": price - 0.05,
            "close": price + 0.02,
            "base_volume": 1.0,
            "quote_turnover": 1000.0 + index,
        })
    return rows


def event(ts_ms=START + 10 * 60_000):
    return {
        "event_id": "taker:BTCUSDT:1",
        "symbol": "BTCUSDT",
        "type": "taker_aggression",
        "direction": "LONG",
        "ts_ms": ts_ms,
        "features": {"spread_bps": 5.0, "taker_fee_bps": 6.0, "funding_rate": 0.0001},
    }


class PhaseBOutcomeTests(unittest.TestCase):
    def test_costs_and_duration_are_explicit(self):
        scored = outcomes.score_event(
            event(), candles(), horizon_min=15,
            fee_bps=6.0, spread_bps=5.0, slippage_bps=2.0, funding_bps=1.0,
            now_ms=START + 200 * 60_000,
        )
        self.assertIsNotNone(scored)
        self.assertEqual(scored["costs_bps"]["fee"], 12.0)
        self.assertEqual(scored["costs_bps"]["spread"], 5.0)
        self.assertEqual(scored["costs_bps"]["slippage"], 2.0)
        self.assertEqual(scored["costs_bps"]["funding"], 1.0)
        self.assertEqual(scored["costs_bps"]["total"], 20.0)
        self.assertAlmostEqual(scored["net_bps"], scored["gross_bps"] - 20.0, places=4)
        self.assertIn("time_to_mfe_min", scored)
        self.assertIn("time_to_mae_min", scored)

    def test_missing_funding_does_not_fabricate_net(self):
        scored = outcomes.score_event(
            event(), candles(), horizon_min=15,
            fee_bps=6.0, spread_bps=5.0, slippage_bps=2.0,
            funding_bps=None, now_ms=START + 200 * 60_000,
        )
        self.assertIsNotNone(scored)
        self.assertIsNone(scored["net_bps"])
        self.assertEqual(scored["funding_status"], "MISSING")
        self.assertIsNotNone(scored["net_ex_funding_bps"])
        self.assertIsNone(scored["costs_bps"]["funding"])
        self.assertIsNone(scored["costs_bps"]["total"])

    def test_insufficient_forward_data_returns_none(self):
        scored = outcomes.score_event(
            event(ts_ms=START + 175 * 60_000), candles(), horizon_min=15,
            now_ms=START + 200 * 60_000,
        )
        self.assertIsNone(scored)

    def test_non_overlapping_selection(self):
        first = {"symbol": "BTCUSDT", "entry_ts_ms": 0, "exit_ts_ms": 15 * 60_000}
        second = {"symbol": "BTCUSDT", "entry_ts_ms": 5 * 60_000, "exit_ts_ms": 20 * 60_000}
        third = {"symbol": "BTCUSDT", "entry_ts_ms": 15 * 60_000, "exit_ts_ms": 30 * 60_000}
        accepted, skipped = outcomes.select_non_overlapping([first, second, third])
        self.assertEqual(len(accepted), 2)
        self.assertEqual(skipped, 1)
        self.assertEqual(accepted[1], third)


if __name__ == "__main__":
    unittest.main()
