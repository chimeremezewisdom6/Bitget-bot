import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from collector.bundle import build_bundle
from research import artifacts


NOW = int(datetime(2026, 11, 25, 12, tzinfo=timezone.utc).timestamp() * 1000)


class FakeTransport:
    def __init__(self, rows, blobs):
        self.rows = rows
        self.blobs = blobs
        self.json_calls = 0
        self.byte_calls = 0

    def get_json(self, url):
        self.json_calls += 1
        return {"artifacts": self.rows}

    def get_bytes(self, url):
        self.byte_calls += 1
        return self.blobs[url]


def make_artifact(artifact_id=1, name="bitget-5m-1", *, expired=False, created="2026-11-25T00:00:00Z"):
    return {
        "id": artifact_id,
        "name": name,
        "created_at": created,
        "expired": expired,
        "size_in_bytes": 100,
        "archive_download_url": f"https://example.test/{artifact_id}",
        "workflow_run": {"id": 10 + artifact_id},
    }


def make_zip(bundle_bytes, summary):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("cycle-1/bundle.tar.gz", bundle_bytes)
        archive.writestr("cycle-1/summary.json", json.dumps(summary))
    return buffer.getvalue()


def make_bundle_bytes(tmp):
    path, manifest = build_bundle(
        {"features": [{"symbol": "BTCUSDT", "ts_ms": 1}]},
        {"slot": "2026-11-25T00:00:00+00:00", "trading_enabled": False},
        tmp,
        max_bytes=100_000,
    )
    return path.read_bytes(), manifest


class PhaseBArtifactTests(unittest.TestCase):
    def test_list_filters_prefix_and_expired_is_explicit(self):
        transport = FakeTransport([
            make_artifact(1, "bitget-5m-1"),
            make_artifact(2, "other-2"),
        ], {})
        result = artifacts.list_artifacts(
            "owner/repo", transport=transport, prefix="bitget-5m-", days=3, now_ms=NOW
        )
        self.assertEqual([item.id for item in result["artifacts"]], [1])

    def test_download_and_validate_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_bytes, manifest = make_bundle_bytes(tmp)
            summary = {"outcome": "success", "manifest": manifest}
            transport = FakeTransport(
                [make_artifact(1)],
                {"https://example.test/1": make_zip(bundle_bytes, summary)},
            )
            with tempfile.TemporaryDirectory() as out:
                result = artifacts.download_bundles(
                    "owner/repo", transport=transport, days=3, out_dir=out, now_ms=NOW
                )
                self.assertEqual(result["artifacts_downloaded"], 1)
                path = Path(result["downloaded"][0]["path"])
                validated = artifacts.validate_artifact_dir(path)
                self.assertEqual(validated["status"], "OK")

    def test_expired_artifact_is_not_downloaded(self):
        transport = FakeTransport([make_artifact(1, expired=True)], {})
        with tempfile.TemporaryDirectory() as out:
            result = artifacts.download_bundles(
                "owner/repo", transport=transport, days=3, out_dir=out, now_ms=NOW
            )
        self.assertEqual(result["artifacts_downloaded"], 0)
        self.assertEqual(result["downloaded"][0]["status"], "EXPIRED")

    def test_bad_sha_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_bytes, manifest = make_bundle_bytes(tmp)
            summary = {"outcome": "success", "manifest": manifest}
            transport = FakeTransport(
                [make_artifact(1)],
                {"https://example.test/1": make_zip(bundle_bytes + b"tampered", summary)},
            )
            with tempfile.TemporaryDirectory() as out:
                result = artifacts.download_bundles(
                    "owner/repo", transport=transport, days=3, out_dir=out, now_ms=NOW
                )
                validated = artifacts.validate_artifact_dir(result["downloaded"][0]["path"])
        self.assertEqual(validated["status"], "BAD_SHA")

    def test_missing_summary_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_bytes, _ = make_bundle_bytes(tmp)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("cycle-1/bundle.tar.gz", bundle_bytes)
            transport = FakeTransport([make_artifact(1)], {"https://example.test/1": buffer.getvalue()})
            with tempfile.TemporaryDirectory() as out:
                result = artifacts.download_bundles(
                    "owner/repo", transport=transport, days=3, out_dir=out, now_ms=NOW
                )
                validated = artifacts.validate_artifact_dir(result["downloaded"][0]["path"])
        self.assertEqual(validated["status"], "INCOMPLETE")

    def test_summary_only_does_not_extract_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_bytes, manifest = make_bundle_bytes(tmp)
            summary = {"outcome": "success", "manifest": manifest}
            transport = FakeTransport(
                [make_artifact(1)],
                {"https://example.test/1": make_zip(bundle_bytes, summary)},
            )
            with tempfile.TemporaryDirectory() as out:
                result = artifacts.download_bundles(
                    "owner/repo", transport=transport, days=3, out_dir=out,
                    now_ms=NOW, summary_only=True,
                )
                path = Path(result["downloaded"][0]["path"])
                self.assertTrue((path / "cycle-1" / "summary.json").exists())
                self.assertFalse((path / "cycle-1" / "bundle.tar.gz").exists())

    def test_artifact_limit_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_bytes, manifest = make_bundle_bytes(tmp)
            summary = {"outcome": "success", "manifest": manifest}
            transport = FakeTransport(
                [make_artifact(1), make_artifact(2)],
                {
                    "https://example.test/1": make_zip(bundle_bytes, summary),
                    "https://example.test/2": make_zip(bundle_bytes, summary),
                },
            )
            with tempfile.TemporaryDirectory() as out:
                result = artifacts.download_bundles(
                    "owner/repo", transport=transport, days=3, out_dir=out,
                    now_ms=NOW, max_artifacts=1,
                )
        self.assertTrue(result["truncated"])
        self.assertEqual(result["artifacts_downloaded"], 1)


if __name__ == "__main__":
    unittest.main()
