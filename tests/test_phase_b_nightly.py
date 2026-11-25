import copy
import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from collector.bundle import build_bundle
from research import nightly
from research.nightly import DAY_MS, SLOT_MS, evaluate_window
from research.spec_registry import load_registry, registry_hash


START = int(datetime(2026, 11, 20, tzinfo=timezone.utc).timestamp() * 1000)
NOW = START + 3 * DAY_MS + 2 * 3_600_000
NOW30 = START + 30 * DAY_MS + 2 * 3_600_000


def feature_row(day, slot, *, event=False):
    ts = START + day * DAY_MS + slot * SLOT_MS
    return {
        "symbol": "BTCUSDT",
        "ts_ms": ts,
        "price": 100.0,
        "turnover24h_usdt": 200_000_000.0,
        "turnover_band": "over_100m_turnover",
        "taker_fee_bps": 6.0,
        "funding_rate": 0.0001,
        "return_1m_pct": 0.02,
        "return_5m_pct": 0.05,
        "return_15m_pct": 0.05,
        "turnover_z_60m": 2.5 if event else 0.5,
        "oi_delta_15m_pct": 0.1,
        "taker_imbalance": 0.6 if event else 0.1,
        "taker_coverage_pct": 50.0,
        "taker_quality": "ADEQUATE",
        "spread_bps": 5.0,
        "bid_depth_0_5pct_usdt": 1000.0,
        "ask_depth_0_5pct_usdt": 1000.0,
        "book_imbalance_0p5": 0.0,
        "flag_0_7": False,
        "volatility_status": "OK",
        "liquidation_total_usdt": 0.0,
        "liquidation_long_usdt": 0.0,
        "liquidation_short_usdt": 0.0,
        "liquidation_records": 0,
        "liquidation_status": "PARTIAL_PAGE",
        "spot_status": "SPOT_UNMAPPED",
    }


def features_for_day(day, *, event=True):
    return [feature_row(day, slot, event=(event and slot == 120)) for slot in range(288)]


def candles_for_day(day):
    rows = []
    for index in range(1440):
        ts = START + day * DAY_MS + index * 60_000
        price = 100.0 + 0.001 * (day * 1440 + index)
        rows.append({
            "symbol": "BTCUSDT",
            "ts": ts,
            "open": price,
            "high": price + 0.02,
            "low": price - 0.02,
            "close": price + 0.01,
            "base_volume": 1.0,
            "quote_turnover": 1000.0 + index,
        })
    return rows


def write_bundles(root, *, days=3, event=True):
    for day in range(days):
        out = Path(root) / f"cycle-{day}"
        meta = {
            "schema_version": 1,
            "slot": datetime.fromtimestamp((START + day * DAY_MS) / 1000, timezone.utc).isoformat(),
            "started_ms": START + day * DAY_MS,
            "finished_ms": START + day * DAY_MS + 60_000,
            "outcome": "success",
            "trading_enabled": False,
            "data_source": "Bitget USDT-FUTURES",
        }
        _, manifest = build_bundle(
            {"features": features_for_day(day, event=event), "candles": candles_for_day(day)},
            meta,
            out,
            max_bytes=5_000_000,
        )
        (out / "summary.json").write_text(
            json.dumps({"outcome": "success", "manifest": manifest}, sort_keys=True),
            encoding="utf-8",
        )


