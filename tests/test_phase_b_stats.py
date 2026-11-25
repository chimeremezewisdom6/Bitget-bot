import unittest

from research import stats


class PhaseBStatsTests(unittest.TestCase):
    def test_summary_reports_tails(self):
        summary = stats.summarise([-2, -1, 0, 1, 2])
        self.assertEqual(summary["n"], 5)
        self.assertIsNotNone(summary["p10"])
        self.assertIsNotNone(summary["p90"])
        self.assertLess(summary["p10"], summary["p90"])

    def test_bootstrap_pvalue_positive_mean(self):
        result = stats.bootstrap_pvalue([1.0] * 10, n_boot=200, seed=1)
        self.assertLess(result["p_value"], 0.05)

    def test_bootstrap_pvalue_negative_mean(self):
        result = stats.bootstrap_pvalue([-1.0] * 10, n_boot=200, seed=1)
        self.assertGreater(result["p_value"], 0.5)

    def test_fdr_is_monotonic(self):
        qvalues = stats.bh_fdr([0.001, 0.01, 0.02, 0.5])
        self.assertEqual(len(qvalues), 4)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in qvalues))
        self.assertLessEqual(qvalues[0], qvalues[-1])


if __name__ == "__main__":
    unittest.main()
