# learner.py
# Patient learning loop. 7-day minimum, 10-min observation rate limit,
# combo consistency check across days, 6 promotion gates.
# Writes 30-min findings, full daily report with action plan.

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from setup_orchestrator import db_conn

log = logging.getLogger("learner")

DAILY_DIR = Path("/tmp/daily_reports")
DAILY_DIR.mkdir(parents=True, exist_ok=True)
FINDINGS_PATH = Path("/tmp/daily_findings.jsonl")
BEST_PARAMS_PATH = Path("/tmp/best_params.json")

WIN_THRESHOLD_PCT = 0.42
RESOLVE_HORIZON_S = 180
OBSERVATION_INTERVAL_S = 600

DEFAULT_PARAMS = {
    "ofi_1m_orders_min": 1.5, "ofi_1m_volume_min": 2.0,
    "ofi_3m_orders_min": 2.0, "ofi_3m_volume_min": 3.0,
    "ofi_10m_volume_min": 1.5, "continuation_required": 4,
    "lag_gap_min": 0.5,
}

PARAM_GRID = {
    "ofi_1m_orders_min": [1.3, 1.5, 1.7],
    "ofi_1m_volume_min": [1.8, 2.0, 2.5],
    "ofi_3m_orders_min": [1.8, 2.0, 2.3],
    "ofi_3m_volume_min": [2.5, 3.0, 3.5],
    "ofi_10m_volume_min": [1.3, 1.5, 2.0],
    "continuation_required": [3, 4],
    "lag_gap_min": [0.3, 0.5, 1.0],
}

MIN_DAYS = 7
MIN_RESOLVED_OBS = 100
MIN_COMBO_TRADES = 30
MIN_WIN_RATE = 0.40
MIN_DAYS_CONFIRMED = 2

LAST_RECORDED: dict[str, float] = {}


def init_learner_tables():
    with db_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price_entry REAL NOT NULL,
                ofi_1m_orders REAL, ofi_1m_volume REAL,
                ofi_3m_orders REAL, ofi_3m_volume REAL,
                ofi_10m_volume REAL,
                continuation_score INTEGER,
                lag_gap_pct REAL,
                price_3m REAL, move_3m_pct REAL,
                resolved INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_obs_ts ON observations(ts);
            CREATE INDEX IF NOT EXISTS idx_obs_resolved ON observations(resolved);
            CREATE TABLE IF NOT EXISTS daily_top_combos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                rank INTEGER NOT NULL,
                combo_json TEXT NOT NULL,
                n INTEGER, win_rate REAL, expectancy REAL,
                UNIQUE(date, rank)
            );
        """)


def _first_observation_ts() -> float | None:
    with db_conn() as c:
        row = c.execute("SELECT MIN(ts) FROM observations").fetchone()
    return row[0] if row and row[0] else None


def _current_phase() -> dict:
    first = _first_observation_ts()
    if first is None:
        return {"phase": "COLLECTING", "day": 0.0, "progress": 0.0,
                "remaining_days": float(MIN_DAYS), "reason": "no data yet"}
    days = (time.time() - first) / 86400.0
    progress = min(days / MIN_DAYS, 1.0)
    if days < 3:
        phase, remaining = "COLLECTING", 3 - days
    elif days < 5:
        phase, remaining = "EVALUATING", 5 - days
    elif days < MIN_DAYS:
        phase, remaining = "VALIDATING", MIN_DAYS - days
    else:
        phase, remaining = "ACTIONABLE", 0.0
    return {
        "phase": phase,
        "day": round(days, 2),
        "progress": round(progress, 3),
        "remaining_days": round(remaining, 2),
        "reason": f"{remaining:.1f}d remaining" if remaining > 0 else "time gate passed",
    }


# ============================================================
# OBSERVATION COLLECTION
# ============================================================

def _loose_candidate(state: dict) -> dict | None:
    from brain import _dominant, _window_ratios, continuation_score

    now = time.time()
    s1 = state["win_1m"].stats(now)
    s3 = state["win_3m"].stats(now)
    s10 = state["win_10m"].stats(now)

    if s1["buy_volume"] + s1["sell_volume"] < 100:
        return None

    d1, o1 = _dominant(s1)
    d3, _ = _dominant(s3)
    d10, _ = _dominant(s10)
    if not (d1 == d3 == d10):
        return None

    r1o, r1v = _window_ratios(s1, d1, o1)
    r3o, r3v = _window_ratios(s3, d1, o1)
    r10v = s10[f"{d1}_volume"] / max(s10[f"{o1}_volume"], 1)

    if r1v < 1.2 or r3v < 1.3 or r10v < 1.1:
        return None

    score, _ = continuation_score(
        state["win_1m"], state["win_3m"], state["win_10m"],
        list(state.get("minute_volumes", [])),
        list(state.get("price_series", [])),
    )
    return {
        "side": d1,
        "price_entry": state["current_price"],
        "ofi_1m_orders": r1o, "ofi_1m_volume": r1v,
        "ofi_3m_orders": r3o, "ofi_3m_volume": r3v,
        "ofi_10m_volume": r10v,
        "continuation_score": score,
        "lag_gap_pct": state.get("lag_gap_pct", 0.0),
    }


def _record_observation(symbol: str, cand: dict):
    with db_conn() as c:
        c.execute(
            """INSERT INTO observations
               (ts, symbol, side, price_entry,
                ofi_1m_orders, ofi_1m_volume, ofi_3m_orders, ofi_3m_volume,
                ofi_10m_volume, continuation_score, lag_gap_pct)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (time.time(), symbol, cand["side"], cand["price_entry"],
             cand["ofi_1m_orders"], cand["ofi_1m_volume"],
             cand["ofi_3m_orders"], cand["ofi_3m_volume"],
             cand["ofi_10m_volume"], cand["continuation_score"], cand["lag_gap_pct"]),
        )