class PhaseBNightlyTests(unittest.TestCase):
    def test_three_day_holdout_is_locked_and_samples_are_insufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_bundles(tmp)
            out = Path(tmp) / "out"
            result = evaluate_window(
                bundles_dir=tmp, days=3, out_dir=out, registry=load_registry(), now_ms=NOW
            )
            self.assertEqual(result["holdout"]["status"], "LOCKED_INSUFFICIENT_DAYS")
            self.assertEqual(result["holdout"]["complete_days"], 3)
            self.assertEqual(result["quality"]["status"], "OK")
            self.assertTrue(result["rows"])
            self.assertTrue(all(row["split"] != "holdout" for row in result["rows"]))
            taker = [
                row for row in result["rows"]
                if row["spec_id"] == "taker_aggression_v1" and row["bucket_dimension"] == "overall"
            ]
            self.assertTrue(taker)
            self.assertTrue(any(row["n"] >= 1 for row in taker))
            self.assertTrue(all(row["verdict"] == "INSUFFICIENT_SAMPLE" for row in taker))
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "data_quality.json").exists())
            self.assertTrue((out / "holdout_status.json").exists())
            self.assertTrue((out / "report.md").exists())
            self.assertTrue((out / "oi_negative.jsonl").exists())
            self.assertTrue((out / "oi_negative_summary.json").exists())

    def test_relaxed_minimums_produce_scored_metrics_without_holdout(self):
        registry = copy.deepcopy(load_registry())
        for spec in registry["specs"]:
            spec["min_n"] = {"pipeline": 1, "validation": 1, "holdout": 1}
        for key in registry["defaults"]["min_days"]:
            registry["defaults"]["min_days"][key] = 1
        for family in registry["families"].values():
            family["fdr_q"] = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            write_bundles(tmp)
            result = evaluate_window(
                bundles_dir=tmp, days=3, out_dir=Path(tmp) / "out",
                registry=registry, now_ms=NOW,
            )
            taker = [
                row for row in result["rows"]
                if row["spec_id"] == "taker_aggression_v1"
                and row["split"] == "train"
                and row["bucket_dimension"] == "overall"
            ]
            self.assertTrue(taker)
            self.assertEqual(taker[0]["sample_status"], "OK")
            self.assertGreaterEqual(taker[0]["n"], 1)
            self.assertTrue(all(row["split"] != "holdout" for row in result["rows"]))

    def test_fee_estimated_status_is_counted(self):
        items = [
            {
                "net_bps": 1.0,
                "gross_bps": 2.0,
                "fee_status": "FEE_ESTIMATED",
                "costs_bps": {"fee": 6.0, "spread": 1.0, "slippage": 2.0,
                              "funding": 0.0, "total": 9.0, "total_ex_funding": 9.0},
            },
            {
                "net_bps": 2.0,
                "gross_bps": 3.0,
                "fee_status": "PROVIDED",
                "costs_bps": {"fee": 6.0, "spread": 1.0, "slippage": 2.0,
                              "funding": 0.0, "total": 9.0, "total_ex_funding": 9.0},
            },
        ]
        summary = nightly._summary_for(items, seed=1)
        self.assertEqual(summary["fee_estimated"], 1)

    def test_no_data_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_window(
                bundles_dir=tmp, days=3, out_dir=Path(tmp) / "out",
                registry=load_registry(), now_ms=NOW,
            )
        self.assertEqual(result["quality"]["status"], "NO_DATA")
        self.assertEqual(result["holdout"]["status"], "LOCKED_INSUFFICIENT_DAYS")
        self.assertEqual(result["rows"], [])

    def test_split_profiles_are_18_6_6_and_3_day_pilot(self):
        registry = load_registry()
        standard = nightly._split_profile(30, registry)
        pilot = nightly._split_profile(3, registry)
        self.assertEqual(
            (standard["train_days"], standard["validation_days"], standard["holdout_days"]),
            (18, 6, 6),
        )
        self.assertEqual(standard["min_days"]["validation"], 6)
        self.assertEqual(standard["min_days"]["holdout"], 6)
        self.assertEqual(
            (pilot["train_days"], pilot["validation_days"], pilot["holdout_days"]),
            (1, 1, 1),
        )

    def test_holdout_requires_ledger_and_uses_utc_date(self):
        registry = load_registry()
        expected = registry_hash(registry)
        base = dict(
            days=30,
            observed_days=30,
            registry=registry,
            confirm_holdout=True,
            spec_hash=expected,
        )
        with mock.patch.object(nightly, "_utc_today", return_value=date(2026, 11, 25)):
            status, _ = nightly._holdout_status(
                **base, complete_days=29, unlock_at="2026-11-25", ledger_path=""
            )
            self.assertEqual(status, "LOCKED_INSUFFICIENT_DAYS")
            status, _ = nightly._holdout_status(
                **base, unlock_at="2026-11-25", ledger_path=""
            )
            self.assertEqual(status, "LOCKED_LEDGER_REQUIRED")
            status, _ = nightly._holdout_status(
                **base, unlock_at="2026-11-26", ledger_path=""
            )
            self.assertEqual(status, "LOCKED_AWAITING_UNLOCK_DATE")
            with tempfile.TemporaryDirectory() as tmp:
                ledger = Path(tmp) / "holdout_ledger.json"
                status, _ = nightly._holdout_status(
                    **base, unlock_at="2026-11-25", ledger_path=str(ledger)
                )
                self.assertEqual(status, "UNLOCKED")
                ledger.write_text(json.dumps({"evaluated_hashes": [expected]}), encoding="utf-8")
                status, _ = nightly._holdout_status(
                    **base, unlock_at="2026-11-25", ledger_path=str(ledger)
                )
                self.assertEqual(status, "LOCKED_ALREADY_EVALUATED")

    def test_holdout_hash_mismatch_and_authorization_are_locked(self):
        registry = load_registry()
        expected = registry_hash(registry)
        base = dict(
            days=30,
            observed_days=30,
            complete_days=30,
            registry=registry,
            unlock_at="2026-11-25",
            ledger_path="",
        )
        with mock.patch.object(nightly, "_utc_today", return_value=date(2026, 11, 25)):
            status, _ = nightly._holdout_status(
                **base, confirm_holdout=True, spec_hash="0" * 64
            )
            self.assertEqual(status, "LOCKED_HASH_MISMATCH")
            status, _ = nightly._holdout_status(
                **base, confirm_holdout=False, spec_hash=expected
            )
            self.assertEqual(status, "LOCKED_AWAITING_AUTHORIZATION")

    def test_holdout_unreadable_ledger_is_locked(self):
        registry = load_registry()
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "holdout_ledger.json"
            ledger.write_text("{not-json", encoding="utf-8")
            with mock.patch.object(nightly, "_utc_today", return_value=date(2026, 11, 25)):
                status, _ = nightly._holdout_status(
                    days=30,
                    observed_days=30,
                    complete_days=30,
                    registry=registry,
                    confirm_holdout=True,
                    spec_hash=registry_hash(registry),
                    unlock_at="2026-11-25",
                    ledger_path=str(ledger),
                )
            self.assertEqual(status, "LOCKED_LEDGER_UNREADABLE")
            ledger.write_text(json.dumps({
                "schema_version": 99,
                "evaluated_hashes": [],
            }), encoding="utf-8")
            with mock.patch.object(nightly, "_utc_today", return_value=date(2026, 11, 25)):
                status, _ = nightly._holdout_status(
                    days=30,
                    observed_days=30,
                    complete_days=30,
                    registry=registry,
                    confirm_holdout=True,
                    spec_hash=registry_hash(registry),
                    unlock_at="2026-11-25",
                    ledger_path=str(ledger),
                )
            self.assertEqual(status, "LOCKED_LEDGER_UNREADABLE")

    def test_holdout_ledger_preserves_metadata_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "evaluated_hashes": [],
                "notes": "keep-me",
            }), encoding="utf-8")
            self.assertTrue(nightly._append_holdout_ledger(path, "hash-a"))
            ledger = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["schema_version"], 2)
            self.assertEqual(ledger["notes"], "keep-me")
            self.assertEqual(ledger["evaluated_hashes"], ["hash-a"])
            self.assertEqual(
                [entry["event"] for entry in ledger["audit"]],
                ["attempted", "completed"],
            )
            self.assertNotIn(
                "results_inspected",
                [entry["event"] for entry in ledger["audit"]],
            )

    def test_holdout_audit_records_results_inspected_without_consuming_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"
            path.write_text(json.dumps({
                "schema_version": 2,
                "evaluated_hashes": ["hash-a"],
                "audit": [],
            }), encoding="utf-8")
            entry = nightly._append_holdout_audit(
                path, "results_inspected", "hash-a",
                run_id="run-1", actor="reviewer", detail="reviewed report",
            )
            self.assertEqual(entry["event"], "results_inspected")
            ledger = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["evaluated_hashes"], ["hash-a"])
            self.assertEqual(ledger["audit"][0]["event"], "results_inspected")
            self.assertEqual(ledger["audit"][0]["actor"], "reviewer")
            with self.assertRaises(nightly.LedgerError):
                nightly._append_holdout_audit(path, "results_inspected", "missing-hash")

    def test_duplicate_append_does_not_add_completed_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"
            self.assertTrue(nightly._append_holdout_ledger(path, "hash-a"))
            self.assertFalse(nightly._append_holdout_ledger(path, "hash-a"))
            ledger = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                [entry["event"] for entry in ledger["audit"]],
                ["attempted", "completed"],
            )

    def test_holdout_ledger_rejects_future_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"
            path.write_text(json.dumps({
                "schema_version": 99,
                "evaluated_hashes": [],
            }), encoding="utf-8")
            with self.assertRaises(nightly.LedgerError):
                nightly._append_holdout_ledger(path, "hash-a")

    def test_holdout_ledger_appends_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"
            self.assertTrue(nightly._append_holdout_ledger(path, "hash-a"))
            self.assertTrue(nightly._append_holdout_ledger(path, "hash-b"))
            self.assertFalse(nightly._append_holdout_ledger(path, "hash-a"))
            ledger = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["evaluated_hashes"], ["hash-a", "hash-b"])

    def test_preflight_holdout_requires_hash_and_30_days(self):
        registry = load_registry()
        expected = registry_hash(registry)
        with self.assertRaises(nightly.LedgerError):
            nightly.preflight_holdout(registry=registry, requested_hash="", days=30)
        with self.assertRaises(nightly.LedgerError):
            nightly.preflight_holdout(registry=registry, requested_hash="0" * 64, days=30)
        with self.assertRaises(nightly.LedgerError):
            nightly.preflight_holdout(registry=registry, requested_hash=expected, days=29)
        self.assertEqual(
            nightly.preflight_holdout(registry=registry, requested_hash=expected, days=30),
            expected,
        )

    def test_holdout_is_restricted_to_linux_ci(self):
        with mock.patch.dict(os.environ, {"CI": "true", "RUNNER_OS": "Linux"}):
            nightly.ensure_linux_ci()
        with mock.patch.dict(os.environ, {"CI": "true", "RUNNER_OS": "Windows"}):
            with self.assertRaises(nightly.LedgerError):
                nightly.ensure_linux_ci()

    def test_verify_holdout_state_checks_hash_and_ledger(self):
        registry = load_registry()
        expected = registry_hash(registry)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "holdout_ledger.json"
            ledger.write_text(json.dumps({
                "schema_version": 2,
                "evaluated_hashes": [],
                "audit": [],
            }), encoding="utf-8")
            with mock.patch.object(nightly, "_utc_today", return_value=date(2026, 11, 25)):
                self.assertEqual(nightly.verify_holdout_state(
                    registry=registry,
                    spec_hash=expected,
                    unlock_at="2026-11-25",
                    ledger_path=str(ledger),
                    days=30,
                ), "UNLOCKED")
            with self.assertRaises(nightly.LedgerError):
                nightly.verify_holdout_state(
                    registry=registry,
                    spec_hash=expected,
                    unlock_at="2026-11-25",
                    ledger_path=str(Path(tmp) / "missing.json"),
                    days=30,
                )

    def test_verify_holdout_result_rechecks_complete_result_and_ledger(self):
        registry = load_registry()
        expected = registry_hash(registry)
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result"
            result.mkdir()
            (result / "holdout_status.json").write_text(json.dumps({
                "status": "UNLOCKED",
                "complete": True,
                "quality_status": "OK",
                "holdout_rows": 8,
                "insufficient_overall_holdout_rows": 0,
                "insufficient_bucket_holdout_rows": 2,
                "registry_hash": expected,
            }), encoding="utf-8")
            (result / "data_quality.json").write_text(json.dumps({"status": "OK"}), encoding="utf-8")
            ledger = Path(tmp) / "holdout_ledger.json"
            ledger.write_text(json.dumps({
                "schema_version": 2,
                "evaluated_hashes": [],
                "audit": [],
            }), encoding="utf-8")
            status = nightly.verify_holdout_result(
                registry=registry,
                spec_hash=expected,
                ledger_path=str(ledger),
                result_dir=result,
                days=30,
            )
            self.assertTrue(status["complete"])
            ledger.write_text(json.dumps({
                "schema_version": 2,
                "evaluated_hashes": [expected],
                "audit": [],
            }), encoding="utf-8")
            with self.assertRaises(nightly.LedgerError):
                nightly.verify_holdout_result(
                    registry=registry,
                    spec_hash=expected,
                    ledger_path=str(ledger),
                    result_dir=result,
                    days=30,
                )

    def test_protected_environment_requires_reviewers_and_no_bypass(self):
        valid = {
            "name": "phase-b-holdout",
            "can_admins_bypass": False,
            "protection_rules": [{
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "User", "reviewer": {"login": "reviewer"}}],
            }],
        }
        nightly.validate_holdout_environment(valid)
        for bad in (
            {},
            {**valid, "name": "wrong"},
            {**valid, "can_admins_bypass": True},
            {**valid, "protection_rules": []},
            {**valid, "protection_rules": [{
                "type": "required_reviewers",
                "prevent_self_review": False,
                "reviewers": [{"type": "User"}],
            }]},
            {**valid, "protection_rules": [{
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [],
            }]},
        ):
            with self.assertRaises(nightly.LedgerError):
                nightly.validate_holdout_environment(bad)

    def test_legacy_closed_pr_without_hash_still_blocks(self):
        holdout_hash = "a" * 64
        legacy = {
            "number": 8,
            "title": "Record holdout",
            "body": "",
            "headRefName": "legacy-ledger-update",
            "mergedAt": None,
        }
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[], closed_prs=[legacy], requested_hash=holdout_hash,
            )
        self.assertEqual(
            nightly.holdout_pr_gate(
                open_prs=[], closed_prs=[legacy], requested_hash=holdout_hash,
                retry_authorization=holdout_hash,
            ),
            "RETRY_AUTHORIZED",
        )
        merged_legacy = {**legacy, "mergedAt": "2026-11-25T00:00:00Z"}
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[], closed_prs=[merged_legacy], requested_hash=holdout_hash,
            )
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[legacy, merged_legacy],
                requested_hash=holdout_hash,
                retry_authorization=holdout_hash,
            )
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[{
                    **legacy,
                    "body": f"Registry hash: {holdout_hash}",
                    "mergedAt": "2026-11-25T00:00:00Z",
                }],
                requested_hash=holdout_hash,
            )
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[{
                    **legacy,
                    "body": f"Registry hash: {holdout_hash}",
                    "mergedAt": "2026-11-25T00:00:00Z",
                }],
                requested_hash=holdout_hash,
                ledger_hashes=[holdout_hash],
            )
        old_hash = "b" * 64
        self.assertEqual(
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[{
                    **legacy,
                    "body": f"Registry hash: {old_hash}",
                    "mergedAt": "2026-11-25T00:00:00Z",
                }],
                requested_hash=holdout_hash,
                ledger_hashes=[old_hash],
            ),
            "CLEAR",
        )

    def test_closed_unmerged_pr_requires_exact_retry_authorization(self):
        holdout_hash = "a" * 64
        abandoned = {
            "number": 7,
            "title": "Record holdout",
            "body": f"Registry hash: {holdout_hash}",
            "headRefName": "holdout-ledger-123",
            "mergedAt": None,
        }
        self.assertEqual(
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[],
                requested_hash=holdout_hash,
            ),
            "CLEAR",
        )
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[{"number": 1, "headRefName": "holdout-ledger-1"}],
                closed_prs=[],
                requested_hash=holdout_hash,
            )
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[abandoned],
                requested_hash=holdout_hash,
            )
        self.assertEqual(
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[abandoned],
                requested_hash=holdout_hash,
                retry_authorization=holdout_hash,
            ),
            "RETRY_AUTHORIZED",
        )
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[],
                closed_prs=[{**abandoned, "mergedAt": "2026-11-25T00:00:00Z"}],
                requested_hash=holdout_hash,
            )
        with self.assertRaises(nightly.LedgerError):
            nightly.holdout_pr_gate(
                open_prs=[{"number": 1}, {"number": 2}],
                closed_prs=[],
                requested_hash=holdout_hash,
                max_prs=2,
            )

    def test_pr_fallback_when_mode_is_unset(self):
        self.assertTrue(nightly.should_open_ledger_pr(None, token_ok=True, push_ok=True))
        self.assertTrue(nightly.should_open_ledger_pr("", token_ok=True, push_ok=True))
        self.assertTrue(nightly.should_open_ledger_pr("pr", token_ok=True, push_ok=True))

    def test_app_token_and_push_failures_fall_back_to_pr(self):
        self.assertFalse(nightly.should_open_ledger_pr("app", token_ok=True, push_ok=True))
        self.assertTrue(nightly.should_open_ledger_pr("app", token_ok=False, push_ok=True))
        self.assertTrue(nightly.should_open_ledger_pr("app", token_ok=True, push_ok=False))

    def test_concurrent_ledger_updates_do_not_lose_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"
            hashes = [f"hash-{index}" for index in range(24)]

            def append(value):
                return nightly._append_holdout_ledger(path, value)

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(append, hashes))
            self.assertTrue(all(results))
            ledger = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["evaluated_hashes"], sorted(hashes))

    def test_duplicate_concurrent_ledger_updates_record_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"

            def append(_):
                return nightly._append_holdout_ledger(path, "same-hash")

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(append, range(16)))
            self.assertEqual(sum(1 for result in results if result), 1)
            ledger = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["evaluated_hashes"], ["same-hash"])

    def test_record_holdout_cli_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holdout_ledger.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(nightly.main(["--record-holdout", str(path), "--holdout-hash", "hash-a"]), 0)
                self.assertEqual(nightly.main(["--record-holdout", str(path), "--holdout-hash", "hash-a"]), 0)
            ledger = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["evaluated_hashes"], ["hash-a"])

    def test_holdout_complete_requires_ok_quality_and_powered_rows(self):
        rows = [{"bucket_dimension": "overall", "sample_status": "OK"}]
        self.assertTrue(nightly._holdout_complete("UNLOCKED", "OK", rows))
        self.assertFalse(nightly._holdout_complete("UNLOCKED", "PARTIAL", rows))
        self.assertFalse(nightly._holdout_complete("LOCKED_AWAITING_AUTHORIZATION", "OK", rows))
        self.assertFalse(nightly._holdout_complete("UNLOCKED", "OK", []))
        self.assertFalse(nightly._holdout_complete(
            "UNLOCKED", "OK", [{"bucket_dimension": "overall", "sample_status": "INSUFFICIENT_SAMPLE"}]
        ))
        self.assertTrue(nightly._holdout_complete(
            "UNLOCKED", "OK", [
                {"bucket_dimension": "overall", "sample_status": "OK"},
                {"bucket_dimension": "turnover_band", "sample_status": "INSUFFICIENT_SAMPLE"},
            ]
        ))

    def test_incomplete_30_day_holdout_does_not_record_ledger(self):
        registry = load_registry()
        with tempfile.TemporaryDirectory() as tmp:
            write_bundles(tmp, days=30, event=False)
            ledger = Path(tmp) / "holdout_ledger.json"
            ledger.write_text(json.dumps({"schema_version": 1, "evaluated_hashes": []}), encoding="utf-8")
            with mock.patch.object(nightly, "_utc_today", return_value=date(2026, 12, 20)):
                result = evaluate_window(
                    bundles_dir=tmp,
                    days=30,
                    out_dir=Path(tmp) / "out",
                    registry=registry,
                    now_ms=NOW30,
                    min_n_override=1,
                    confirm_holdout=True,
                    spec_hash=registry_hash(registry),
                    holdout_unlock_at="2026-12-20",
                    holdout_ledger=str(ledger),
                )
            self.assertEqual(result["holdout"]["status"], "UNLOCKED")
            self.assertFalse(result["holdout"]["evaluated"])
            self.assertGreater(result["holdout"]["holdout_rows"], 0)
            self.assertGreater(result["holdout"]["insufficient_holdout_rows"], 0)
            self.assertGreater(result["holdout"]["insufficient_overall_holdout_rows"], 0)
            self.assertEqual(result["holdout"]["insufficient_bucket_holdout_rows"], 0)
            self.assertEqual(
                json.loads(ledger.read_text(encoding="utf-8"))["evaluated_hashes"], []
            )

    def test_complete_synthetic_30_day_holdout_can_be_recorded(self):
        registry = copy.deepcopy(load_registry())
        spec = next(item for item in registry["specs"] if item["spec_id"] == "taker_aggression_v1")
        registry["specs"] = [spec]
        registry["families"] = {
            "primary_v1": {"specs": ["taker_aggression_v1"], "fdr_q": 0.10}
        }
        for item in registry["specs"]:
            item["min_n"] = {"pipeline": 1, "validation": 1, "holdout": 1}
        for profile in registry["split_profiles"].values():
            profile["min_days"] = {"pipeline": 1, "validation": 1, "holdout": 1}
        with tempfile.TemporaryDirectory() as tmp:
            write_bundles(tmp, days=30, event=True)
            ledger = Path(tmp) / "holdout_ledger.json"
            ledger.write_text(json.dumps({"schema_version": 1, "evaluated_hashes": []}), encoding="utf-8")
            with mock.patch.object(nightly, "_utc_today", return_value=date(2026, 12, 20)):
                result = evaluate_window(
                    bundles_dir=tmp,
                    days=30,
                    out_dir=Path(tmp) / "out",
                    registry=registry,
                    now_ms=NOW30,
                    min_n_override=1,
                    confirm_holdout=True,
                    spec_hash=registry_hash(registry),
                    holdout_unlock_at="2026-12-20",
                    holdout_ledger=str(ledger),
                )
            self.assertEqual(result["holdout"]["status"], "UNLOCKED")
            self.assertTrue(result["holdout"]["evaluated"])
            self.assertGreater(result["holdout"]["holdout_rows"], 0)
            self.assertEqual(result["holdout"]["insufficient_overall_holdout_rows"], 0)
            self.assertEqual(result["holdout"]["insufficient_bucket_holdout_rows"], 0)
            self.assertEqual(result["holdout"]["audit_event"], "attempted")
            self.assertIn("attempted_at", result["holdout"])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(nightly.main([
                    "--record-holdout", str(ledger),
                    "--holdout-hash", registry_hash(registry),
                ]), 0)
            self.assertEqual(
                json.loads(ledger.read_text(encoding="utf-8"))["evaluated_hashes"],
                [registry_hash(registry)],
            )

    def test_negative_oi_is_written_as_diagnostic(self):
        rows = nightly._negative_oi_rows([
            {"symbol": "BTCUSDT", "ts_ms": NOW, "oi_delta_15m_pct": -2.5, "return_15m_pct": -0.4},
            {"symbol": "BTCUSDT", "ts_ms": NOW, "oi_delta_15m_pct": -2.5, "return_15m_pct": 0.4},
            {"symbol": "BTCUSDT", "ts_ms": NOW, "oi_delta_15m_pct": -1.0, "return_15m_pct": -0.4},
        ])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["oi_price_alignment"], "ALIGNED")
        self.assertEqual(rows[1]["oi_price_alignment"], "OPPOSED")

    def test_funding_prorates_by_horizon_and_direction(self):
        feature = feature_row(0, 0)
        feature["funding_rate"] = 0.0001
        for horizon, expected in ((5, 1.0 * 5 / 480), (15, 1.0 * 15 / 480),
                                  (30, 1.0 * 30 / 480), (60, 1.0 * 60 / 480)):
            long_value, long_status = nightly._funding_bps(feature, "LONG", horizon)
            short_value, short_status = nightly._funding_bps(feature, "SHORT", horizon)
            self.assertEqual(long_status, "PROVIDED")
            self.assertEqual(short_status, "PROVIDED")
            self.assertAlmostEqual(long_value, expected, places=9)
            self.assertAlmostEqual(short_value, -expected, places=9)
        feature["funding_rate"] = None
        value, status = nightly._funding_bps(feature, "LONG", 15)
        self.assertIsNone(value)
        self.assertEqual(status, "MISSING")


if __name__ == "__main__":
    unittest.main()
