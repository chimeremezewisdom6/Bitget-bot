# scanner.py
# Multi-timeframe momentum + exhaustion scanner.
# Every 10 minutes: rank all coins by net acceleration across 10m/20m/30m/1h.
# Logs every scan (even when no entry) so you can see what it is doing.
# PAPER ONLY until 8 consecutive wins.
# Win = close with move_pct >= 0.42%.

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("scanner")

TIMEFRAMES = [(600, "10m"), (1200, "20m"), (1800, "30m"), (3600, "1h")]
SCAN_INTERVAL_S = 600            # 10 minutes
TICK_INTERVAL_S = 5
MAX_HOLD_S = 3600

MIN_DOMINANT_RATIO = 1.3
MIN_DELTA_10M = 0.20
MIN_DELTA_20M = 0.10
MIN_TF_AGREEMENT = 2

EXIT_DELTA_NEGATIVE = -0.05
EXIT_RATIO_RETRACE = 0.20

WIN_THRESHOLD_PCT = 0.42
LIVE_UNLOCK_STREAK = 8

TRADES_PATH = Path("/tmp/scanner_trades.jsonl")
SCANS_PATH = Path("/tmp/scanner_scans.jsonl")
VALIDATION_PATH = Path("/tmp/scanner_validation.json")
WEIGHTS = {"10m": 1.0, "20m": 0.75, "30m": 0.5, "1h": 0.3}


@dataclass
class TFStats:
    ratio: float
    delta: float
    buy_volume: float
    sell_volume: float
    dominant: str


@dataclass
class CoinScan:
    symbol: str
    current_price: float
    tf_stats: dict
    dominant_side: str
    acceleration_score: float
    exhaustion_score: float
    net_score: float
    best_side: str | None


def _raw_volumes_all(buf, now):
    results = {label: [0.0, 0.0, 0.0, 0.0] for _, label in TIMEFRAMES}
    for ts, side, price, qty in buf:
        notional = price * qty
        age = now - ts
        for horizon_s, label in TIMEFRAMES:
            if age < horizon_s:
                if side == "buy":
                    results[label][0] += notional
                else:
                    results[label][1] += notional
            elif age < 2 * horizon_s:
                if side == "buy":
                    results[label][2] += notional
                else:
                    results[label][3] += notional
    return {label: tuple(v) for label, v in results.items()}


def _stats_from_raw(raw_tuple, focus_side):
    cur_buy, cur_sell, prior_buy, prior_sell = raw_tuple
    if cur_buy + cur_sell < 100:
        return None
    if focus_side == "buy":
        cur_num, cur_den = cur_buy, cur_sell
        prior_num, prior_den = prior_buy, prior_sell
    else:
        cur_num, cur_den = cur_sell, cur_buy
        prior_num, prior_den = prior_sell, prior_buy
    cur_ratio = cur_num / max(cur_den, 1.0)
    prior_ratio = (prior_num / max(prior_den, 1.0)
                   if prior_num + prior_den >= 100 else 1.0)
    return TFStats(
        ratio=round(cur_ratio, 3),
        delta=round(cur_ratio - prior_ratio, 3),
        buy_volume=round(cur_buy, 2),
        sell_volume=round(cur_sell, 2),
        dominant=focus_side,
    )