def _resolve_pending(market_state: dict):
    cutoff = time.time() - RESOLVE_HORIZON_S
    with db_conn() as c:
        rows = c.execute(
            "SELECT id, symbol, side, price_entry FROM observations "
            "WHERE resolved=0 AND ts <= ?", (cutoff,)
        ).fetchall()
        for obs_id, symbol, side, entry in rows:
            state = market_state.get(symbol)
            if not state or not state.get("current_price"):
                continue
            exit_px = state["current_price"]
            move = ((exit_px - entry) / entry * 100.0 if side == "buy"
                    else (entry - exit_px) / entry * 100.0)
            c.execute(
                "UPDATE observations SET price_3m=?, move_3m_pct=?, resolved=1 WHERE id=?",
                (exit_px, move, obs_id),
            )


def _fetch_observations(since_ts: float) -> list[dict]:
    with db_conn() as c:
        rows = c.execute(
            """SELECT symbol, side, ofi_1m_orders, ofi_1m_volume, ofi_3m_orders,
                      ofi_3m_volume, ofi_10m_volume, continuation_score, lag_gap_pct,
                      move_3m_pct
               FROM observations WHERE resolved=1 AND ts >= ?""", (since_ts,)
        ).fetchall()
    keys = ["symbol", "side", "ofi_1m_orders", "ofi_1m_volume", "ofi_3m_orders",
            "ofi_3m_volume", "ofi_10m_volume", "continuation_score", "lag_gap_pct",
            "move_3m_pct"]
    return [dict(zip(keys, r)) for r in rows]


def _resolved_count() -> int:
    with db_conn() as c:
        return c.execute("SELECT COUNT(*) FROM observations WHERE resolved=1").fetchone()[0]


# ============================================================
# PARAMETER SEARCH
# ============================================================

def _iter_combos():
    keys = list(PARAM_GRID.keys())
    def rec(i, acc):
        if i == len(keys):
            yield dict(acc)
            return
        for v in PARAM_GRID[keys[i]]:
            acc[keys[i]] = v
            yield from rec(i + 1, acc)
    yield from rec(0, {})


def _passes(obs: dict, combo: dict) -> bool:
    return (
        obs["ofi_1m_orders"] >= combo["ofi_1m_orders_min"]
        and obs["ofi_1m_volume"] >= combo["ofi_1m_volume_min"]
        and obs["ofi_3m_orders"] >= combo["ofi_3m_orders_min"]
        and obs["ofi_3m_volume"] >= combo["ofi_3m_volume_min"]
        and obs["ofi_10m_volume"] >= combo["ofi_10m_volume_min"]
        and obs["continuation_score"] >= combo["continuation_required"]
        and obs["lag_gap_pct"] >= combo["lag_gap_min"]
    )


def _evaluate_combos(observations: list[dict]) -> list[dict]:
    results = []
    for combo in _iter_combos():
        filtered = [o for o in observations if _passes(o, combo)]
        if len(filtered) < 5:
            continue
        wins = [o for o in filtered if o["move_3m_pct"] >= WIN_THRESHOLD_PCT]
        losses = [o for o in filtered if o["move_3m_pct"] < WIN_THRESHOLD_PCT]
        if not wins or not losses:
            continue
        wr = len(wins) / len(filtered)
        avg_w = mean(o["move_3m_pct"] for o in wins)
        avg_l = mean(o["move_3m_pct"] for o in losses)
        results.append({**combo,
                        "n": len(filtered),
                        "win_rate": round(wr, 3),
                        "avg_win": round(avg_w, 3),
                        "avg_loss": round(avg_l, 3),
                        "expectancy": round(wr * avg_w + (1 - wr) * avg_l, 3)})
    return sorted(results, key=lambda x: -x["expectancy"])


