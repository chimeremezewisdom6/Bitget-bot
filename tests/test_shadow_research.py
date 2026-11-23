import unittest

from shadow_research import book_depth, simulate_market_fill, as_float


class ShadowResearchTests(unittest.TestCase):
    def test_invalid_numbers_fall_back(self):
        self.assertEqual(as_float("bad"), 0.0)
        self.assertEqual(as_float("12.5"), 12.5)

    def test_book_depth_within_price_band(self):
        asks = [[100.0, 2.0], [100.05, 1.0], [100.2, 5.0]]
        self.assertAlmostEqual(book_depth(asks, 100.0, "asks", 0.1), 300.05)

    def test_buy_walk_calculates_vwap_and_slippage(self):
        asks = [[101.0, 1.0], [102.0, 1.0]]
        result = simulate_market_fill(asks, 150.0, "buy", 100.0)
        self.assertTrue(result["fully_filled_visible_book"])
        self.assertAlmostEqual(result["filled_usdt"], 150.0)
        self.assertGreater(result["slippage_bps_vs_mid"], 0)

    def test_sell_walk_calculates_adverse_slippage(self):
        bids = [[99.0, 1.0], [98.0, 1.0]]
        result = simulate_market_fill(bids, 150.0, "sell", 100.0)
        self.assertTrue(result["fully_filled_visible_book"])
        self.assertGreater(result["slippage_bps_vs_mid"], 0)

    def test_partial_book_fill_is_not_fabricated(self):
        asks = [[100.0, 0.5]]
        result = simulate_market_fill(asks, 100.0, "buy", 100.0)
        self.assertFalse(result["fully_filled_visible_book"])
        self.assertAlmostEqual(result["filled_usdt"], 50.0)
        self.assertAlmostEqual(result["unfilled_usdt"], 50.0)


if __name__ == "__main__":
    unittest.main()