def scan_coin(symbol, state, now):
    buf = state.get("trade_buffer")
    if not buf or len(buf) < 10:
        return None
    price = state.get("current_price", 0.0)
    if price <= 0:
        return None

    raw = _raw_volumes_all(buf, now)
    cur_buy_10, cur_sell_10, _, _ = raw["10m"]
    if cur_buy_10 + cur_sell_10 < 100:
        return None

    dom = "buy" if cur_buy_10 >= cur_sell_10 else "sell"

    tf_stats = {}
    for label, rt in raw.items():
        s = _stats_from_raw(rt, dom)
        if s is not None:
            tf_stats[label] = s

    if "10m" not in tf_stats:
        return None

    agreeing = sum(
        1 for s in tf_stats.values()
        if (dom == "buy" and s.buy_volume >= s.sell_volume)
        or (dom == "sell" and s.sell_volume >= s.buy_volume)
    )

    accel = sum((s.delta * WEIGHTS[label]
                 for label, s in tf_stats.items() if s.delta > 0), 0.0)
    exhaust = sum((-s.delta * WEIGHTS[label]
                   for label, s in tf_stats.items() if s.delta < 0), 0.0)
    net = accel - exhaust

    s10 = tf_stats["10m"]
    s20 = tf_stats.get("20m")
    best_side = None
    if (s10.ratio >= MIN_DOMINANT_RATIO
            and s10.delta >= MIN_DELTA_10M
            and s20 is not None and s20.delta >= MIN_DELTA_20M
            and agreeing >= MIN_TF_AGREEMENT):
        best_side = dom

    return CoinScan(
        symbol=symbol,
        current_price=price,
        tf_stats=tf_stats,
        dominant_side=dom,
        acceleration_score=round(accel, 3),
        exhaustion_score=round(exhaust, 3),
        net_score=round(net, 3),
        best_side=best_side,
    )


def scan_all(market_state):
    now = time.time()
    results = []
    for symbol, state in list(market_state.items()):
        s = scan_coin(symbol, state, now)
        if s is not None:
            results.append(s)
    results.sort(key=lambda x: -x.net_score)
    return results


def best_entry(scans):
    for s in scans:
        if s.best_side is not None:
            return s
    return None


def should_exit(scan, entry_side, entry_ratio):
    if scan is None:
        return True, "no_data"
    s10 = scan.tf_stats.get("10m")
    if s10 is None:
        return True, "no_10m"
    if s10.dominant != entry_side:
        return True, "flipped"
    if s10.delta < EXIT_DELTA_NEGATIVE:
        return True, "fading"
    if s10.ratio < entry_ratio * (1 - EXIT_RATIO_RETRACE):
        return True, "retrace"
    return False, ""


# ============================================================
# STREAK / VALIDATION
# ============================================================

def _read_closed_trades() -> list[dict]:
    if not TRADES_PATH.exists():
        return []
    out = []
    for line in TRADES_PATH.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("action") == "close":
            out.append(rec)
    return out


def streak_count() -> int:
    trades = _read_closed_trades()
    streak = 0
    for t in reversed(trades):
        if t.get("is_win"):
            streak += 1
        else:
            break
    return streak


def streak_losses() -> int:
    trades = _read_closed_trades()
    streak = 0
    for t in reversed(trades):
        if not t.get("is_win"):
            streak += 1
        else:
            break
    return streak


def total_closed() -> int:
    return len(_read_closed_trades())


def win_rate() -> float:
    trades = _read_closed_trades()
    if not trades:
        return 0.0
    return sum(1 for t in trades if t.get("is_win")) / len(trades)


def validation_stamp() -> dict | None:
    if not VALIDATION_PATH.exists():
        return None
    try:
        return json.loads(VALIDATION_PATH.read_text())
    except Exception:
        return None


def can_go_live() -> bool:
    return validation_stamp() is not None


def _maybe_write_validation():
    if VALIDATION_PATH.exists():
        return
    streak = streak_count()
    if streak >= LIVE_UNLOCK_STREAK:
        stamp = {
            "validated_at": time.time(),
            "validated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "streak": streak,
            "threshold_pct": WIN_THRESHOLD_PCT,
            "total_trades": total_closed(),
            "win_rate": round(win_rate(), 3),
        }
        VALIDATION_PATH.write_text(json.dumps(stamp, indent=2))
        log.info("=" * 60)
        log.info("LIVE UNLOCKED — %d consecutive wins", streak)
        log.info("Validation stamp written: %s", VALIDATION_PATH)
        log.info("=" * 60)


# ============================================================
# RUNNER
# ============================================================