def _persist_top_combos(date_str: str, combos: list[dict]):
    with db_conn() as c:
        for rank, combo in enumerate(combos[:3], 1):
            c.execute(
                """INSERT OR REPLACE INTO daily_top_combos
                   (date, rank, combo_json, n, win_rate, expectancy)
                   VALUES (?,?,?,?,?,?)""",
                (date_str, rank,
                 json.dumps({k: combo[k] for k in DEFAULT_PARAMS}),
                 combo["n"], combo["win_rate"], combo["expectancy"]),
            )


def _combo_confirmed_days(combo: dict) -> int:
    with db_conn() as c:
        rows = c.execute(
            "SELECT date, combo_json FROM daily_top_combos WHERE rank <= 3"
        ).fetchall()
    matching = set()
    for date, cj in rows:
        stored = json.loads(cj)
        if all(stored.get(k) == combo.get(k) for k in DEFAULT_PARAMS.keys()):
            matching.add(date)
    return len(matching)


def _check_gates() -> dict:
    phase = _current_phase()
    resolved = _resolved_count()
    obs_7d = _fetch_observations(time.time() - 7 * 86400)
    combos = _evaluate_combos(obs_7d) if obs_7d else []
    top = combos[0] if combos else None

    gates = [
        {"name": "phase_actionable",
         "pass": phase["phase"] == "ACTIONABLE",
         "detail": f"phase={phase['phase']}, day={phase['day']}"},
        {"name": "enough_observations",
         "pass": resolved >= MIN_RESOLVED_OBS,
         "detail": f"{resolved}/{MIN_RESOLVED_OBS} resolved"},
        {"name": "combo_exists",
         "pass": top is not None,
         "detail": "top combo found" if top else "no valid combo"},
        {"name": "combo_sample_size",
         "pass": bool(top and top["n"] >= MIN_COMBO_TRADES),
         "detail": f"{top['n'] if top else 0}/{MIN_COMBO_TRADES} trades"},
        {"name": "combo_win_rate",
         "pass": bool(top and top["win_rate"] >= MIN_WIN_RATE),
         "detail": f"{top['win_rate']:.0%}" if top else "n/a"},
        {"name": "combo_expectancy",
         "pass": bool(top and top["expectancy"] > 0),
         "detail": f"{top['expectancy']:+.2f}%" if top else "n/a"},
        {"name": "confirmed_across_days",
         "pass": bool(top and _combo_confirmed_days(top) >= MIN_DAYS_CONFIRMED),
         "detail": f"{_combo_confirmed_days(top) if top else 0}/{MIN_DAYS_CONFIRMED} days"},
    ]
    all_pass = all(g["pass"] for g in gates)
    return {"phase": phase, "gates": gates, "all_pass": all_pass,
            "top_combo": top, "resolved": resolved}


def _write_30min_finding(session_start: float):
    now = time.time()
    obs = _fetch_observations(session_start)
    phase = _current_phase()
    summary = {
        "ts": now, "phase": phase["phase"], "day": phase["day"],
        "window_min": round((now - session_start) / 60, 1),
        "observations": len(obs),
    }
    if obs:
        wins = [o for o in obs if o["move_3m_pct"] >= WIN_THRESHOLD_PCT]
        losses = [o for o in obs if o["move_3m_pct"] < WIN_THRESHOLD_PCT]
        summary["wins"] = len(wins)
        summary["losses"] = len(losses)
        if wins:
            summary["avg_win"] = round(mean(o["move_3m_pct"] for o in wins), 3)
        if losses:
            summary["avg_loss"] = round(mean(o["move_3m_pct"] for o in losses), 3)
        if phase["phase"] in ("EVALUATING", "VALIDATING", "ACTIONABLE"):
            combos = _evaluate_combos(obs)
            if combos:
                summary["best_combo_expectancy"] = combos[0]["expectancy"]
    with FINDINGS_PATH.open("a") as f:
        f.write(json.dumps(summary) + "\n")
    log.info("30-min | phase=%s day=%.1f obs=%d",
             summary["phase"], summary["day"], summary["observations"])


