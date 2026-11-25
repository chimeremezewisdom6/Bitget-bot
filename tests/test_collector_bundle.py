import tempfile
import unittest
from pathlib import Path

from collector import bundle
from research.dataset import load_bundle


class BundleTests(unittest.TestCase):
    def sections(self):
        return {
            "features": [{"symbol": "BTCUSDT", "ts_ms": 2, "value": 1.0}],
            "book": [{"symbol": "BTCUSDT", "bids": [[100, 1]], "asks": [[101, 1]]}],
            "flow": [{"symbol": "BTCUSDT", "imbalance": 0.2}],
            "micro": [{"symbol": "BTCUSDT", "sample": 1}],
        }

    def test_bundle_is_deterministic(self):
        meta = {"slot": "2026-11-25T06:00:00+00:00", "symbols_ok": 1, "symbols_failed": 0}
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            path_a, manifest_a = bundle.build_bundle(self.sections(), meta, first)
            path_b, manifest_b = bundle.build_bundle(self.sections(), meta, second)
            self.assertEqual(manifest_a["sha256"], manifest_b["sha256"])
            self.assertEqual(manifest_a["size_bytes"], manifest_b["size_bytes"])

    def test_manifest_counts_and_quality(self):
        meta = {"slot": "slot", "symbols_ok": 1, "symbols_failed": 2, "duplicates": 3}
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest = bundle.build_bundle(self.sections(), meta, tmp)
        self.assertEqual(manifest["counts"]["features"], 1)
        self.assertEqual(manifest["counts"]["micro"], 1)
        self.assertEqual(manifest["quality"]["symbols_failed"], 2)
        self.assertEqual(manifest["quality"]["duplicates"], 3)

    def test_trim_drops_optional_sections_in_order(self):
        trimmed, dropped = bundle.trim_sections(self.sections(), max_bytes=1)
        self.assertEqual(dropped, ["micro", "book", "flow"])
        self.assertEqual(trimmed["features"], self.sections()["features"])

    def test_bundle_roundtrip(self):
        meta = {"slot": "slot", "symbols_ok": 1, "symbols_failed": 0}
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = bundle.build_bundle(self.sections(), meta, tmp)
            loaded = load_bundle(path)
        self.assertEqual(loaded["meta"]["slot"], "slot")
        self.assertEqual(len(loaded["rows"]["features"]), 1)
        self.assertEqual(loaded["rows"]["features"][0]["symbol"], "BTCUSDT")

    def test_size_limit_is_reported(self):
        meta = {"slot": "slot", "symbols_ok": 1, "symbols_failed": 0}
        with tempfile.TemporaryDirectory() as tmp:
            path, manifest = bundle.build_bundle(self.sections(), meta, tmp, max_bytes=50)
        self.assertGreater(manifest["size_bytes"], 0)
        self.assertTrue(manifest["quality"]["truncated_sections"])


if __name__ == "__main__":
    unittest.main()
