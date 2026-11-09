# setup_orchestrator.py
# FastAPI entrypoint. Config contract, SQLite ledger, 4h volume aggregation.
# Lifespan: self-test → learner → setup → body → scanner.
# Endpoints for /health, /learnings, /report/today, /scanner*.

import asyncio
import json
import os
import sqlite3
import time
import logging
from contextlib import asynccontextmanager
from typing import Any

import ccxt.async_support as ccxt
from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError, field_validator

from scanner import ScannerRunner, SCAN_INTERVAL_S

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("setup")

# ============================================================
# CONTRACT
# ============================================================

class ConfigContract(BaseModel):
    model_config = {"extra": "forbid"}

    leverage: int = Field(default=3, ge=1, le=10)
    risk_pct: float = Field(default=0.90, gt=0, lt=1.0)
    fee_roundtrip_pct: float = Field(default=0.22, gt=0)
    min_net_profit_pct: float = Field(default=0.20, ge=0)
    min_vol_ratio_vs_mcap: float = Field(default=0.05, gt=0)
    min_big8_share: float = Field(default=0.85, ge=0.5, le=1.0)
    max_concurrent_fetches: int = Field(default=20, ge=5, le=50)
    per_task_timeout_s: float = Field(default=2.0, gt=0, le=10.0)
    cycle_interval_s: int = Field(default=4 * 3600, ge=60)
    required_win_streak: int = Field(default=6, ge=1, le=20)
    paper_mode: bool = Field(default=True)
    continuation_required_score: int = Field(default=4, ge=0, le=4)
    trailing_stop_pct: float = Field(default=1.0, gt=0, le=5.0)
    max_slippage_pct: float = Field(default=0.05, gt=0, le=1.0)
    execution_venue: str = Field(default="bitget")

    @field_validator("execution_venue")
    @classmethod
    def venue_valid(cls, v):
        if v not in ("bitget", "mexc"):
            raise ValueError("execution_venue must be 'bitget' or 'mexc'")
        return v

    @property
    def win_threshold_pct(self) -> float:
        return self.fee_roundtrip_pct + self.min_net_profit_pct

# ============================================================
# PERSISTENCE
# ============================================================

DB_PATH = os.environ.get("SETUP_DB", "/tmp/setup.db")

def db_conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c

def init_db():
    with db_conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS config_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                config_json TEXT NOT NULL,
                is_known_good INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL, kind TEXT NOT NULL, detail TEXT
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_open REAL NOT NULL, ts_close REAL NOT NULL,
                symbol TEXT NOT NULL, side TEXT NOT NULL,
                entry_price REAL NOT NULL, exit_price REAL NOT NULL,
                move_pct REAL NOT NULL, is_win INTEGER NOT NULL,
                is_paper INTEGER NOT NULL DEFAULT 1, balance_after REAL
            );
        """)

def save_cfg(cfg: ConfigContract, known_good: bool):
    with db_conn() as c:
        c.execute("INSERT INTO config_snapshots (ts, config_json, is_known_good) VALUES (?, ?, ?)",
                  (time.time(), cfg.model_dump_json(), int(known_good)))

def load_known_good() -> ConfigContract | None:
    with db_conn() as c:
        row = c.execute("SELECT config_json FROM config_snapshots WHERE is_known_good=1 ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    try:
        return ConfigContract.model_validate_json(row[0])
    except ValidationError:
        return None

def record_incident(kind: str, detail: str = ""):
    with db_conn() as c:
        c.execute("INSERT INTO incidents (ts, kind, detail) VALUES (?, ?, ?)", (time.time(), kind, detail))
    log.warning("incident: %s | %s", kind, detail)

def resolve_config(candidate: dict[str, Any]) -> ConfigContract:
    try:
        cfg = ConfigContract.model_validate(candidate)
        save_cfg(cfg, known_good=False)
        return cfg
    except ValidationError as e:
        record_incident("config_invalid", str(e))
        fallback = load_known_good()
        if fallback:
            log.info("rolled back to last known-good config")
            return fallback
        log.warning("no known-good snapshot; using safe defaults")
        return ConfigContract()

def promote(cfg: ConfigContract):
    save_cfg(cfg, known_good=True)

# ============================================================
# WIN / LOSS
# ============================================================

def classify(entry: float, exit_: float, side: str, threshold: float) -> tuple[bool, float]:
    if side == "long":
        move = (exit_ - entry) / entry * 100.0
    elif side == "short":
        move = (entry - exit_) / entry * 100.0
    else:
        raise ValueError(f"bad side: {side}")
    return (move >= threshold), move

def record_close(cfg: ConfigContract, symbol: str, side: str, entry: float, exit_: float,
                 ts_open: float, balance_after: float | None = None, is_paper: bool = True) -> dict:
    is_win, move = classify(entry, exit_, side, cfg.win_threshold_pct)
    with db_conn() as c:
        c.execute(
            """INSERT INTO trades (ts_open, ts_close, symbol, side, entry_price, exit_price,
               move_pct, is_win, is_paper, balance_after) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ts_open, time.time(), symbol, side, entry, exit_, move, int(is_win), int(is_paper), balance_after),
        )
    out = {"symbol": symbol, "side": side, "move_pct": round(move, 4),
           "threshold_pct": cfg.win_threshold_pct, "is_win": is_win,
           "note": "WIN" if is_win else f"LOSS ({move:+.2f}% < {cfg.win_threshold_pct:.2f}%)"}
    log.info("trade closed: %s", out)
    return out