class ScannerRunner:
    def __init__(self):
        self._stop = asyncio.Event()
        self.position = None
        self.last_scan_ts = 0.0
        self.last_scans = []
        self.scan_count = 0
        self.last_scan_record = None
        self.scan_history = deque(maxlen=6)

    async def run(self):
        log.info("scanner started | paper only | unlock at %d consecutive wins",
                 LIVE_UNLOCK_STREAK)
        if validation_stamp():
            log.info("validation stamp already present — scanner live-eligible")
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception as e:
                log.error("scanner tick: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=TICK_INTERVAL_S)
            except asyncio.TimeoutError:
                pass

    async def _tick(self):
        from body import MARKET_STATE
        now = time.time()

        # ===== EXIT (every 5s) =====
        if self.position is not None:
            sym = self.position["symbol"]
            state = MARKET_STATE.get(sym)
            if state:
                scan = scan_coin(sym, state, now)
                exit_now, reason = should_exit(
                    scan, self.position["side"], self.position["entry_ratio"])
                if exit_now:
                    px = scan.current_price if scan else self.position["entry_price"]
                    await self._close(px, reason)
                    return
            if now - self.position["entry_ts"] >= MAX_HOLD_S:
                state = MARKET_STATE.get(sym)
                px = state["current_price"] if state else self.position["entry_price"]
                await self._close(px, "max_hold")
                return

        # ===== SCAN every 10 min =====
        if now - self.last_scan_ts >= SCAN_INTERVAL_S:
            self.scan_count += 1
            scans = scan_all(MARKET_STATE)
            self.last_scans = scans
            self.last_scan_ts = now
            best = best_entry(scans)

            if self.position is not None:
                action = "HOLDING"
            elif best is None:
                action = "NO_QUALIFIER"
            else:
                action = "OPENING"

            record = self._build_scan_record(scans, best, action, now)
            self.last_scan_record = record
            self.scan_history.append(record)
            self._log_scan_to_file(record)
            self._log_scan_to_stdout(record)

            if action == "OPENING":
                await self._open_position(best, now)

    # ---------------------------------------------------------
    # SCAN LOGGING
    # ---------------------------------------------------------

    def _build_scan_record(self, scans, best, action, now):
        top5 = [
            {
                "symbol": s.symbol,
                "side": s.best_side or s.dominant_side,
                "net": s.net_score,
                "accel": s.acceleration_score,
                "exhaust": s.exhaustion_score,
                "qualified": s.best_side is not None,
            }
            for s in scans[:5]
        ]

        position_summary = None
        if self.position is not None:
            age = now - self.position["entry_ts"]
            from body import MARKET_STATE
            cur_state = MARKET_STATE.get(self.position["symbol"], {})
            cur_px = cur_state.get("current_price", self.position["entry_price"])
            if self.position["side"] == "long":
                unrealized = (cur_px - self.position["entry_price"]) / self.position["entry_price"] * 100
            else:
                unrealized = (self.position["entry_price"] - cur_px) / self.position["entry_price"] * 100
            position_summary = {
                "symbol": self.position["symbol"],
                "side": self.position["side"],
                "age_s": round(age, 1),
                "unrealized_pct": round(unrealized, 3),
            }

        qualified = None
        if best is not None:
            qualified = {
                "symbol": best.symbol,
                "side": best.best_side,
                "net": best.net_score,
                "ratio_10m": best.tf_stats["10m"].ratio,
                "delta_10m": best.tf_stats["10m"].delta,
            }

        return {
            "scan_id": self.scan_count,
            "ts": now,
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "coins_scanned": len(scans),
            "coins_qualified": sum(1 for s in scans if s.best_side is not None),
            "qualified": qualified,
            "action": action,
            "top5": top5,
            "position": position_summary,
            "streak": streak_count(),
            "total_closed": total_closed(),
            "win_rate": round(win_rate(), 3),
            "can_go_live": can_go_live(),
        }

    def _log_scan_to_file(self, record):
        try:
            with SCANS_PATH.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            log.warning("scan log failed: %s", e)

    def _log_scan_to_stdout(self, record):
        q = record["qualified"]
        q_str = (f"{q['symbol']} {q['side']} net={q['net']:.2f} "
                 f"r10={q['ratio_10m']:.2f} d10={q['delta_10m']:.2f}"
                 if q else "None")
        top_str = " ".join(
            f"{t['symbol'].split('/')[0]}({t['net']:+.2f})"
            for t in record["top5"][:3]
        ) or "—"
        pos_str = ""
        if record["position"]:
            p = record["position"]
            pos_str = (f" | pos={p['symbol'].split('/')[0]} {p['side']} "
                       f"age={p['age_s']:.0f}s PnL={p['unrealized_pct']:+.2f}%")
        log.info(
            "SCAN #%d | action=%s | qualified=%s | scanned=%d (qualified=%d) | "
            "top3=%s | streak=%d/%d | wins=%d/%d (%.0f%%)%s",
            record["scan_id"], record["action"], q_str,
            record["coins_scanned"], record["coins_qualified"],
            top_str, record["streak"], LIVE_UNLOCK_STREAK,
            record["streak"], record["total_closed"],
            record["win_rate"] * 100, pos_str,
        )

    # ---------------------------------------------------------
    # OPEN / CLOSE
    # ---------------------------------------------------------

    async def _open_position(self, best, now):
        side = "long" if best.best_side == "buy" else "short"
        self.position = {
            "symbol": best.symbol,
            "side": side,
            "entry_price": best.current_price,
            "entry_ts": now,
            "entry_ratio": best.tf_stats["10m"].ratio,
            "accel": best.acceleration_score,
            "exhaust": best.exhaustion_score,
            "net": best.net_score,
        }
        log.info(
            "PAPER OPEN %s %s @ %.6f | r10=%.2f d10=%.2f accel=%.2f exhaust=%.2f net=%.2f",
            best.symbol, side, best.current_price,
            best.tf_stats["10m"].ratio, best.tf_stats["10m"].delta,
            best.acceleration_score, best.exhaustion_score, best.net_score,
        )
        self._log_trade({"action": "open", **self.position})

    async def _close(self, exit_px, reason):
        pos = self.position
        self.position = None
        if not pos:
            return
        if pos["side"] == "long":
            move = (exit_px - pos["entry_price"]) / pos["entry_price"] * 100
        else:
            move = (pos["entry_price"] - exit_px) / pos["entry_price"] * 100
        is_win = move >= WIN_THRESHOLD_PCT

        record = {
            "action": "close",
            "symbol": pos["symbol"],
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_px,
            "entry_ts": pos["entry_ts"],
            "exit_ts": time.time(),
            "move_pct": round(move, 3),
            "reason": reason,
            "is_win": is_win,
        }
        self._log_trade(record)

        new_streak = streak_count()
        log.info(
            "PAPER CLOSE %s %s @ %.6f | move=%+.3f%% | %s | %s | streak_now=%d/%d",
            pos["symbol"], pos["side"], exit_px, move, reason,
            "WIN" if is_win else "LOSS", new_streak, LIVE_UNLOCK_STREAK,
        )

        _maybe_write_validation()

    def _log_trade(self, record):
        try:
            with TRADES_PATH.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            log.warning("trade log failed: %s", e)

    # ---------------------------------------------------------
    # STATE VIEWS
    # ---------------------------------------------------------

    def _last_scan_view(self):
        return self.last_scan_record

    def _scan_history_view(self):
        return list(self.scan_history)

    def _recent_trades_view(self, limit=20):
        return _read_closed_trades()[-limit:]

    def _streak_view(self):
        total = total_closed()
        wins = streak_count()
        losses = streak_losses()
        return {
            "consecutive_wins": wins,
            "consecutive_losses": losses,
            "required_to_unlock": LIVE_UNLOCK_STREAK,
            "remaining": max(0, LIVE_UNLOCK_STREAK - wins),
            "total_closed": total,
            "overall_win_rate": round(win_rate(), 3),
            "can_go_live": can_go_live(),
            "validation": validation_stamp(),
        }

    def current_best_reading(self):
        if not self.last_scans:
            return None
        best = best_entry(self.last_scans)
        if not best:
            return None
        return {
            "symbol": best.symbol,
            "side": best.best_side,
            "net": best.net_score,
            "accel": best.acceleration_score,
            "exhaust": best.exhaustion_score,
            "tf": {label: {"ratio": s.ratio, "delta": s.delta}
                   for label, s in best.tf_stats.items()},
        }

    def top_5(self):
        return [
            {"symbol": s.symbol, "side": s.best_side, "net": s.net_score,
             "accel": s.acceleration_score, "exhaust": s.exhaustion_score}
            for s in self.last_scans[:5]
        ]

    def stop(self):
        self._stop.set()
