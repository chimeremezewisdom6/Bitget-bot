import json
import tempfile
import unittest
from pathlib import Path
from research_report import build_report

class ResearchReportTests(unittest.TestCase):
    def test_counts_only_forward_reference_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "session.json").write_text(json.dumps({"cycles": 4, "started_at_utc": "start"}))
            (root / "market_observations.jsonl").write_text('{"symbol":"BTCUSDT"}\n{"symbol":"ETHUSDT"}\n')
            (root / "public_trader_posts.jsonl").write_text('{"source":"reddit"}\n')
            (root / "shadow_experiments.jsonl").write_text(
                '{"type":"signal","strategy":"ema"}\n'
                '{"type":"forward_reference_outcome","strategy":"ema","estimated_net_bps":10}\n'
                '{"type":"forward_reference_outcome","strategy":"ema","estimated_net_bps":-5}\n')
            report = build_report(root)
            self.assertIn("Distinct symbols observed: 2", report)
            self.assertIn("Candidate signals: 1", report)
            self.assertIn("Forward reference outcomes: 2", report)
            self.assertIn("Mean estimated net result: 2.50 bps", report)
            self.assertIn("not executable fills", report)

if __name__ == "__main__":
    unittest.main()
