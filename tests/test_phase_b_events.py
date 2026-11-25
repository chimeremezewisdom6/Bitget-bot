import unittest

from research import events


def feature(**overrides):
    base = {
        "symbol": "BTCUSDT",
        "ts_ms": 1_800_000_000_000,
        "taker_imbalance": 0.6,
        "taker_coverage_pct": 50.0,
        "taker_quality": "ADEQUATE",
        "turnover_z_60m": 2.5,
        "return_1m_pct": 0.2,
        "return_5m_pct": 0.3,
        "return_15m_pct": 0.4,
        "oi_delta_15m_pct": 2.5,
        "spread_bps": 5.0,
        "funding_rate": 0.0001,
        "taker_fee_bps": 6.0,
        "book_imbalance_0p5": -0.3,
        "liquidation_total_usdt": 6000.0,
        "liquidation_long_usdt": 6000.0,
        "liquidation_short_usdt": 0.0,
        "liquidation_records": 2,
        "liquidation_side": "LONG",
        "liquidation_status": "PARTIAL_PAGE",
        "spot_turnover_z": 2.5,
        "spot_return_5m_pct": 0.3,
        "spot_basis_bps": 10.0,
        "spot_status": "MAPPED",
        "breakout_60m": True,
        "breakout_direction": "LONG",
        "failed_breakout": False,
        "absorption": {
            "absorbed": True, "direction": "SHORT", "depth_known": True,
            "book_known": True, "book_aligned": True, "book_imbalance": -0.3,
        },
    }
    base.update(overrides)
    return base


