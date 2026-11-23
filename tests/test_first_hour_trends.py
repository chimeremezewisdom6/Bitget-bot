import unittest

from daily_research import analyze_first_hour_trends


def candle(ts, open_price, high, low, close):
    return [str(ts), str(open_price), str(high), str(low), str(close), "1", "100"]


class FirstHourTrendBacktestTests(unittest.TestCase):
    def test_long_breakout_counts_first_hour_candle_colours(self):
        start = 1_700_000_000_000
        rows = [
            candle(start + i * 60_000, 100, 100.1, 99.9, 100)
            for i in range(60)
        ]
        rows.append(candle(start + 60 * 60_000, 100.5, 101.1, 100.4, 101))
        rows.extend(
            candle(start + i * 60_000, 101 + (i - 61) * 0.01,
                   101.2 + (i - 61) * 0.01, 101 + (i - 61) * 0.01,
                   101.1 + (i - 61) * 0.01)
            for i in range(61, 120)
        )
        result = analyze_first_hour_trends("TESTUSDT", rows, start, start + 120 * 60_000)
        self.assertEqual(result["events_found"], 1)
        event = result["events"][0]
        self.assertEqual(event["direction"], "LONG")
        self.assertEqual(event["candles_in_first_hour"], 60)
        self.assertEqual(event["green_candles"], 60)
        self.assertEqual(event["direction_matching_candles"], 60)

    def test_short_breakout_counts_red_candles(self):
        start = 1_700_000_000_000
        rows = [
            candle(start + i * 60_000, 100, 100.1, 99.9, 100)
            for i in range(60)
        ]
        rows.append(candle(start + 60 * 60_000, 99.5, 99.6, 98.9, 99))
        rows.extend(
            candle(start + i * 60_000, 99 - (i - 61) * 0.01,
                   99 - (i - 61) * 0.01, 98.8 - (i - 61) * 0.01,
                   98.9 - (i - 61) * 0.01)
            for i in range(61, 120)
        )
        result = analyze_first_hour_trends("TESTUSDT", rows, start, start + 120 * 60_000)
        self.assertEqual(result["events_found"], 1)
        event = result["events"][0]
        self.assertEqual(event["direction"], "SHORT")
        self.assertEqual(event["red_candles"], 60)
        self.assertEqual(event["direction_matching_candles"], 60)

    def test_incomplete_first_hour_is_not_counted(self):
        start = 1_700_000_000_000
        rows = [
            candle(start + i * 60_000, 100, 100.1, 99.9, 100)
            for i in range(60)
        ]
        rows.append(candle(start + 60 * 60_000, 100.5, 101.1, 100.4, 101))
        rows.extend(
            candle(start + i * 60_000, 101, 101.2, 100.9, 101.1)
            for i in range(61, 90)
        )
        result = analyze_first_hour_trends("TESTUSDT", rows, start, start + 90 * 60_000)
        self.assertEqual(result["events_found"], 0)


if __name__ == "__main__":
    unittest.main()