def _write_daily_report():
    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = DAILY_DIR / f"{today}.md"
    gate_result = _check_gates()
    phase = gate_result["phase"]
    obs_7d = _fetch_observations(now - 7 * 86400)
    combos = _evaluate_combos(obs_7d) if obs_7d else []

    lines = [f"# Daily Learning Report — {today}\n"]

    bar_len = 20
    filled = int(phase["progress"] * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    lines.append(f"## Phase: **{phase['phase']}** — Day {phase['day']:.1f} of {MIN_DAYS}\n")
    lines.append(f"`[{bar}]` {phase['progress']*100:.0f}%  ·  {phase['reason']}\n")

    lines.append("## Promotion Gates\n")
    for g in gate_result["gates"]:
        mark = "✅" if g["pass"] else "❌"
        lines.append(f"- {mark} **{g['name']}** — {g['detail']}")
    lines.append("")

    lines.append("## 7-Day Data\n")
    lines.append(f"- Resolved observations: **{gate_result['resolved']}** (gate: {MIN_RESOLVED_OBS})")
    if obs_7d:
        wins = [o for o in obs_7d if o["move_3m_pct"] >= WIN_THRESHOLD_PCT]
        losses = [o for o in obs_7d if o["move_3m_pct"] < WIN_THRESHOLD_PCT]
        lines.append(f"- All observations: {len(obs_7d)} · "
                     f"Wins: {len(wins)} · Losses: {len(losses)} · "
                     f"Raw win rate: {len(wins)/len(obs_7d):.1%}")
    lines.append("")

    lines.append("## Best Combinations (7-day window)\n")
    if not combos:
        lines.append("_No combination meets the 5-trade floor yet._\n")
    else:
        lines.append("| # | Score≥ | 1m o/v | 3m o/v | 10m v | Lag | N | WR | Exp | Confirmed |")
        lines.append("|---|--------|--------|--------|-------|---|-----|-----|-----|-----------|")
        for i, c in enumerate(combos[:5], 1):
            confirmed = _combo_confirmed_days(c)
            lines.append(
                f"| {i} | {c['continuation_required']} | "
                f"{c['ofi_1m_orders_min']}/{c['ofi_1m_volume_min']} | "
                f"{c['ofi_3m_orders_min']}/{c['ofi_3m_volume_min']} | "
                f"{c['ofi_10m_volume_min']} | {c['lag_gap_min']} | "
                f"{c['n']} | {c['win_rate']:.0%} | {c['expectancy']:+.2f}% | "
                f"{confirmed}/{MIN_DAYS_CONFIRMED} |"
            )
        lines.append("")
        _persist_top_combos(today, combos)

    lines.append("## Action Plan\n")
    if gate_result["all_pass"]:
        top = gate_result["top_combo"]
        params = {k: top[k] for k in DEFAULT_PARAMS}
        params["_validation"] = {
            "phase": "ACTIONABLE", "validated_at": now,
            "day": phase["day"], "resolved_obs": gate_result["resolved"],
            "win_rate": top["win_rate"], "expectancy": top["expectancy"],
            "confirmed_days": _combo_confirmed_days(top),
        }
        BEST_PARAMS_PATH.write_text(json.dumps(params, indent=2))
        lines.append("**STATUS: ACTIONABLE ✅** All gates passed. Params promoted.\n")
        for k, v in params.items():
            if k != "_validation":
                lines.append(f"- `{k}`: **{v}**")
        lines.append(f"\nExpected: {top['win_rate']:.0%} win rate · "
                     f"{top['expectancy']:+.2f}% expectancy · "
                     f"{top['n']} trades over {_combo_confirmed_days(top)} days")
    else:
        failing = [g["name"] for g in gate_result["gates"] if not g["pass"]]
        lines.append(f"**STATUS: GATHERING EVIDENCE**\n")
        lines.append(f"Blocking gates: {', '.join(failing)}")
        lines.append(f"\nNo parameters will be promoted today.")
        lines.append(f"`live_runner.py` will refuse to trade live until all gates pass.")

    report_path.write_text("\n".join(lines))
    log.info("daily report → %s | phase=%s all_pass=%s",
             report_path, phase["phase"], gate_result["all_pass"])


class Learner:
    def __init__(self):
        self._stop = asyncio.Event()
        self.last_30min = time.time()
        self.today = datetime.now(timezone.utc).date()

    async def run(self):
        init_learner_tables()
        log.info("learner started | phase=%s", _current_phase()["phase"])
        while not self._stop.is_set():
            try:
                from body import MARKET_STATE
                await self._sample(MARKET_STATE)
                _resolve_pending(MARKET_STATE)

                now = time.time()
                if now - self.last_30min >= 1800:
                    _write_30min_finding(self.last_30min)
                    self.last_30min = now

                today = datetime.now(timezone.utc).date()
                if today != self.today:
                    _write_daily_report()
                    self.today = today
                    self.last_30min = now
            except Exception as e:
                log.error("learner cycle error: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

    async def _sample(self, market_state: dict):
        now = time.time()
        for symbol, state in list(market_state.items()):
            if now - state.get("last_updated", 0) > 60:
                continue
            if now - LAST_RECORDED.get(symbol, 0) < OBSERVATION_INTERVAL_S:
                continue
            cand = _loose_candidate(state)
            if cand:
                _record_observation(symbol, cand)
                LAST_RECORDED[symbol] = now

    def stop(self):
        self._stop.set()
