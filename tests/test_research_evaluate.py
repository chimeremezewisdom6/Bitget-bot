import tempfile
import unittest
from pathlib import Path

from research import evaluate

START = 1_800_000_000_000
DAY = 86_400_000


def spec():
    return {
        "id": "EXP-0001",
        "version": "1.0.0",
        "question": "q",
        "hypothesis": "h",
        "event": {"type": "turnover_expansion", "params": {"turnover_z": 2.0}},
        "outcomes": {"horizons": [5]},
        "split": {"total_days": 30, "train_days": 15, "validation_days": 7,
                  "test_days": 8, "embargo_minutes": 60},
        "decision": {"min_events": 200, "min_days": 10, "ci": 0.95, "fdr_q": 0.10},
    }


def features():
    rows = []
    for day in (5, 16, 25):
        rows.append({
            "symbol": "BTCUSDT",
            "ts_ms": START + day * DAY + 12 * 3_600_000,
            "turnover_z_60m": 3.0,
            "return_1m_pct": 0.5,
            "flag_0_7": False,
            "volatility_status": "OK",
        })
    return rows


def candles():
    rows = []
    for index in range(30 * 24 * 60):
        price = 100.0 + index * 0.001
        rows.append([
            str(START + index * 60_000),
            str(price), str(price + 0.01), str(price - 0.01), str(price), "1", "1000",
        ])
    return rows


class EvaluateTests(unittest.TestCase):
    def test_evaluate_produces_split_metrics(self):
        metrics = evaluate.evaluate(
            spec(), features(), {"BTCUSDT": candles()}, start_ms=START, fee_bps=6, funding_bps=0.0,
        )
        self.assertEqual(metrics["experiment_id"], "EXP-0001")
        self.assertEqual(metrics["split_sizes"], {"train": 1, "validation": 1, "test": 1})
        for split in ("train", "validation", "test"):
            self.assertEqual(metrics["splits"][split]["events"], 1)
            self.assertEqual(metrics["splits"][split]["by_horizon"]["5"]["n"], 1)

    def test_report_and_outputs(self):
        metrics = evaluate.evaluate(
            spec(), features(), {"BTCUSDT": candles()}, start_ms=START, fee_bps=6, funding_bps=0.0,
        )
        report = evaluate.render_report(metrics)
        self.assertIn("EXP-0001", report)
        self.assertIn("Interpretation", report)
        with tempfile.TemporaryDirectory() as tmp:
            paths = evaluate.write_outputs(metrics, tmp)
            self.assertTrue(Path(paths["metrics"]).exists())
            self.assertTrue(Path(paths["report"]).exists())

    def test_volatility_buckets_are_reported(self):
        metrics = evaluate.evaluate(
            spec(), features(), {"BTCUSDT": candles()}, start_ms=START, fee_bps=6, funding_bps=0.0,
        )
        self.assertIn("volatility_normal", metrics["splits"]["train"]["by_bucket"])


if __name__ == "__main__":
    unittest.main()
