import unittest

from collector import universe


def instrument(symbol, base, **overrides):
    row = {
        "symbol": symbol,
        "baseCoin": base,
        "quoteCoin": "USDT",
        "status": "online",
        "type": "perpetual",
        "instrumentType": "crypto",
        "symbolType": "crypto",
        "takerFeeRate": "0.0006",
    }
    row.update(overrides)
    return row


def ticker(symbol, turnover, bid, ask):
    return {
        "symbol": symbol,
        "turnover24h": str(turnover),
        "bid1Price": str(bid),
        "ask1Price": str(ask),
        "lastPrice": str((bid + ask) / 2),
    }


class UniverseTests(unittest.TestCase):
    def setUp(self):
        self.instruments = [
            instrument("BTCUSDT", "BTC"),
            instrument("ETHUSDT", "ETH"),
            instrument("WIDEUSDT", "WIDE"),
            instrument("THINUSDT", "THIN"),
            instrument("STOCKUSDT", "STOCK", symbolType="stock"),
            instrument("SPOTUSDT", "SPOT", type="spot"),
        ]
        self.tickers = [
            ticker("BTCUSDT", 50_000_000, 100.0, 100.05),
            ticker("ETHUSDT", 40_000_000, 200.0, 200.1),
            ticker("WIDEUSDT", 30_000_000, 10.0, 10.1),
            ticker("THINUSDT", 20_000_000, 1.0, 1.001),
            ticker("STOCKUSDT", 10_000_000, 5.0, 5.01),
            ticker("SPOTUSDT", 9_000_000, 2.0, 2.001),
        ]
        self.books = {
            "BTCUSDT": {"b": [[100.0, 1_000.0]], "a": [[100.05, 1_000.0]]},
            "ETHUSDT": {"b": [[200.0, 500.0]], "a": [[200.1, 500.0]]},
            "WIDEUSDT": {"b": [[10.0, 5_000.0]], "a": [[10.1, 5_000.0]]},
            "THINUSDT": {"b": [[1.0, 1.0]], "a": [[1.001, 1.0]]},
        }

    def test_stock_and_spot_instruments_are_excluded(self):
        candidates = universe.rank_candidates(self.tickers, self.instruments)
        symbols = {row["symbol"] for row in candidates.rows}
        self.assertNotIn("STOCKUSDT", symbols)
        self.assertNotIn("SPOTUSDT", symbols)
        stages = {(row["symbol"], row["stage"]) for row in candidates.excluded}
        self.assertIn(("STOCKUSDT", "instrument"), stages)
        self.assertIn(("SPOTUSDT", "instrument"), stages)

    def test_top_n_is_enforced_and_recorded(self):
        candidates = universe.rank_candidates(self.tickers, self.instruments, top_n=2)
        self.assertEqual([row["symbol"] for row in candidates.rows], ["BTCUSDT", "ETHUSDT"])
        self.assertIn(("WIDEUSDT", "top_n"), {(row["symbol"], row["stage"]) for row in candidates.excluded})

    def test_spread_and_depth_filters_are_applied_in_order(self):
        candidates = universe.rank_candidates(self.tickers, self.instruments)
        selection = universe.select(candidates, self.books)
        symbols = [row.symbol for row in selection.selected]
        self.assertEqual(symbols, ["BTCUSDT", "ETHUSDT"])
        reasons = {(row["symbol"], row["stage"]) for row in selection.excluded}
        self.assertIn(("WIDEUSDT", "spread"), reasons)
        self.assertIn(("THINUSDT", "depth"), reasons)
        self.assertEqual(selection.sample_sizes["after_spread"], 3)
        self.assertEqual(selection.sample_sizes["after_depth"], 2)
        self.assertEqual(selection.sample_sizes["final"], 2)

    def test_turnover_band_counts_are_recorded(self):
        candidates = universe.rank_candidates(self.tickers, self.instruments)
        selection = universe.select(candidates, self.books)
        self.assertEqual(sum(selection.band_counts.values()), 2)
        self.assertEqual(selection.band_counts["10m_100m_turnover"], 2)

    def test_low_sample_flag_is_explicit(self):
        candidates = universe.rank_candidates(self.tickers, self.instruments)
        selection = universe.select(candidates, self.books)
        self.assertTrue(selection.sample_sizes["low_sample"])

    def test_missing_book_is_excluded(self):
        candidates = universe.rank_candidates(self.tickers, self.instruments)
        selection = universe.select(candidates, {})
        self.assertEqual(selection.selected, [])
        self.assertTrue(all(row["stage"] == "depth" for row in selection.excluded if row["symbol"] in {"BTCUSDT", "ETHUSDT"}))


if __name__ == "__main__":
    unittest.main()
