import unittest

from research.watchdog import classify


NOW = 1_800_000_000_000


def summary(slot, *, outcome="success", started=None, finished=None, ok=90, failed=10, truncated=False):
    return {
        "slot_ms": slot,
        "slot": str(slot),
        "started_ms": slot if started is None else started,
        "finished_ms": (slot + 60_000) if finished is None else finished,
        "outcome": outcome,
        "symbols_ok": ok,
        "symbols_failed": failed,
        "manifest": {"quality": {"truncated_sections": ["book"] if truncated else []}},
    }


class PhaseBWatchdogTests(unittest.TestCase):
    def test_no_data(self):
        result = classify([], now_ms=NOW)
        self.assertEqual(result["status"], "NO_DATA")

    def test_stale_data(self):
        result = classify([summary(NOW - 20 * 60_000)], now_ms=NOW, stale_minutes=15)
        self.assertEqual(result["status"], "STALE")

    def test_missing_slots(self):
        result = classify([summary(NOW)], now_ms=NOW, window_minutes=60)
        self.assertEqual(result["status"], "MISSING")
        self.assertGreater(result["missing_slots"], 0)

    def test_failed_collection(self):
        rows = [summary(NOW - index * 300_000, outcome="failed" if index == 0 else "success") for index in range(12)]
        result = classify(rows, now_ms=NOW, window_minutes=60)
        self.assertEqual(result["status"], "INCOMPLETE")

    def test_truncated_bundle(self):
        rows = [summary(NOW - index * 300_000, truncated=(index == 0)) for index in range(12)]
        result = classify(rows, now_ms=NOW, window_minutes=60)
        self.assertEqual(result["status"], "TRUNCATED")

    def test_degraded_coverage(self):
        rows = [summary(NOW - index * 300_000, ok=50, failed=50) for index in range(12)]
        result = classify(rows, now_ms=NOW, window_minutes=60)
        self.assertEqual(result["status"], "DEGRADED")

    def test_delayed_collection(self):
        rows = [summary(NOW - index * 300_000, started=(NOW - index * 300_000) + 120_000) for index in range(12)]
        result = classify(rows, now_ms=NOW, window_minutes=60)
        self.assertEqual(result["status"], "DELAYED")

    def test_healthy_window(self):
        rows = [summary(NOW - index * 300_000) for index in range(12)]
        result = classify(rows, now_ms=NOW, window_minutes=60)
        self.assertEqual(result["status"], "OK")


if __name__ == "__main__":
    unittest.main()
