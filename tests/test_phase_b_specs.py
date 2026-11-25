import copy
import unittest
from pathlib import Path

from research.spec_registry import (
    SpecError,
    load_registry,
    registry_hash,
    spec_hash,
    specs_for_family,
    validate_registry,
)


class PhaseBSpecTests(unittest.TestCase):
    def test_registry_is_frozen_and_hashes_match(self):
        data = load_registry()
        self.assertTrue(data["frozen"])
        self.assertEqual(len(data["specs"]), 10)
        for spec in data["specs"]:
            self.assertEqual(spec["spec_hash"], spec_hash(spec))
        self.assertEqual(len(registry_hash(data)), 64)

    def test_primary_family_contains_both_liquidation_hypotheses(self):
        data = load_registry()
        ids = {spec["spec_id"] for spec in specs_for_family(data, "primary_v1")}
        self.assertIn("liquidation_fade_v1", ids)
        self.assertIn("liquidation_follow_v1", ids)
        self.assertIn("absorption_depth_v1", ids)
        self.assertNotIn("absorption_strict_v1", ids)

    def test_secondary_absorption_is_separate(self):
        data = load_registry()
        ids = [spec["spec_id"] for spec in specs_for_family(data, "secondary_absorption_v1")]
        self.assertEqual(ids, ["absorption_strict_v1"])

    def test_holdout_is_locked(self):
        data = load_registry()
        self.assertEqual(data["holdout"]["policy"], "locked_last_20pct")
        self.assertGreaterEqual(data["holdout"]["unlock_after_days"], 30)
        self.assertFalse(data["holdout"]["evaluated"])
        self.assertIsNone(data["holdout"]["unlock_at"])

    def test_standard_split_is_18_6_6_with_six_day_minimums(self):
        data = load_registry()
        standard = data["split_profiles"]["standard_30d"]
        self.assertEqual(
            (standard["train_days"], standard["validation_days"], standard["holdout_days"]),
            (18, 6, 6),
        )
        self.assertEqual(standard["min_days"]["validation"], 6)
        self.assertEqual(standard["min_days"]["holdout"], 6)

    def test_pilot_split_keeps_three_day_testability(self):
        data = load_registry()
        pilot = data["split_profiles"]["pilot_3d"]
        self.assertEqual(
            (pilot["train_days"], pilot["validation_days"], pilot["holdout_days"]),
            (1, 1, 1),
        )

    def test_positive_oi_build_replaces_negative_oi_event(self):
        data = load_registry()
        ids = {spec["spec_id"] for spec in data["specs"]}
        self.assertIn("oi_build_positive_v1", ids)
        self.assertNotIn("oi_change_v1", ids)
        spec = next(spec for spec in data["specs"] if spec["spec_id"] == "oi_build_positive_v1")
        self.assertTrue(spec["params"]["require_positive_oi"])

    def test_spot_lead_spec_has_no_magnitude_filter(self):
        data = load_registry()
        spec = next(spec for spec in data["specs"] if spec["spec_id"] == "spot_lead_v1")
        self.assertTrue(spec["params"]["require_timestamp_lead"])
        self.assertNotIn("min_abs_spot_return_pct", spec["params"])

    def test_taker_spec_has_no_coverage_threshold(self):
        data = load_registry()
        spec = next(spec for spec in data["specs"] if spec["spec_id"] == "taker_aggression_v1")
        self.assertNotIn("min_coverage_pct", spec["params"])
        self.assertEqual(spec["params"]["min_quality"], "ADEQUATE")

    def test_frozen_v1_registry_remains_loadable(self):
        path = Path(__file__).resolve().parents[1] / "research" / "specs" / "phase_b_v1.json"
        data = load_registry(path)
        self.assertEqual(data["registry_version"], "phase_b_v1")
        self.assertEqual(data["holdout"]["policy"], "locked_newest_day")
        self.assertEqual(len(data["specs"]), 10)

    def test_tampered_spec_hash_is_rejected(self):
        data = load_registry()
        tampered = copy.deepcopy(data)
        tampered["specs"][0]["params"]["min_imbalance"] = 0.1
        with self.assertRaises(SpecError):
            validate_registry(tampered)

    def test_unknown_family_is_rejected(self):
        data = load_registry()
        tampered = copy.deepcopy(data)
        tampered["specs"][0]["family"] = "not_a_family"
        with self.assertRaises(SpecError):
            validate_registry(tampered)


if __name__ == "__main__":
    unittest.main()
