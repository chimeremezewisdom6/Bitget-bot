# test_harness.py
# Startup self-test. Pure computation. Runs in ~1 second.

import asyncio
import logging
import time
from typing import Any, Callable

log = logging.getLogger("test_harness")


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: list[dict] = []

    def ok(self, name: str):
        self.passed += 1
        log.debug("✓ %s", name)

    def fail(self, name: str, err: str):
        self.failed += 1
        self.failures.append({"test": name, "error": err})
        log.warning("✗ %s — %s", name, err)

    def to_dict(self):
        return {"passed": self.passed, "failed": self.failed, "failures": self.failures}


async def _run(name: str, fn: Callable[[], None], result: TestResult):
    try:
        fn()
        result.ok(name)
    except AssertionError as e:
        result.fail(name, f"assertion: {e}")
    except Exception as e:
        result.fail(name, f"{type(e).__name__}: {e}")


def test_config_validates_good():
    from setup_orchestrator import ConfigContract
    cfg = ConfigContract(leverage=3, risk_pct=0.90, fee_roundtrip_pct=0.22, min_net_profit_pct=0.20)
    assert cfg.win_threshold_pct == 0.42


def test_config_rejects_risk_gt_1():
    from setup_orchestrator import ConfigContract
    from pydantic import ValidationError
    try:
        ConfigContract(risk_pct=1.2)
        raise AssertionError("should have rejected risk_pct=1.2")
    except ValidationError:
        pass


def test_config_rejects_bad_venue():
    from setup_orchestrator import ConfigContract
    from pydantic import ValidationError
    try:
        ConfigContract(execution_venue="kraken")
        raise AssertionError("should have rejected unknown venue")
    except ValidationError:
        pass


def test_classifier_long_win_at_threshold():
    from setup_orchestrator import classify
    is_win, move = classify(1.00, 1.0042, "long", 0.42)
    assert is_win is True
    assert abs(move - 0.42) < 0.001


def test_classifier_long_loss_below_threshold():
    from setup_orchestrator import classify
    is_win, move = classify(1.00, 1.0030, "long", 0.42)
    assert is_win is False
    assert move < 0.42


def test_classifier_short_win():
    from setup_orchestrator import classify
    is_win, _ = classify(1.00, 0.9958, "short", 0.42)
    assert is_win is True


def test_sqlite_roundtrip():
    from setup_orchestrator import db_conn
    with db_conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS _test (v INTEGER)")
        c.execute("INSERT INTO _test (v) VALUES (42)")
        row = c.execute("SELECT v FROM _test WHERE v=42").fetchone()
        assert row[0] == 42
        c.execute("DROP TABLE _test")


def test_ofi_window_add_and_stats():
    from brain import OfiWindow
    w = OfiWindow(60)
    now = time.time()
    for i in range(5):
        w.add(now - i, "buy", 1.00, 10.0)
    for i in range(3):
        w.add(now - i, "sell", 1.00, 10.0)
    s = w.stats(now)
    assert s["buy_orders"] == 5
    assert s["sell_orders"] == 3
    assert abs(s["buy_volume"] - 50.0) < 0.01


def test_ofi_window_eviction():
    from brain import OfiWindow
    w = OfiWindow(10)
    now = time.time()
    w.add(now - 30, "buy", 1.0, 1.0)
    w.add(now - 5, "buy", 1.0, 1.0)
    s = w.stats(now)
    assert s["buy_orders"] == 1


def test_ratio_handles_zero():
    from brain import _ratio
    assert _ratio(5, 0) == float("inf")
    assert _ratio(0, 0) == 0.0


def test_dominant_buy():
    from brain import _dominant
    side, opp = _dominant({"buy_volume": 100, "sell_volume": 50, "buy_orders": 1, "sell_orders": 1})
    assert side == "buy" and opp == "sell"


