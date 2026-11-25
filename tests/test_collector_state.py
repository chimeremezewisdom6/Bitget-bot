import json
import tempfile
import unittest
from pathlib import Path

from collector import state


class StateTests(unittest.TestCase):
    def test_start_session_has_bounded_fields(self):
        session = state.start_session(1_800_000_000_000)
        self.assertTrue(session["active"])
        self.assertFalse(session["trading_enabled"])
        self.assertNotIn("candle_ids", session)
        self.assertNotIn("signal_ids", session)
        self.assertNotIn("trend_backtest_symbols_completed", session)
        self.assertLess(len(json.dumps(session)), 2_000)

    def test_session_expiry(self):
        session = state.start_session(1_800_000_000_000)
        self.assertTrue(state.is_active(session, 1_800_000_000_000))
        self.assertFalse(state.is_active(session, 1_800_000_000_000 + 90_000_000))

    def test_finish_session_marks_inactive(self):
        session = state.start_session(1_800_000_000_000)
        finished = state.finish_session(session, 1_800_000_000_000 + 1_000)
        self.assertFalse(finished["active"])
        self.assertIn("stopped_at_utc", finished)

    def test_heartbeat_is_truthful(self):
        session = state.start_session(1_800_000_000_000)
        result = {
            "outcome": "partial", "slot": "slot", "symbols_requested": 10,
            "symbols_ok": 9, "symbols_failed": 1, "candles_new": 8,
            "events": 2, "duplicates": 0, "duration_ms": 1000,
            "artifact": "cycle-1", "errors": [{"symbol": "X", "source": "fills", "message": "timeout"}],
        }
        beat = state.heartbeat(result, session, now_ms=1_800_000_000_000)
        self.assertEqual(beat["outcome"], "partial")
        self.assertEqual(beat["symbols_ok"], 9)
        self.assertEqual(beat["symbols_failed"], 1)
        self.assertFalse(beat["trading_enabled"])
        self.assertEqual(len(beat["errors"]), 1)

    def test_atomic_write_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "state.json"
            state.write_json_atomic(path, {"a": 1})
            self.assertEqual(json.loads(path.read_text()), {"a": 1})
            self.assertFalse(any(path.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
