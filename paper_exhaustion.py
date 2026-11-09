"""paper_exhaustion.py — paper trade the gap between dying and growing side.

FOCUSED ON 4 WINDOWS: 10min, 20min, 30min, 1h.

Includes:
  - HTTP server on /health, /stats, /csv (for UptimeRobot + data pull)
  - Periodic CSV flush every 5 min (survives most restarts)
  - WebSocket watchdog (reconnects stale feeds)
  - Memory caps on trades and buffers
"""

import asyncio
import csv
import io
import json
import logging
import os
import time
import urllib.request
from collections import defaultdict, deque
from pathlib import Path
from statistics import mean

import ccxt.pro as ccxtpro
from aiohttp import web   # NEW: for HTTP server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("paper")

# ============================================================
# PARAMETERS
# ============================================================
SYMBOLS_COUNT  = int(os.environ.get("SYMBOLS_COUNT", "15"))
MIN_VOL_USD    = 1_000_000
HTTP_PORT      = int(os.environ.get("PORT", "10000"))

WINDOWS = {"10min": 600, "20min": 1200, "30min": 1800, "1h": 3600}
HORIZONS = [60, 180, 300, 600, 1800, 3600, 7200]

ACCEL_MIN        = 1.5
DECAY_MAX        = 0.7
GAP_MIN          = 2.0
END_DOM_MIN      = 1.3
MIN_END_USD_BASE = 5000.0

TP_PCT        = 2.0
SL_PCT        = 0.8
MAX_HOLD_MULT = 2
MAX_HOLD_CAP  = 4 * 3600

BUCKET_SEC          = 10
LOG_DIR             = Path("/tmp/paper_exhaustion")
LOG_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH            = LOG_DIR / "trades.csv"
SUMMARY_EVERY       = 300
CSV_FLUSH_EVERY     = 300     # NEW: dump in-memory CSV to disk every 5 min
WS_STALE_AFTER_SEC  = 180     # NEW: force reconnect if no trade in 3 min
MAX_ACTIVE_TRADES   = 100     # NEW: memory guard


def _min_end_for_window(W: int) -> float:
    return MIN_END_USD_BASE * max(1.0, (W / 600) ** 0.5)


def _cap_growth(x: float) -> float:
    if x <= 0 or x != x:
        return 0.1
    return min(x, 100.0)