def test_continuation_score_perfect():
    from brain import OfiWindow, continuation_score
    now = time.time()
    w1, w3, w10 = OfiWindow(60), OfiWindow(180), OfiWindow(600)
    for i in range(5):
        w1.add(now - i, "buy", 1.0, 20.0)
    for i in range(5):
        w3.add(now - i, "buy", 1.0, 20.0)
    for i in range(5):
        w10.add(now - i, "buy", 1.0, 20.0)
    prices = [1.0, 0.99, 1.0, 1.01, 1.005]
    score, _ = continuation_score(w1, w3, w10, [10, 12, 15], prices)
    assert score >= 2


def test_decide_entry_blocked_by_score():
    from brain import OfiWindow, decide_entry
    now = time.time()
    w1, w3, w10 = OfiWindow(60), OfiWindow(180), OfiWindow(600)
    w1.add(now, "buy", 1.0, 1.0)
    w3.add(now, "buy", 1.0, 1.0)
    w10.add(now, "buy", 1.0, 1.0)
    result = decide_entry("TEST", {"passed": True}, w1, w3, w10, required_score=4)
    assert result is None


def test_slippage_thin_book():
    from body import compute_slippage_from_levels
    levels = [[1.00, 10000.0], [1.01, 10000.0]]
    slip = compute_slippage_from_levels(levels, "buy", 5000.0)
    assert 0.0 <= slip <= 1.0


def test_slippage_deep_book():
    from body import compute_slippage_from_levels
    levels = [[1.00, 100000.0], [1.01, 100000.0]]
    slip = compute_slippage_from_levels(levels, "buy", 5000.0)
    assert slip < 0.001


def test_slippage_insufficient_depth():
    from body import compute_slippage_from_levels
    levels = [[1.00, 1.0]]
    slip = compute_slippage_from_levels(levels, "buy", 100000.0)
    assert slip >= 999.0


def test_price_cache_move():
    from lead_lag import PriceCache
    c = PriceCache(600)
    now = time.time()
    c.add(now - 100, 1.00)
    c.add(now, 1.02)
    assert abs(c.move_pct(now) - 2.0) < 0.01


def test_price_cache_eviction():
    from lead_lag import PriceCache
    c = PriceCache(10)
    now = time.time()
    c.add(now - 30, 1.00)
    c.add(now, 1.02)
    assert abs(c.move_pct(now) - 2.0) < 0.01


def test_scanner_classifier_win():
    from scanner import WIN_THRESHOLD_PCT
    move = 0.45
    assert (move >= WIN_THRESHOLD_PCT) is True


def test_scanner_classifier_loss():
    from scanner import WIN_THRESHOLD_PCT
    move = 0.30
    assert (move >= WIN_THRESHOLD_PCT) is False


async def run_all_tests() -> dict[str, Any]:
    result = TestResult()
    tests = [
        ("config_validates_good", test_config_validates_good),
        ("config_rejects_risk_gt_1", test_config_rejects_risk_gt_1),
        ("config_rejects_bad_venue", test_config_rejects_bad_venue),
        ("classifier_long_win_at_threshold", test_classifier_long_win_at_threshold),
        ("classifier_long_loss_below_threshold", test_classifier_long_loss_below_threshold),
        ("classifier_short_win", test_classifier_short_win),
        ("sqlite_roundtrip", test_sqlite_roundtrip),
        ("ofi_window_add_and_stats", test_ofi_window_add_and_stats),
        ("ofi_window_eviction", test_ofi_window_eviction),
        ("ratio_handles_zero", test_ratio_handles_zero),
        ("dominant_buy", test_dominant_buy),
        ("continuation_score_perfect", test_continuation_score_perfect),
        ("decide_entry_blocked_by_score", test_decide_entry_blocked_by_score),
        ("slippage_thin_book", test_slippage_thin_book),
        ("slippage_deep_book", test_slippage_deep_book),
        ("slippage_insufficient_depth", test_slippage_insufficient_depth),
        ("price_cache_move", test_price_cache_move),
        ("price_cache_eviction", test_price_cache_eviction),
        ("scanner_classifier_win", test_scanner_classifier_win),
        ("scanner_classifier_loss", test_scanner_classifier_loss),
    ]
    for name, fn in tests:
        await _run(name, fn, result)
    log.info("SELF-TEST: %d passed, %d failed", result.passed, result.failed)
    return result.to_dict()
