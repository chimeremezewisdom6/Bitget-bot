import unittest

from research import events, outcomes

START = 1_800_000_000_000


def candles():
    closes = [100.0, 100.0, 100.5, 100.8, 101.0, 101.2, 101.0, 101.0, 101.0, 101.0]
    rows = []
    for index, close in enumerate(closes):
        rows.append([
            str(START + index * 60_000),
            str(close), str(close + 0.2), str(close - 0.2), str(close), "10", "1000",
        ])
    return rows


def event(direction):
    return events.Event(
        event_id=f"e:{direction}", type="turnover_expansion", version="1",
        symbol="BTCUSDT", ts_ms=START, direction=direction,
    )


class OutcomeTests(unittest.TestCase):
    def test_long_next_bar_entry_and_costs(self):
        result = outcomes.score_event(
            event("LONG"), candles(), horizon_min=5, fee_bps=6, spread_bps=2,
            funding_bps=0.0, now_ms=START + 20 * 60_000,
        )
        self.assertEqual(result["entry_ts_ms"], START + 60_000)
        self.assertEqual(result["entry_price"], 100.0)
        self.assertEqual(result["exit_price"], 101.2)
        self.assertAlmostEqual(result["gross_bps"], 120.0, places=6)
        self.assertAlmostEqual(result["costs_bps"]["total"], 14.0, places=6)
        self.assertAlmostEqual(result["net_bps"], 106.0, places=6)

    def test_short_reverses_gross(self):
        result = outcomes.score_event(
            event("SHORT"), candles(), horizon_min=5, fee_bps=6, spread_bps=2,
            funding_bps=0.0, now_ms=START + 20 * 60_000,
        )
        self.assertAlmostEqual(result["gross_bps"], -120.0, places=6)
        self.assertAlmostEqual(result["net_bps"], -134.0, places=6)

    def test_mfe_and_mae(self):
        result = outcomes.score_event(
            event("LONG"), candles(), horizon_min=5, fee_bps=0,
            funding_bps=0.0, now_ms=START + 20 * 60_000,
        )
        self.assertAlmostEqual(result["mfe_bps"], 140.0, places=6)
        self.assertAlmostEqual(result["mae_bps"], -20.0, places=6)

    def test_insufficient_forward_data_returns_none(self):
        self.assertIsNone(outcomes.score_event(
            event("LONG"), candles(), horizon_min=20, now_ms=START + 20 * 60_000,
        ))

    def test_exact_minute_horizon_uses_entry_plus_horizon_minus_one(self):
        one = outcomes.score_event(
            event("LONG"), candles(), horizon_min=1, fee_bps=0,
            funding_bps=0.0, now_ms=START + 20 * 60_000,
        )
        two = outcomes.score_event(
            event("LONG"), candles(), horizon_min=2, fee_bps=0,
            funding_bps=0.0, now_ms=START + 20 * 60_000,
        )
        self.assertEqual(one["exit_ts_ms"], START + 60_000)
        self.assertAlmostEqual(one["gross_bps"], 0.0, places=6)
        self.assertEqual(two["exit_ts_ms"], START + 120_000)
        self.assertAlmostEqual(two["gross_bps"], 50.0, places=6)

    def test_spread_is_charged_once_as_full_round_trip(self):
        flat = [
            [str(START + index * 60_000), "100", "100.1", "99.9", "100", "1", "1000"]
            for index in range(10)
        ]
        result = outcomes.score_event(
            event("LONG"), flat, horizon_min=5, fee_bps=0, spread_bps=5,
            funding_bps=0.0, now_ms=START + 20 * 60_000,
        )
        self.assertAlmostEqual(result["costs_bps"]["spread"], 5.0, places=6)
        self.assertAlmostEqual(result["costs_bps"]["total"], 5.0, places=6)
        self.assertAlmostEqual(result["net_bps"], -5.0, places=6)

    def test_funding_credit_and_cost_depend_on_direction(self):
        long = outcomes.score_event(
            event("LONG"), candles(), horizon_min=5, fee_bps=0,
            funding_bps=2.0, now_ms=START + 20 * 60_000,
        )
        short = outcomes.score_event(
            event("SHORT"), candles(), horizon_min=5, fee_bps=0,
            funding_bps=-2.0, now_ms=START + 20 * 60_000,
        )
        self.assertAlmostEqual(long["costs_bps"]["funding"], 2.0, places=6)
        self.assertAlmostEqual(short["costs_bps"]["funding"], -2.0, places=6)
        self.assertAlmostEqual(long["net_bps"], long["gross_bps"] - 2.0, places=6)
        self.assertAlmostEqual(short["net_bps"], short["gross_bps"] + 2.0, places=6)

    def test_missing_funding_is_not_treated_as_zero(self):
        result = outcomes.score_event(
            event("LONG"), candles(), horizon_min=5, fee_bps=0,
            now_ms=START + 20 * 60_000,
        )
        self.assertIsNone(result["costs_bps"]["funding"])
        self.assertIsNone(result["costs_bps"]["total"])
        self.assertIsNone(result["net_bps"])
        self.assertEqual(result["funding_status"], "MISSING")

    def test_entry_is_strictly_after_event(self):
        later = events.Event(
            event_id="e", type="x", version="1", symbol="BTCUSDT",
            ts_ms=START + 60_000, direction="LONG",
        )
        result = outcomes.score_event(
            later, candles(), horizon_min=1, fee_bps=0, now_ms=START + 20 * 60_000,
        )
        self.assertEqual(result["entry_ts_ms"], START + 120_000)


if __name__ == "__main__":
    unittest.main()
