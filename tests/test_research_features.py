import unittest

from research import features


def candles(closes, start=1_800_000_000_000, turnover=None):
    rows = []
    for index, close in enumerate(closes):
        value = turnover[index] if turnover else 1000
        rows.append([
            str(start + index * 60_000),
            str(close), str(close + 0.01), str(close - 0.01), str(close),
            "10", str(value),
        ])
    return rows


class VolatilityTests(unittest.TestCase):
    def test_flag_uses_maximum_absolute_change(self):
        rows = candles([100.0] * 60 + [100.7])
        result = features.volatility_60(rows, now_ms=1_800_000_000_000 + 61 * 60_000)
        self.assertEqual(result["volatility_status"], "OK")
        self.assertAlmostEqual(result["max_abs_1m_pct"], 0.7, places=6)
        self.assertTrue(result["flag_0_7"])
        self.assertAlmostEqual(result["sum_abs_1m_pct"], 0.7, places=6)
        self.assertAlmostEqual(result["mean_abs_1m_pct"], 0.7 / 60, places=6)

    def test_flag_boundary_below_threshold(self):
        rows = candles([100.0] * 60 + [100.699])
        result = features.volatility_60(rows, now_ms=1_800_000_000_000 + 61 * 60_000)
        self.assertFalse(result["flag_0_7"])

    def test_insufficient_candles(self):
        rows = candles([100.0] * 60)
        result = features.volatility_60(rows, now_ms=1_800_000_000_000 + 61 * 60_000)
        self.assertEqual(result["volatility_status"], "INSUFFICIENT_CANDLES")
        self.assertIsNone(result["flag_0_7"])

    def test_gap_disables_flag(self):
        rows = candles([100.0] * 61 + [100.7])
        del rows[30]
        result = features.volatility_60(rows, now_ms=1_800_000_000_000 + 63 * 60_000)
        self.assertEqual(result["volatility_status"], "GAP")
        self.assertIsNone(result["flag_0_7"])

    def test_in_progress_candle_is_excluded(self):
        rows = candles([100.0] * 60 + [100.7])
        now = 1_800_000_000_000 + 61 * 60_000
        rows.append([str(now), "200", "200", "200", "200", "1", "1"])
        result = features.volatility_60(rows, now_ms=now)
        self.assertEqual(result["volatility_status"], "OK")
        self.assertAlmostEqual(result["max_abs_1m_pct"], 0.7, places=6)


class OtherFeatureTests(unittest.TestCase):
    def test_turnover_z_uses_prior_window(self):
        turnover = [1000 + index for index in range(60)] + [10_000]
        rows = candles([100.0] * 61, turnover=turnover)
        result = features.turnover_z(rows, now_ms=1_800_000_000_000 + 62 * 60_000)
        self.assertIsNotNone(result["turnover_z"])
        self.assertGreater(result["turnover_z"], 2)

    def test_oi_delta(self):
        payload = {"data": {"list": [
            {"timestamp": str(1_800_000_000_000 - (12 - index) * 300_000),
             "openInterest": str(100 + index * 10)}
            for index in range(13)
        ]}}
        expected = (220.0 / 190.0 - 1.0) * 100.0
        self.assertAlmostEqual(features.oi_delta(payload, 15), expected, places=6)

    def test_taker_imbalance(self):
        fills = [{"side": "buy", "size": "7", "price": "100", "ts": "1000"},
                 {"side": "sell", "size": "3", "price": "100", "ts": "2000"}]
        result = features.taker_imbalance(fills, now_ms=2000)
        self.assertAlmostEqual(result["imbalance"], 0.4, places=6)
        self.assertEqual(result["quality"], "SAMPLED")

    def test_absorption_proxy(self):
        result = features.absorption_proxy(0.5, 0.05, -5.0)
        self.assertTrue(result["absorbed"])
        self.assertEqual(result["direction"], "SHORT")
        self.assertFalse(features.absorption_proxy(0.1, 0.05, -5.0)["absorbed"])

    def test_basis_and_spread(self):
        self.assertAlmostEqual(features.basis_bps(100.0, 99.0), 101.010101, places=5)
        self.assertAlmostEqual(features.spread_bps(99.99, 100.01), 2.0, places=6)
        self.assertIsNone(features.spread_bps(100.0, 99.0))

    def test_depth_within_pct(self):
        levels = [[100.0, 10.0], [100.4, 10.0], [102.0, 100.0]]
        self.assertAlmostEqual(features.depth_within_pct(levels, 100.0, 0.005), 2004.0)

    def test_breakout_state(self):
        rows = candles([100.0 + index * 0.5 for index in range(70)])
        result = features.breakout_state(rows, now_ms=1_800_000_000_000 + 71 * 60_000)
        self.assertTrue(result["breakout_60m"])
        self.assertEqual(result["direction"], "LONG")
        self.assertFalse(result["failed_breakout"])


if __name__ == "__main__":
    unittest.main()