class PhaseBEventTests(unittest.TestCase):
    def test_oi_change_records_both_directions(self):
        event = events.detect_oi_change(feature(), {"min_abs_oi_delta_pct": 2.0, "min_abs_return_pct": 0.2})
        self.assertIsNotNone(event)
        self.assertEqual(event.type, "oi_change")
        self.assertEqual(event.direction, "LONG")
        self.assertEqual(event.features["oi_direction"], "UP")
        self.assertEqual(event.features["price_direction"], "LONG")
        self.assertEqual(event.features["oi_price_alignment"], "ALIGNED")

    def test_oi_change_opposed_alignment_is_recorded(self):
        event = events.detect_oi_change(
            feature(oi_delta_15m_pct=-2.5),
            {"min_abs_oi_delta_pct": 2.0, "min_abs_return_pct": 0.2},
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.features["oi_direction"], "DOWN")
        self.assertEqual(event.features["oi_price_alignment"], "OPPOSED")

    def test_oi_change_rejects_small_changes(self):
        self.assertIsNone(events.detect_oi_change(feature(oi_delta_15m_pct=1.0), {"min_abs_oi_delta_pct": 2.0}))
        self.assertIsNone(events.detect_oi_change(feature(return_15m_pct=0.1), {"min_abs_return_pct": 0.2}))

    def test_oi_build_is_positive_only(self):
        params = {"min_abs_oi_delta_pct": 2.0, "min_abs_return_pct": 0.2, "require_positive_oi": True}
        self.assertIsNone(events.detect_oi_change(feature(oi_delta_15m_pct=-2.5), params))
        self.assertIsNotNone(events.detect_oi_change(feature(oi_delta_15m_pct=2.5), params))

    def test_positive_oi_with_negative_price_is_opposed_build(self):
        params = {"min_abs_oi_delta_pct": 2.0, "min_abs_return_pct": 0.2, "require_positive_oi": True}
        event = events.detect_oi_change(
            feature(oi_delta_15m_pct=2.5, return_15m_pct=-0.4), params
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.direction, "SHORT")
        self.assertEqual(event.features["oi_direction"], "UP")
        self.assertEqual(event.features["price_direction"], "SHORT")
        self.assertEqual(event.features["oi_price_alignment"], "OPPOSED")

    def test_oi_build_exact_thresholds(self):
        params = {"min_abs_oi_delta_pct": 2.0, "min_abs_return_pct": 0.2, "require_positive_oi": True}
        self.assertIsNotNone(events.detect_oi_change(feature(oi_delta_15m_pct=2.0, return_15m_pct=0.2), params))
        self.assertIsNone(events.detect_oi_change(feature(oi_delta_15m_pct=1.999, return_15m_pct=0.2), params))
        self.assertIsNone(events.detect_oi_change(feature(oi_delta_15m_pct=2.0, return_15m_pct=0.199), params))

    def test_liquidation_fade_and_follow_directions(self):
        fade_long = events.detect_liquidation_spike(feature(), {"min_notional_usdt": 5000, "mode": "fade"})
        follow_long = events.detect_liquidation_spike(feature(), {"min_notional_usdt": 5000, "mode": "follow"})
        self.assertEqual(fade_long.direction, "LONG")
        self.assertEqual(follow_long.direction, "SHORT")
        short = feature(liquidation_long_usdt=0.0, liquidation_short_usdt=6000.0, liquidation_side="SHORT")
        self.assertEqual(events.detect_liquidation_spike(short, {"mode": "fade"}).direction, "SHORT")
        self.assertEqual(events.detect_liquidation_spike(short, {"mode": "follow"}).direction, "LONG")

    def test_liquidation_threshold_and_mixed_side(self):
        self.assertIsNone(events.detect_liquidation_spike(
            feature(liquidation_total_usdt=4999.0, liquidation_long_usdt=4999.0),
            {"min_notional_usdt": 5000},
        ))
        self.assertIsNone(events.detect_liquidation_spike(
            feature(liquidation_long_usdt=3000.0, liquidation_short_usdt=3000.0),
            {"min_notional_usdt": 5000},
        ))

    def test_liquidation_size_is_preserved(self):
        event = events.detect_liquidation_spike(feature(), {"min_notional_usdt": 5000})
        self.assertEqual(event.features["liquidation_total_usdt"], 6000.0)
        self.assertEqual(event.features["liquidation_records"], 2)

    def test_absorption_requires_depth_and_optional_book_alignment(self):
        self.assertIsNotNone(events.detect_absorption(feature(), {"require_depth_known": True}))
        unknown_depth = feature(absorption={
            "absorbed": True, "direction": "SHORT", "depth_known": False,
            "book_known": True, "book_aligned": True, "book_imbalance": -0.3,
        })
        self.assertIsNone(events.detect_absorption(unknown_depth, {"require_depth_known": True}))
        weak_book = feature(absorption={
            "absorbed": True, "direction": "SHORT", "depth_known": True,
            "book_known": True, "book_aligned": False, "book_imbalance": -0.1,
        })
        self.assertIsNone(events.detect_absorption(weak_book, {"require_book_imbalance": True}))
        self.assertIsNotNone(events.detect_absorption(feature(), {"require_book_imbalance": True}))

    def test_breakout_turnover_filter(self):
        self.assertIsNone(events.detect_breakout(feature(turnover_z_60m=1.8), {"turnover_z": 2.0}))
        self.assertIsNotNone(events.detect_breakout(feature(turnover_z_60m=2.5), {"turnover_z": 2.0}))

    def test_failed_breakout_turnover_filter(self):
        failed = feature(failed_breakout=True, turnover_z_60m=1.8)
        self.assertIsNone(events.detect_failed_breakout(failed, {"turnover_z": 2.0}))
        self.assertIsNotNone(events.detect_failed_breakout(feature(failed_breakout=True, turnover_z_60m=2.5), {"turnover_z": 2.0}))

    def test_event_payload_carries_phase_b_fields(self):
        event = events.detect_taker_aggression(feature(), {"min_imbalance": 0.5, "min_coverage_pct": 20})
        for key in ("funding_rate", "taker_fee_bps", "liquidation_total_usdt", "book_imbalance_0p5"):
            self.assertIn(key, event.features)


if __name__ == "__main__":
    unittest.main()
