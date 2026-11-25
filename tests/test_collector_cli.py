import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from collector import cli
from collector.cycle import CycleResult


class CollectorCliTests(unittest.TestCase):
    def test_defaults_are_lightweight_and_public(self):
        args = cli.parse_args([])
        self.assertEqual(args.top_n, 100)
        self.assertEqual(args.concurrency, 4)
        self.assertEqual(args.rate_per_sec, 4.0)
        self.assertEqual(args.max_bytes, 300_000)
        self.assertFalse(args.micro)

    def test_slot_alignment(self):
        self.assertEqual(cli.slot_for(1_800_000_123_456), 1_800_000_000_000)

    def test_summary_is_written_with_source_and_no_trading(self):
        with tempfile.TemporaryDirectory() as tmp:
            cycle_dir = Path(tmp) / "cycle-1800000000000"
            cycle_dir.mkdir(parents=True)
            bundle_path = cycle_dir / "bundle.tar.gz"
            bundle_path.write_bytes(b"bundle")
            result = CycleResult(
                slot_ms=1_800_000_000_000,
                started_ms=1_800_000_000_000,
                finished_ms=1_800_000_060_000,
                outcome="success",
                symbols_requested=3,
                symbols_ok=3,
                symbols_failed=0,
                candles_new=10,
                events=2,
                duplicates=0,
                bundle_path=str(bundle_path),
                manifest={"artifact": "cycle-1800000000000", "size_bytes": 6, "quality": {}},
                errors=[],
                metrics={"requests": 3},
            )
            cli._write_outputs(result, tmp, 1_800_000_000_000)
            summary = json.loads((cycle_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["data_source"], "Bitget USDT-FUTURES public market data")
            self.assertFalse(summary["trading_enabled"])
            self.assertEqual(summary["manifest"]["artifact"], "cycle-1800000000000")
            self.assertTrue((cycle_dir / "logs.txt").exists())

    def test_collector_refuses_to_run_without_explicit_enablement(self):
        with mock.patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli.main(["--out-dir", tmp]), 2)

    def test_collector_enabled_requires_exact_true(self):
        with mock.patch.dict(os.environ, {"PHASE_B_COLLECTOR_ENABLED": "yes"}, clear=True):
            self.assertFalse(cli.collector_enabled())
        with mock.patch.dict(os.environ, {"PHASE_B_COLLECTOR_ENABLED": "true"}, clear=True):
            self.assertTrue(cli.collector_enabled())

    def test_collector_has_no_force_bypass(self):
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            cli.parse_args(["--force"])


if __name__ == "__main__":
    unittest.main()
