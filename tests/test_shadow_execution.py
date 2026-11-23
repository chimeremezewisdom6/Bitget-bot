import unittest
from shadow_execution import walk_book, simulate_round_trip

class ShadowExecutionTests(unittest.TestCase):
    def test_buy_walk_vwap(self):
        r = walk_book([[100, 1], [102, 1]], "buy", quote_target=150)
        self.assertTrue(r["complete"])
        self.assertAlmostEqual(r["filled_base"], 1.4901960784, places=7)
    def test_partial_sell_is_reported(self):
        r = walk_book([[99, 0.5]], "sell", quote_target=100)
        self.assertFalse(r["complete"])
        self.assertAlmostEqual(r["filled_quote_usdt"], 49.5)
        self.assertAlmostEqual(r["remaining_target"], 50.5)
    def test_round_trip_fees_and_funding(self):
        r = simulate_round_trip(entry_levels=[[100, 10]], exit_levels=[[102, 10]], direction="LONG", notional_usdt=100, taker_fee_bps=5, funding_bps=1)
        self.assertEqual(r["status"], "FULLY_SIMULATED")
        self.assertAlmostEqual(r["gross_pnl_usdt"], 2)
        self.assertAlmostEqual(r["total_fees_usdt"], 0.101)
        self.assertAlmostEqual(r["funding_cost_usdt"], 0.01)
        self.assertAlmostEqual(r["net_pnl_usdt"], 1.889)
    def test_short_reverses_funding_sign(self):
        r = simulate_round_trip(entry_levels=[[100, 10]], exit_levels=[[98, 10]], direction="SHORT", notional_usdt=100, taker_fee_bps=0, funding_bps=1)
        self.assertAlmostEqual(r["gross_pnl_usdt"], 2)
        self.assertAlmostEqual(r["funding_cost_usdt"], -0.01)
        self.assertAlmostEqual(r["net_pnl_usdt"], 2.01)
    def test_partial_entry_has_no_pnl(self):
        r = simulate_round_trip(entry_levels=[[100, 0.1]], exit_levels=[[101, 1]], direction="LONG", notional_usdt=100, taker_fee_bps=5)
        self.assertEqual(r["status"], "PARTIAL_ENTRY_NO_FULL_POSITION")
        self.assertIsNone(r["net_pnl_usdt"])
    def test_invalid_side_rejected(self):
        with self.assertRaises(ValueError):
            walk_book([], "hold", quote_target=10)

if __name__ == "__main__":
    unittest.main()