def streak(cfg: ConfigContract, is_paper: bool = True) -> int:
    with db_conn() as c:
        rows = c.execute("SELECT is_win FROM trades WHERE is_paper=? ORDER BY id DESC", (int(is_paper),)).fetchall()
    n = 0
    for (w,) in rows:
        if w:
            n += 1
        else:
            break
    return n

# ============================================================
# VOLUME AGGREGATION
# ============================================================

BIG8 = ["binance", "bybit", "okx", "kucoin", "bitget", "mexc", "bingx", "gate"]
GLOBAL = list(set(BIG8 + ["bitfinex", "kraken", "coinbase", "htx", "cryptocom", "upbit", "bithumb"]))

async def _vol(ex_id: str, symbol: str, sem: asyncio.Semaphore, timeout: float):
    async with sem:
        ex = None
        try:
            ex = getattr(ccxt, ex_id)({"enableRateLimit": True})
            ohlcv = await asyncio.wait_for(ex.fetch_ohlcv(symbol, "4h", limit=1), timeout)
            return ex_id, float(ohlcv[0][5]) if ohlcv and ohlcv[0] else None
        except Exception:
            return ex_id, None
        finally:
            if ex is not None:
                await ex.close()

async def aggregate(symbol: str, cfg: ConfigContract) -> dict:
    sem = asyncio.Semaphore(cfg.max_concurrent_fetches)
    tasks = [asyncio.create_task(_vol(x, symbol, sem, cfg.per_task_timeout_s), name=x) for x in GLOBAL]
    big8_total = global_total = 0.0
    for coro in asyncio.as_completed(tasks):
        try:
            ex_id, v = await coro
        except Exception:
            continue
        if v is None:
            continue
        global_total += v
        if ex_id in BIG8:
            big8_total += v
    share = big8_total / global_total if global_total > 0 else 0.0
    return {"symbol": symbol, "big8_share": share, "passed": share >= cfg.min_big8_share}

# ============================================================
# ORCHESTRATOR
# ============================================================

class Orchestrator:
    def __init__(self):
        self.cfg: ConfigContract | None = None
        self._stop = asyncio.Event()

    def _candidate(self) -> dict:
        return {
            "leverage": int(os.environ.get("LEVERAGE", "3")),
            "risk_pct": float(os.environ.get("RISK_PCT", "0.90")),
            "fee_roundtrip_pct": float(os.environ.get("FEE_PCT", "0.22")),
            "min_net_profit_pct": float(os.environ.get("MIN_NET_PROFIT", "0.20")),
            "min_vol_ratio_vs_mcap": float(os.environ.get("MIN_VOL_RATIO", "0.05")),
            "min_big8_share": float(os.environ.get("MIN_BIG8_SHARE", "0.85")),
            "required_win_streak": int(os.environ.get("REQ_WIN_STREAK", "6")),
            "paper_mode": os.environ.get("PAPER_MODE", "true").lower() == "true",
            "execution_venue": os.environ.get("EXECUTION_VENUE", "bitget"),
            "trailing_stop_pct": float(os.environ.get("TRAILING_STOP_PCT", "1.0")),
            "continuation_required_score": int(os.environ.get("CONTINUATION_REQUIRED", "4")),
            "max_slippage_pct": float(os.environ.get("MAX_SLIPPAGE", "0.05")),
        }

    async def run(self, symbols: list[str]):
        while not self._stop.is_set():
            try:
                self.cfg = resolve_config(self._candidate())
                for sym in symbols:
                    r = await aggregate(sym, self.cfg)
                    log.info("%s big8_share=%.3f pass=%s", sym, r["big8_share"], r["passed"])
                promote(self.cfg)
            except Exception as e:
                record_incident("cycle_exception", repr(e))
                log.exception("cycle failed")
            try:
                await asyncio.wait_for(self._stop.wait(),
                                       timeout=self.cfg.cycle_interval_s if self.cfg else 4 * 3600)
            except asyncio.TimeoutError:
                pass

    def stop(self):
        self._stop.set()