# ============================================================
# UNIVERSE
# ============================================================
def get_top_symbols(n=15):
    url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
    req = urllib.request.Request(url, headers={"User-Agent": "paper/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read())
    except Exception as e:
        log.error("universe fetch failed: %s", e)
        return []
    coins = []
    for t in d.get("data", []) or []:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        try:
            vol = float(t.get("usdtVolume", 0) or 0)
        except (TypeError, ValueError):
            continue
        if vol >= MIN_VOL_USD:
            coins.append((sym, vol))
    coins.sort(key=lambda x: -x[1])
    return [s for s, _ in coins[:n]]


# ============================================================
# PAPER TRADE
# ============================================================
class PaperTrade:
    _next_id = 0

    def __init__(self, symbol, side, window, W, entry_px, entry_ts,
                 tp_px, sl_px, max_hold_sec, feats,
                 gap, grow_growth, die_growth):
        PaperTrade._next_id += 1
        self.id = PaperTrade._next_id
        self.symbol = symbol
        self.side = side
        self.window = window
        self.W = W
        self.entry_px = entry_px
        self.entry_ts = entry_ts
        self.tp_px = tp_px
        self.sl_px = sl_px
        self.max_hold_sec = max_hold_sec
        self.feats = feats
        self.gap = gap
        self.grow_growth = grow_growth
        self.die_growth = die_growth
        self.horizon_marks = {h: None for h in HORIZONS}
        self.realistic_closed = False
        self.realistic_exit_px = None
        self.realistic_exit_ts = None
        self.realistic_reason = None
        self.finalized = False

    def mark_horizons(self, price, now):
        elapsed = now - self.entry_ts
        for h in HORIZONS:
            if self.horizon_marks[h] is None and elapsed >= h:
                self.horizon_marks[h] = price

    def update_realistic(self, price, now):
        if self.realistic_closed:
            return
        if self.side == "buy":
            if price >= self.tp_px:
                self._close(price, now, "TP"); return
            if price <= self.sl_px:
                self._close(price, now, "SL"); return
        else:
            if price <= self.tp_px:
                self._close(price, now, "TP"); return
            if price >= self.sl_px:
                self._close(price, now, "SL"); return
        if now - self.entry_ts >= self.max_hold_sec:
            self._close(price, now, "TIME")

    def _close(self, price, now, reason):
        self.realistic_closed = True
        self.realistic_exit_px = price
        self.realistic_exit_ts = now
        self.realistic_reason = reason

    def all_horizons_filled(self):
        return all(v is not None for v in self.horizon_marks.values())

    def pnl_pct(self):
        return None if not self.realistic_closed else self._pnl(self.realistic_exit_px)

    def horizon_pnl_pct(self, h):
        p = self.horizon_marks.get(h)
        return None if p is None else self._pnl(p)

    def _pnl(self, px):
        if self.side == "buy":
            return (px - self.entry_px) / self.entry_px * 100.0
        return (self.entry_px - px) / self.entry_px * 100.0


# ============================================================
# PAPER BOT
# ============================================================
class PaperBot:
    def __init__(self, symbols):
        self.symbols = symbols
        self.buffers = {s: deque() for s in symbols}
        self.last_price = {s: 0.0 for s in symbols}
        self.last_seen_ts = {s: 0.0 for s in symbols}  # NEW: feed watchdog
        self.active_trades = []
        self.closed_trades = []
        self.last_detect = {}
        self.warmup_until = time.time() + 300
        self.start_ts = time.time()
        self.stats = defaultdict(lambda: {
            "signals": 0, "closed": 0, "wins": 0,
            "pnl_sum": 0.0, "horizon_pnls": defaultdict(list),
            "top_signals": [],
        })
        self.csv_buffer = io.StringIO()  # NEW: in-memory CSV
        self.csv_writer = csv.writer(self.csv_buffer)
        self.csv_header_written = False
        self.last_csv_flush = time.time()

    # --- CSV (in memory, flushed periodically) ---
    def _write_csv_row(self, t):
        if not self.csv_header_written:
            headers = [
                "id", "entry_ts", "window", "symbol", "side",
                "entry_px", "tp_px", "sl_px", "max_hold_sec",
                "gap", "grow_growth", "die_growth",
                "end_dom", "end_vol",
                "q_buy_0", "q_buy_1", "q_buy_2", "q_buy_3",
                "q_sell_0", "q_sell_1", "q_sell_2", "q_sell_3",
                "exit_ts", "exit_reason", "exit_px", "realistic_pnl",
            ]
            for h in HORIZONS:
                headers.append(f"h_{h}s_px")
                headers.append(f"h_{h}s_pnl")
            self.csv_writer.writerow(headers)
            self.csv_header_written = True
        f = t.feats
        row = [
            t.id, f"{t.entry_ts:.2f}", t.window, t.symbol, t.side,
            f"{t.entry_px:.8f}", f"{t.tp_px:.8f}", f"{t.sl_px:.8f}",
            t.max_hold_sec,
            f"{t.gap:.3f}", f"{t.grow_growth:.3f}", f"{t.die_growth:.3f}",
            f"{f['end_dom']:.3f}", f"{f['end_vol']:.2f}",
        ]
        for k in range(4):
            row.append(f"{f['q_buy'][k]:.2f}")
        for k in range(4):
            row.append(f"{f['q_sell'][k]:.2f}")
        rp = t.pnl_pct()
        row += [
            f"{t.realistic_exit_ts:.2f}" if t.realistic_exit_ts else "",
            t.realistic_reason or "",
            f"{t.realistic_exit_px:.8f}" if t.realistic_exit_px else "",
            f"{rp:.4f}" if rp is not None else "",
        ]
        for h in HORIZONS:
            px = t.horizon_marks.get(h)
            pnl = t.horizon_pnl_pct(h)
            row.append(f"{px:.8f}" if px else "")
            row.append(f"{pnl:.4f}" if pnl is not None else "")
        self.csv_writer.writerow(row)

    def flush_csv(self):
        """Write in-memory CSV to disk. Called every 5 min and on shutdown."""
        try:
            with CSV_PATH.open("w", newline="") as f:
                f.write(self.csv_buffer.getvalue())
            self.last_csv_flush = time.time()
            log.info("csv flushed (%d bytes)", len(self.csv_buffer.getvalue()))
        except Exception as e:
            log.warning("csv flush failed: %s", e)

    def get_csv_text(self) -> str:
        return self.csv_buffer.getvalue()

    # --- Buffer ---
    def add_trade(self, symbol, ts, px, qty, side):
        bucket_ts = int(ts // BUCKET_SEC) * BUCKET_SEC
        buf = self.buffers[symbol]
        usd = px * qty
        self.last_seen_ts[symbol] = time.time()
        if buf and buf[-1][0] == bucket_ts:
            t, b, s, o, _ = buf[-1]
            if side == "buy":
                b += usd
            else:
                s += usd
            buf[-1] = (t, b, s, o, px)
        elif not buf or buf[-1][0] < bucket_ts:
            if side == "buy":
                buf.append((bucket_ts, usd, 0.0, px, px))
            else:
                buf.append((bucket_ts, 0.0, usd, px, px))

    def _trim(self, symbol, now):
        cutoff = now - 3600 - 120
        buf = self.buffers[symbol]
        while buf and buf[0][0] < cutoff:
            buf.popleft()

    def _window_stats(self, symbol, T, W):
        buf = self.buffers[symbol]
        if not buf or buf[-1][0] < T - 120:
            return None
        cutoff = T - W
        buy = sell = 0.0
        first = last = None
        for ts, b, s, o, c in reversed(buf):
            if ts > T:
                continue
            if ts < cutoff:
                break
            buy += b
            sell += s
            if last is None:
                last = c
            first = o
        if first is None or last is None or first <= 0:
            return None
        return {"buy": buy, "sell": sell, "first": first, "last": last}

    def _features(self, symbol, T, W):
        qw = W // 4
        quarters = []
        for k in range(4):
            qs = self._window_stats(symbol, T - (3 - k) * qw, qw)
            if qs is None:
                return None
            quarters.append(qs)
        q0, q1, q2, q3 = quarters
        bf, bs = q0["buy"] + q1["buy"], q2["buy"] + q3["buy"]
        sf, ss = q0["sell"] + q1["sell"], q2["sell"] + q3["sell"]
        bg = _cap_growth(bs / bf if bf > 0 else (100.0 if bs > 0 else 1.0))
        sg = _cap_growth(ss / sf if sf > 0 else (100.0 if ss > 0 else 1.0))
        if q3["buy"] >= q3["sell"]:
            end_side, end_dom, end_vol = "buy", q3["buy"] / max(q3["sell"], 1), q3["buy"]
        else:
            end_side, end_dom, end_vol = "sell", q3["sell"] / max(q3["buy"], 1), q3["sell"]
        if q3["last"] <= 0:
            return None
        return {
            "buy_growth": bg, "sell_growth": sg,
            "end_side": end_side, "end_dom": end_dom, "end_vol": end_vol,
            "entry_px": q3["last"],
            "q_buy": [q["buy"] for q in quarters],
            "q_sell": [q["sell"] for q in quarters],
        }

    def _classify(self, f, W):
        bg, sg = f["buy_growth"], f["sell_growth"]
        if bg >= sg:
            grow_side, grow_growth, die_growth = "buy", bg, sg
        else:
            grow_side, grow_growth, die_growth = "sell", sg, bg
        gap = grow_growth / max(die_growth, 0.1)
        if gap < GAP_MIN or grow_growth < ACCEL_MIN or die_growth > DECAY_MAX:
            return None
        if f["end_side"] != grow_side or f["end_dom"] < END_DOM_MIN:
            return None
        if f["end_vol"] < _min_end_for_window(W):
            return None
        return grow_side, gap, grow_growth, die_growth

    def detect(self, now):
        if now < self.warmup_until:
            return
        for symbol in self.symbols:
            self._trim(symbol, now)
            for wname, W in WINDOWS.items():
                key = (symbol, wname)
                if now - self.last_detect.get(key, 0) < W // 4:
                    continue
                buf = self.buffers[symbol]
                if not buf or buf[0][0] > now - W:
                    continue
                f = self._features(symbol, now, W)
                if f is None:
                    continue
                decision = self._classify(f, W)
                if decision is None:
                    continue
                # Memory cap
                if len(self.active_trades) >= MAX_ACTIVE_TRADES:
                    log.warning("MAX_ACTIVE_TRADES hit (%d), skipping new signal",
                                MAX_ACTIVE_TRADES)
                    continue
                side, gap, grow_growth, die_growth = decision
                self.last_detect[key] = now
                self._open(symbol, side, wname, W, f, gap,
                           grow_growth, die_growth, now)

    def _open(self, symbol, side, wname, W, f, gap,
              grow_growth, die_growth, now):
        entry = f["entry_px"]
        if side == "buy":
            tp = entry * (1 + TP_PCT / 100)
            sl = entry * (1 - SL_PCT / 100)
        else:
            tp = entry * (1 - TP_PCT / 100)
            sl = entry * (1 + SL_PCT / 100)
        max_hold = min(int(W * MAX_HOLD_MULT), MAX_HOLD_CAP)
        t = PaperTrade(symbol, side, wname, W, entry, now, tp, sl,
                       max_hold, f, gap, grow_growth, die_growth)
        self.active_trades.append(t)
        s = self.stats[wname]
        s["signals"] += 1
        s["top_signals"].append((gap, t.id, symbol, side, entry, now))
        s["top_signals"].sort(key=lambda x: -x[0])
        s["top_signals"] = s["top_signals"][:20]
        log.info(
            "OPEN #%d [%s] %s %s @ %.8f | gap=%.1fx "
            "(grow %.2fx / die %.2fx) | end_dom=%.2fx | q_buy=%s q_sell=%s",
            t.id, wname, symbol, side.upper(), entry, gap,
            grow_growth, die_growth, f["end_dom"],
            [int(x) for x in f["q_buy"]],
            [int(x) for x in f["q_sell"]],
        )

    def on_trade(self, symbol, px, now):
        self.last_price[symbol] = px
        for t in list(self.active_trades):
            if t.symbol != symbol or t.finalized:
                continue
            t.mark_horizons(px, now)
            if not t.realistic_closed:
                t.update_realistic(px, now)
                if t.realistic_closed:
                    log.info(
                        "CLOSE #%d [%s] %s %s | %s | %.8f -> %.8f | pnl=%+.3f%%",
                        t.id, t.window, t.symbol, t.side.upper(),
                        t.realistic_reason, t.entry_px,
                        t.realistic_exit_px, t.pnl_pct(),
                    )
            if t.all_horizons_filled():
                self._finalize(t)

    def _finalize(self, t):
        t.finalized = True
        if t in self.active_trades:
            self.active_trades.remove(t)
        self.closed_trades.append(t)
        last = self.last_price.get(t.symbol, 0) or t.entry_px
        for h in HORIZONS:
            if t.horizon_marks[h] is None:
                t.horizon_marks[h] = last
        s = self.stats[t.window]
        pnl = t.pnl_pct()
        if pnl is not None:
            s["closed"] += 1
            if pnl > 0:
                s["wins"] += 1
            s["pnl_sum"] += pnl
        for h in HORIZONS:
            hp = t.horizon_pnl_pct(h)
            if hp is not None:
                s["horizon_pnls"][h].append(hp)
        self._write_csv_row(t)

    def force_finalize_timeouts(self, now):
        for t in list(self.active_trades):
            if t.finalized:
                continue
            if now - t.entry_ts > max(HORIZONS) + 300:
                self._finalize(t)

    def get_stats_json(self):
        runtime_h = (time.time() - self.start_ts) / 3600
        out = {
            "runtime_hours": round(runtime_h, 2),
            "signals": sum(s["signals"] for s in self.stats.values()),
            "closed": len(self.closed_trades),
            "active": len(self.active_trades),
            "warmup_done": time.time() >= self.warmup_until,
            "windows": {},
            "feeds": {},
        }
        for wname in WINDOWS:
            s = self.stats.get(wname)
            if not s:
                continue
            w = {"signals": s["signals"], "closed": s["closed"]}
            if s["closed"] > 0:
                w["win_rate"] = round(s["wins"] / s["closed"], 3)
                w["avg_pnl_pct"] = round(s["pnl_sum"] / s["closed"], 3)
            out["windows"][wname] = w
        now = time.time()
        for sym in self.symbols:
            last = self.last_seen_ts.get(sym, 0)
            out["feeds"][sym] = {
                "last_seen_sec_ago": int(now - last) if last else None,
                "stale": (now - last) > WS_STALE_AFTER_SEC if last else True,
            }
        return out


# ============================================================
# HTTP SERVER (for UptimeRobot + data pull)
# ============================================================
async def start_http(bot):
    async def health(req):
        return web.json_response({"ok": True, "ts": time.time()})

    async def stats(req):
        return web.json_response(bot.get_stats_json())

    async def csv_endpoint(req):
        text = bot.get_csv_text()
        return web.Response(
            text=text if text else "id,entry_ts,window,symbol,side\n",
            content_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=trades.csv"},
        )

    async def root(req):
        return web.Response(text=(
            "paper_exhaustion running.\n"
            "/health  - uptime ping\n"
            "/stats   - JSON stats\n"
            "/csv     - download CSV\n"
        ))

    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    app.router.add_get("/stats", stats)
    app.router.add_get("/csv", csv_endpoint)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    log.info("HTTP server on :%d (/health /stats /csv)", HTTP_PORT)
    return runner


# ============================================================
# LOOPS
# ============================================================
async def feed_symbol(ws, bot, symbol):
    consecutive_errors = 0
    while True:
        try:
            trades = await ws.watch_trades(symbol)
            consecutive_errors = 0
            now = time.time()
            for t in trades:
                ts = t["timestamp"] / 1000.0
                px = float(t["price"])
                qty = float(t["amount"])
                bot.add_trade(symbol, ts, px, qty, t["side"])
                bot.on_trade(symbol, px, now)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            consecutive_errors += 1
            log.warning("ws %s: %s (err #%d)", symbol,
                        type(e).__name__, consecutive_errors)
            await asyncio.sleep(min(30, 3 * consecutive_errors))


async def ws_watchdog(bot):
    """NEW: if a symbol has not seen a trade in WS_STALE_AFTER_SEC,
    log it. The feed loop auto-reconnects on its own; this just tells us."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        stale = []
        for sym in bot.symbols:
            last = bot.last_seen_ts.get(sym, 0)
            if last and now - last > WS_STALE_AFTER_SEC:
                stale.append(f"{sym}({int(now - last)}s)")
        if stale:
            log.warning("stale feeds: %s", ", ".join(stale))


async def detection_loop(bot):
    while True:
        await asyncio.sleep(30)
        try:
            now = time.time()
            bot.detect(now)
            bot.force_finalize_timeouts(now)
        except Exception as e:
            log.error("detect error: %s", e)


async def summary_loop(bot):
    while True:
        await asyncio.sleep(SUMMARY_EVERY)
        try:
            runtime_h = (time.time() - bot.start_ts) / 3600
            total_sig = sum(s["signals"] for s in bot.stats.values())
            total_cls = len(bot.closed_trades)
            log.info("SUMMARY runtime=%.1fh signals=%d closed=%d active=%d",
                     runtime_h, total_sig, total_cls, len(bot.active_trades))
            for wname in WINDOWS:
                s = bot.stats.get(wname)
                if not s or s["closed"] == 0:
                    continue
                n = s["closed"]
                log.info("  [%s] n=%d WR=%.1f%% avg=%+.3f%%",
                         wname, n, s["wins"] / n * 100, s["pnl_sum"] / n)
        except Exception as e:
            log.error("summary error: %s", e)


async def csv_flush_loop(bot):
    """NEW: flush in-memory CSV to disk every 5 min."""
    while True:
        await asyncio.sleep(CSV_FLUSH_EVERY)
        try:
            bot.flush_csv()
        except Exception as e:
            log.error("flush error: %s", e)


# ============================================================
# MAIN
# ============================================================
async def main():
    log.info("=" * 80)
    log.info("PAPER EXHAUSTION — growing vs dying side, biggest gap")
    log.info("  windows=%s", list(WINDOWS.keys()))
    log.info("  gap>=%.1fx accel>=%.1fx decay<=%.1fx end_dom>=%.1fx",
             GAP_MIN, ACCEL_MIN, DECAY_MAX, END_DOM_MIN)
    log.info("  TP=%.1f%% SL=%.1f%% hold=%dx window (cap %ds)",
             TP_PCT, SL_PCT, MAX_HOLD_MULT, MAX_HOLD_CAP)
    log.info("=" * 80)

    symbols = get_top_symbols(SYMBOLS_COUNT)
    if not symbols:
        log.error("no symbols")
        return
    log.info("symbols (%d): %s", len(symbols), symbols)

    bot = PaperBot(symbols)
    ws = ccxtpro.bitget({"enableRateLimit": True})

    runner = await start_http(bot)   # NEW: HTTP server for Render
    log.info("warmup: 5 min (no signals until buffers fill)")

    feeds = [asyncio.create_task(feed_symbol(ws, bot, s)) for s in symbols]
    tasks = [
        asyncio.create_task(detection_loop(bot)),
        asyncio.create_task(summary_loop(bot)),
        asyncio.create_task(csv_flush_loop(bot)),    # NEW
        asyncio.create_task(ws_watchdog(bot)),        # NEW
    ]

    try:
        await asyncio.gather(*feeds, *tasks)
    except asyncio.CancelledError:
        pass
    finally:
        for t in feeds + tasks:
            t.cancel()
        try:
            await asyncio.wait_for(ws.close(), timeout=2.0)
        except Exception:
            pass
        bot.finalize_all()
        bot.flush_csv()
        try:
            await runner.cleanup()
        except Exception:
            pass
        log.info("csv flushed to %s", CSV_PATH)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("interrupted")
