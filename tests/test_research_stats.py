import unittest

from research import stats


class StatsTests(unittest.TestCase):
    def test_bootstrap_is_seeded_and_contains_mean(self):
        first = stats.bootstrap_ci([1, 2, 3, 4], n_boot=500, seed=7)
        second = stats.bootstrap_ci([1, 2, 3, 4], n_boot=500, seed=7)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["mean"], 2.5)
        self.assertLessEqual(first["lo"], first["mean"])
        self.assertGreaterEqual(first["hi"], first["mean"])

    def test_block_bootstrap_uses_labels(self):
        values = [1.0, 1.1, 5.0, 5.1]
        labels = ["a", "a", "b", "b"]
        result = stats.bootstrap_ci(values, n_boot=200, seed=1, blocks=labels)
        self.assertEqual(result["n"], 4)
        self.assertIsNotNone(result["lo"])

    def test_wilson_interval(self):
        result = stats.wilson_interval(8, 10)
        self.assertAlmostEqual(result["rate"], 0.8)
        self.assertLess(result["lo"], 0.8)
        self.assertGreater(result["hi"], 0.8)

    def test_profit_factor(self):
        self.assertAlmostEqual(stats.profit_factor([2.0, -1.0]), 2.0)
        self.assertIsNone(stats.profit_factor([1.0, 2.0]))

    def test_bh_fdr(self):
        qvalues = stats.bh_fdr([0.01, 0.04, 0.03, 0.5])
        self.assertAlmostEqual(qvalues[0], 0.04, places=6)
        self.assertAlmostEqual(qvalues[1], 0.053333, places=6)
        self.assertAlmostEqual(qvalues[2], 0.053333, places=6)
        self.assertAlmostEqual(qvalues[3], 0.5, places=6)

    def test_verdict_rules(self):
        validated = stats.verdict(
            n=300, days=15, ci={"lo": 1.0, "hi": 5.0}, lift_bps=2.0, q_value=0.05,
        )
        rejected = stats.verdict(
            n=300, days=15, ci={"lo": -5.0, "hi": -1.0}, lift_bps=2.0, q_value=0.05,
        )
        small = stats.verdict(
            n=10, days=15, ci={"lo": 1.0, "hi": 5.0}, lift_bps=2.0, q_value=0.05,
        )
        self.assertEqual(validated, "VALIDATED")
        self.assertEqual(rejected, "REJECTED")
        self.assertEqual(small, "INCONCLUSIVE")

    def test_summarise(self):
        result = stats.summarise([1.0, -1.0, 2.0], seed=0)
        self.assertEqual(result["n"], 3)
        self.assertAlmostEqual(result["positive_rate"], 2 / 3, places=6)


if __name__ == "__main__":
    unittest.main()
