import unittest

from cap_watchlist import classify_turnover


class BitgetActivityWatchlistTests(unittest.TestCase):
    def test_turnover_band_boundaries_are_non_overlapping(self):
        self.assertEqual(classify_turnover(999_999), "under_1m_turnover")
        self.assertEqual(classify_turnover(1_000_000), "1m_10m_turnover")
        self.assertEqual(classify_turnover(10_000_000), "10m_100m_turnover")
        self.assertEqual(classify_turnover(100_000_000), "over_100m_turnover")

    def test_invalid_turnover_is_not_classified(self):
        self.assertEqual(classify_turnover(None), "UNVERIFIED")
        self.assertEqual(classify_turnover(-1), "UNVERIFIED")

    def test_grouping_metric_is_turnover_not_market_cap(self):
        from cap_watchlist import BANDS
        self.assertEqual(len(BANDS), 4)
        self.assertTrue(all("turnover" in band["name"] for band in BANDS))


if __name__ == "__main__":
    unittest.main()
