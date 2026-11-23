import unittest
from cap_watchlist import classify_market_cap, match_exact_symbol, select_watchlist

BANDS = [
    {"name": "lower_cap", "min_usd": 0, "max_usd": 10_000_000},
    {"name": "small_cap", "min_usd": 10_000_000, "max_usd": 100_000_000},
    {"name": "mid_cap", "min_usd": 100_000_000, "max_usd": 1_000_000_000},
    {"name": "mega_cap", "min_usd": 1_000_000_000, "max_usd": None},
]

class CapWatchlistTests(unittest.TestCase):
    def test_cap_boundaries_are_non_overlapping(self):
        self.assertEqual(classify_market_cap(9_999_999, BANDS), "lower_cap")
        self.assertEqual(classify_market_cap(10_000_000, BANDS), "small_cap")
        self.assertEqual(classify_market_cap(100_000_000, BANDS), "mid_cap")
        self.assertEqual(classify_market_cap(1_000_000_000, BANDS), "mega_cap")
        self.assertEqual(classify_market_cap(None, BANDS), "UNVERIFIED")

    def test_exact_unique_symbol_match_is_provisional(self):
        coins = [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}]
        self.assertEqual(match_exact_symbol("BTC", coins), ("bitcoin", "unique_exact_symbol_needs_review"))

    def test_ambiguous_symbol_is_not_guessed(self):
        coins = [{"id": "coin-a", "symbol": "abc"}, {"id": "coin-b", "symbol": "abc"}]
        self.assertEqual(match_exact_symbol("ABC", coins), (None, "ambiguous_exact_symbol"))

    def test_verified_override_is_explicit(self):
        self.assertEqual(match_exact_symbol("ABC", [], {"coingecko_id": "coin-a", "verified": True}),
                         ("coin-a", "manually_verified_override"))

    def test_watchlist_never_fills_missing_group_with_other_caps(self):
        candidates = [
            {"symbol": "AUSDT", "market_cap_band": "lower_cap", "identity_status": "unique_exact_symbol_needs_review", "turnover24h_usdt": 100},
            {"symbol": "BUSDT", "market_cap_band": "mega_cap", "identity_status": "unique_exact_symbol_needs_review", "turnover24h_usdt": 200},
        ]
        result = select_watchlist(candidates, BANDS, 3)
        self.assertEqual([x["symbol"] for x in result["lower_cap"]], ["AUSDT"])
        self.assertEqual([x["symbol"] for x in result["mega_cap"]], ["BUSDT"])
        self.assertEqual(result["small_cap"], [])
        self.assertEqual(result["mid_cap"], [])

if __name__ == "__main__":
    unittest.main()
