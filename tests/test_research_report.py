import json
import tempfile
import unittest
from pathlib import Path
from research_report import build_report


class ResearchReportTests(unittest.TestCase):
    def test_counts_only_two_book_shadow_outcomes_and_calculates_profit_factor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "daily_research"
            root.mkdir()
            (root / "session.json").write_text(json.dumps({"cycles": 4, "started_at_utc": "start"}))
            (root / "market_observations.jsonl").write_text(
                '{"symbol":"BTCUSDT"}\n{"symbol":"ETHUSDT"}\n'
            )
            (root / "public_trader_posts.jsonl").write_text(
                '{"source":"reddit","title":"Trader discussion","url":"https://example.com/post","collected_at_utc":"2026-11-23T10:00:00Z"}\n'
            )
            (root / "shadow_experiments.jsonl").write_text(
                '{"type":"signal","strategy":"ema"}\n'
                '{"type":"orderbook_shadow_outcome","strategy":"ema","notional_usdt":100,"net_after_trading_fees_usdt":0.1}\n'
                '{"type":"orderbook_shadow_outcome","strategy":"ema","notional_usdt":100,"net_after_trading_fees_usdt":-0.05}\n'
                '{"type":"forward_reference_outcome","notional_usdt":100,"net_after_trading_fees_usdt":50}\n'
            )
            report = build_report(root)
            self.assertIn("Distinct symbols observed: 2", report)
            self.assertIn("Candidate signals eligible for entry evaluation: 1", report)
            self.assertIn("Two-snapshot order-book shadow outcomes: 2", report)
            self.assertIn("Mean estimated net result: 2.50 bps", report)
            self.assertIn("Gross positive outcomes: 0.100000 USDT", report)
            self.assertIn("Gross negative outcomes: 0.050000 USDT", report)
            self.assertIn("Profit factor (gross gains / gross losses): 2.000", report)
            self.assertIn("Trader discussion", report)
            self.assertIn("not executable fills", report)


if __name__ == "__main__":
    unittest.main()
