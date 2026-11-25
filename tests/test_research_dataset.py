import tempfile
import unittest
from pathlib import Path

from collector import bundle
from research import dataset

START = 1_800_000_000_000
DAY = 86_400_000


def row(day, hour=12):
    return {"symbol": "BTCUSDT", "ts_ms": START + day * DAY + hour * 3_600_000}


class DatasetTests(unittest.TestCase):
    def test_split_is_chronological(self):
        rows = [row(5), row(16), row(25)]
        split = dataset.split_30d(rows, START)
        self.assertEqual(len(split["train"]), 1)
        self.assertEqual(len(split["validation"]), 1)
        self.assertEqual(len(split["test"]), 1)

    def test_event_near_boundary_is_excluded(self):
        near = {"symbol": "BTCUSDT", "ts_ms": START + 15 * DAY - 30 * 60_000}
        split = dataset.split_30d([near], START)
        self.assertEqual(split["train"], [])
        self.assertEqual(split["validation"], [])

    def test_event_crossing_dataset_end_is_excluded(self):
        last = {"symbol": "BTCUSDT", "ts_ms": START + 29 * DAY + 23 * 3_600_000 + 30 * 60_000}
        split = dataset.split_30d([last], START)
        self.assertEqual(split["test"], [])

    def test_validation_event_with_trailing_lookback_across_boundary_is_excluded(self):
        early = {"symbol": "BTCUSDT", "ts_ms": START + 15 * DAY + 30 * 60_000}
        split = dataset.split_30d([early], START)
        self.assertEqual(split["validation"], [])

    def test_validation_event_after_lookback_is_included(self):
        later = {"symbol": "BTCUSDT", "ts_ms": START + 15 * DAY + 2 * 3_600_000}
        split = dataset.split_30d([later], START)
        self.assertEqual(len(split["validation"]), 1)

    def test_test_event_with_trailing_lookback_across_boundary_is_excluded(self):
        early = {"symbol": "BTCUSDT", "ts_ms": START + 22 * DAY + 30 * 60_000}
        split = dataset.split_30d([early], START)
        self.assertEqual(split["test"], [])

    def test_bundle_roundtrip_and_hash(self):
        meta = {"slot": "slot", "symbols_ok": 1, "symbols_failed": 0}
        sections = {
            "features": [{"symbol": "BTCUSDT", "ts_ms": 1, "value": 2.0}],
            "candles": [{"symbol": "BTCUSDT", "ts": 1, "close": 100.0}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path, manifest = bundle.build_bundle(sections, meta, tmp)
            loaded = dataset.load_bundle(path)
            self.assertEqual(loaded["rows"]["features"][0]["value"], 2.0)
            selected = dataset.load_bundle(path, sections={"features"})
            self.assertIn("features", selected["rows"])
            self.assertNotIn("candles", selected["rows"])
            self.assertEqual(dataset.sha256_file(path), manifest["sha256"])
            loaded_all = dataset.load_bundles(tmp)
        self.assertEqual(len(loaded_all["metas"]), 1)
        self.assertEqual(len(loaded_all["rows"]["features"]), 1)


if __name__ == "__main__":
    unittest.main()