orchestrator = Orchestrator()
_scanner: ScannerRunner | None = None

# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from test_harness import run_all_tests
    test_result = await run_all_tests()
    if test_result["failed"] > 0:
        record_incident("self_test_failed", json.dumps(test_result["failures"]))
        log.error("SELF-TEST FAILURES: %s", test_result["failures"])

    import body
    from learner import Learner
    learner = Learner()
    learner_task = asyncio.create_task(learner.run())

    global _scanner
    _scanner = ScannerRunner()
    scanner_task = asyncio.create_task(_scanner.run())

    symbols = os.environ.get("SYMBOLS", "BTC/USDT:USDT").split(",")
    setup_task = asyncio.create_task(orchestrator.run(symbols))
    body_task = asyncio.create_task(body.run(symbols))

    yield

    learner.stop()
    orchestrator.stop()
    if _scanner:
        _scanner.stop()
    for t in (learner_task, setup_task, body_task, scanner_task):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

app = FastAPI(lifespan=lifespan)

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/ping")
async def ping():
    return {"ok": True, "ts": time.time()}

@app.get("/health")
async def health():
    cfg = orchestrator.cfg
    if not cfg:
        return {"ok": True, "config": None}
    s = streak(cfg, is_paper=True)
    return {"ok": True, "config": cfg.model_dump(), "win_threshold_pct": cfg.win_threshold_pct,
            "paper_win_streak": s, "required_streak": cfg.required_win_streak,
            "can_go_live": s >= cfg.required_win_streak}

@app.post("/trade/close")
async def trade_close(payload: dict):
    cfg = orchestrator.cfg or ConfigContract()
    return record_close(cfg, payload["symbol"], payload["side"],
                        float(payload["entry_price"]), float(payload["exit_price"]),
                        float(payload.get("ts_open", time.time())),
                        payload.get("balance_after"),
                        bool(payload.get("is_paper", True)))

@app.get("/learnings")
async def learnings():
    from learner import _check_gates, _current_phase
    path = "/tmp/best_params.json"
    params = json.loads(open(path).read()) if os.path.exists(path) else None
    gate_result = _check_gates()
    return {
        "ok": True,
        "phase": _current_phase(),
        "gates": gate_result["gates"],
        "all_pass": gate_result["all_pass"],
        "resolved_observations": gate_result["resolved"],
        "params": params,
    }

@app.get("/report/today")
async def report_today():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"/tmp/daily_reports/{today}.md"
    if os.path.exists(path):
        return {"ok": True, "date": today, "report": open(path).read()}
    return {"ok": False, "note": "no report yet today"}

# ============================================================
# SCANNER ENDPOINTS
# ============================================================

@app.get("/scanner")
async def scanner_state():
    if _scanner is None:
        return {"ok": False, "note": "scanner not started"}
    return {
        "ok": True,
        "paper_only": not _scanner._streak_view()["can_go_live"],
        "next_scan_in_s": max(0, SCAN_INTERVAL_S - (time.time() - _scanner.last_scan_ts)),
        "scan_count": _scanner.scan_count,
        "last_scan": _scanner._last_scan_view(),
        "scan_history": _scanner._scan_history_view(),
        "position": _scanner.position,
        "streak": _scanner._streak_view(),
        "recent_trades": _scanner._recent_trades_view(20),
        "current_best": _scanner.current_best_reading(),
        "top_5": _scanner.top_5(),
    }

@app.get("/scanner/streak")
async def scanner_streak():
    if _scanner is None:
        return {"ok": False, "note": "scanner not started"}
    return {"ok": True, **_scanner._streak_view()}

@app.get("/scanner/scans")
async def scanner_scans():
    if _scanner is None:
        return {"ok": False, "note": "scanner not started"}
    return {"ok": True, "scans": _scanner._scan_history_view()}

@app.get("/scanner/trades")
async def scanner_trades():
    if _scanner is None:
        return {"ok": False, "note": "scanner not started"}
    return {"ok": True, "trades": _scanner._recent_trades_view(100)}

@app.post("/scanner/force_scan")
async def scanner_force_scan():
    if _scanner is None:
        return {"ok": False, "note": "scanner not started"}
    _scanner.last_scan_ts = 0.0
    return {"ok": True, "note": "scan scheduled for next tick"}
