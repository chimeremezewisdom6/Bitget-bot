import unittest

from trend_ignition import analyze_trend_ignition


class TrendIgnitionTests(unittest.TestCase):
    def fixtures(self, rising=True):
        candles = []
        price = 100.0
        for i in range(60):
            opening = price
            closing = opening * (1.002 if rising else 0.998)
            candles.append([
                str(i * 60_000), str(opening), str(max(opening, closing) * 1.001),
                str(min(opening, closing) * 0.999), str(closing),
                "100", "100000" if i >= 55 else "10000"
            ])
            price = closing
        oi = []
        for i in range(13):
            oi.append({
                "symbol": "TESTUSDT", "timestamp": str(i * 5 * 60_000),
                "openInterest": str(100 + i), "openInterestValue": str(100000 + i * 1000)
            })
        return candles, {"data": {"list": oi}}

    def test_detects_bullish_ignition_evidence(self):
        candles, oi = self.fixtures(True)
        result = analyze_trend_ignition("TESTUSDT", candles, oi, now_ms=61 * 60_000)
        self.assertEqual(result["status"], "ANALYZED")
        self.assertGreater(result["directions"]["LONG"]["score"], 0)
        self.assertEqual(result["candle_windows"]["5"]["green"], 5)
        self.assertIsNotNone(result["directions"]["LONG"]["open_interest_change_pct"][15])

    def test_detects_bearish_candle_pressure(self):
        candles, oi = self.fixtures(False)
        result = analyze_trend_ignition("TESTUSDT", candles, oi, now_ms=61 * 60_000)
        self.assertGreater(result["directions"]["SHORT"]["score"], 0)
        self.assertEqual(result["candle_windows"]["5"]["red"], 5)

    def test_rejects_incomplete_or_insufficient_candle_history(self):
        candles, oi = self.fixtures(True)
        result = analyze_trend_ignition("TESTUSDT", candles[:20], oi, now_ms=61 * 60_000)
        self.assertEqual(result["status"], "INSUFFICIENT_CANDLES")

    def test_missing_oi_is_explicit_not_zero(self):
        candles, _ = self.fixtures(True)
        result = analyze_trend_ignition("TESTUSDT", candles, {}, now_ms=61 * 60_000)
        self.assertEqual(
            result["directions"]["LONG"]["positioning_context"],
            "OI_HISTORY_UNAVAILABLE"
        )


if __name__ == "__main__":
    unittest.main()
