import unittest

from research.features import volatility_60


START = 1_800_000_000_000


def make_candles(changes):
    rows = []
    price = 100.0
    for index, change in enumerate(changes):
        open_price = price
        close_price = price * (1.0 + change / 100.0)
        rows.append({
            "ts": START + index * 60_000,
            "open": open_price,
            "high": max(open_price, close_price) + 0.001,
            "low": min(open_price, close_price) - 0.001,
            "close": close_price,
            "base_volume": 1.0,
            "quote_turnover": 1000.0,
        })
        price = close_price
    return rows


class PhaseBVolatilityTests(unittest.TestCase):
    def test_threshold_is_exactly_point_seven_percent(self):
        changes = [0.01] * 61
        changes[30] = 0.7
        result = volatility_60(make_candles(changes), now_ms=START + 61 * 60_000)
        self.assertEqual(result["flag_0_7"], True)
        self.assertAlmostEqual(result["max_abs_1m_pct"], 0.7, places=4)

    def test_below_threshold_is_false(self):
        changes = [0.01] * 61
        changes[30] = 0.69
        result = volatility_60(make_candles(changes), now_ms=START + 61 * 60_000)
        self.assertEqual(result["flag_0_7"], False)

    def test_gap_produces_gap_status(self):
        changes = [0.01] * 62
        changes[30] = 0.7
        rows = make_candles(changes)
        rows.pop(30)
        result = volatility_60(rows, now_ms=START + 62 * 60_000)
        self.assertEqual(result["volatility_status"], "GAP")
        self.assertIsNone(result["flag_0_7"])

    def test_insufficient_history_produces_no_flag(self):
        result = volatility_60(make_candles([0.01] * 60), now_ms=START + 61 * 60_000)
        self.assertEqual(result["volatility_status"], "INSUFFICIENT_CANDLES")
        self.assertIsNone(result["flag_0_7"])

    def test_in_progress_candle_is_excluded(self):
        changes = [0.01] * 61
        changes[30] = 0.7
        rows = make_candles(changes)
        rows.append({
            "ts": START + 61 * 60_000, "open": 100.0, "high": 200.0,
            "low": 50.0, "close": 200.0, "base_volume": 1.0, "quote_turnover": 1000.0,
        })
        result = volatility_60(rows, now_ms=START + 61 * 60_000)
        self.assertEqual(result["flag_0_7"], True)


if __name__ == "__main__":
    unittest.main()
