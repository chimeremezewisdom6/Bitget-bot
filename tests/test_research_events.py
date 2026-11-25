import unittest

from research import events


def feature(**overrides):
    base = {
        "symbol": "BTCUSDT", "ts_ms": 1_800_000_000_000,
        "turnover_z_60m": 3.0, "return_1m_pct": 0.5,
        "return_5m_pct": 0.4, "return_15m_pct": 0.8,
        "oi_delta_15m_pct": 0.6, "taker_imbalance": 0.5,
        "taker_coverage_pct": 40.0, "taker_quality": "ADEQUATE",
        "volatility_status": "OK", "flag_0_7": False,
        "spot_turnover_z": 3.0, "spot_return_5m_pct": 0.5,
        "breakout_60m": True, "breakout_direction": "LONG",
        "failed_breakout": False,
        "absorption": {"absorbed": True, "direction": "SHORT"},
    }
    base.update(overrides)
    return base


class EventTests(unittest.TestCase):
    def test_turnover_expansion_boundary(self):
        self.assertIsNotNone(events.detect(feature(), "turnover_expansion"))
        self.assertIsNone(events.detect(feature(turnover_z_60m=1.99), "turnover_expansion"))
        self.assertIsNone(events.detect(feature(return_1m_pct=0.1), "turnover_expansion"))

    def test_oi_build_requires_matching_sign(self):
        event = events.detect(feature(), "oi_build")
        self.assertEqual(event.direction, "LONG")
        self.assertIsNone(events.detect(feature(oi_delta_15m_pct=-0.6), "oi_build"))

    def test_taker_aggression_requires_coverage(self):
        self.assertIsNotNone(events.detect(feature(), "taker_aggression"))
        self.assertIsNone(events.detect(feature(taker_coverage_pct=10.0), "taker_aggression"))

    def test_absorption_fades_the_aggressor(self):
        event = events.detect(feature(), "absorption")
        self.assertEqual(event.direction, "SHORT")
        self.assertIsNone(events.detect(feature(absorption={"absorbed": False}), "absorption"))

    def test_spot_lead_requires_spot_to_lead(self):
        self.assertIsNotNone(events.detect(feature(), "spot_lead"))
        self.assertIsNone(events.detect(feature(return_5m_pct=0.9), "spot_lead"))

    def test_failed_breakout_fades_direction(self):
        event = events.detect(feature(failed_breakout=True), "failed_breakout")
        self.assertEqual(event.direction, "SHORT")
        self.assertIsNone(events.detect(feature(), "failed_breakout"))

    def test_unknown_event_type_raises(self):
        with self.assertRaises(ValueError):
            events.detect(feature(), "not_a_real_event")

    def test_dedupe_keeps_earliest_within_gap(self):
        first = events.detect(feature(ts_ms=1_000), "turnover_expansion")
        second = events.detect(feature(ts_ms=61_000), "turnover_expansion")
        third = events.detect(feature(ts_ms=4_000_000), "turnover_expansion")
        kept = events.dedupe([first, second, third], min_gap_ms=3_600_000)
        self.assertEqual([event.ts_ms for event in kept], [1_000, 4_000_000])


if __name__ == "__main__":
    unittest.main()
