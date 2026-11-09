"""paper_exhaustion.py — paper trade the "dying side vs growing side" gap.

FOCUSED ON 4 WINDOWS: 10min, 20min, 30min, 1h.

THE LOGIC
    For each window W and each symbol:
      1. Split the last W seconds into 4 equal quarters
      2. Measure buy USD and sell USD in each quarter
      3. Compute buy_growth  = (Q3+Q4 buy)  / (Q1+Q2 buy)
         Compute sell_growth = (Q3+Q4 sell) / (Q1+Q2 sell)
      4. Growing side  = side with the larger growth
         Dying side    = side with the smaller growth
         GAP           = growing_growth / dying_growth
      5. FIRE only when ALL of these are true:
           - GAP           >= GAP_MIN        (the two sides are diverging)
           - growing_growth >= ACCEL_MIN     (growing side is actually accelerating)
           - dying_growth  <= DECAY_MAX      (dying side is actually fading)
           - Q4 is dominated by the growing side (>= END_DOM_MIN)
           - Q4 growing volume >= MIN_END_USD (scaled to window)
      6. Enter PAPER trade on the growing side.

    Each trade tracks 7 horizons (1m,3m,5m,10m,30m,1h,2h) AND a realistic exit
    (TP 2%, SL 0.8%, timeout 2× window). All results go to CSV.

HOW TO RUN
    python paper_exhaustion.py
    Ctrl+C stops it. Full summary at exit.

OUTPUT
    Console:           live per-signal opens/closes
    Console (5-min):   per-window summary + top 10 gaps seen
    /tmp/paper_exhaustion/trades.csv:   every signal + outcome
"""

import asyncio
import csv
import json
import logging
import os
import time
import urllib.request
from collections import defaultdict, deque
from pathlib import Path
from statistics import mean

import ccxt.pro as ccxtpro

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("paper")

# ============================================================
# PARAMETERS — tune here
# ============================================================
SYMBOLS_COUNT = int(os.environ.get("SYMBOLS_COUNT", "15"))
MIN_VOL_USD   = 1_000_000

WINDOWS = {
    "10min": 600,
    "20min": 1200,
    "30min": 1800,
    "1h":    3600,
}

HORIZONS = [60, 180, 300, 600, 1800, 3600, 7200]

# Growth / gap thresholds
ACCEL_MIN        = 1.5    # growing side must be growing >= 1.5x
DECAY_MAX        = 0.7    # dying side must be <= 0.7x
GAP_MIN          = 2.0    # grow_growth / die_growth >= 2.0
END_DOM_MIN      = 1.3    # Q4 dominance of growing side
MIN_END_USD_BASE = 5000.0 # scaled by sqrt(W/600)

# Trade management
TP_PCT        = 2.0
SL_PCT        = 0.8
MAX_HOLD_MULT = 2
MAX_HOLD_CAP  = 4 * 3600

# Infra
BUCKET_SEC    = 10
LOG_DIR       = Path("/tmp/paper_exhaustion")
LOG_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH      = LOG_DIR / "trades.csv"
SUMMARY_EVERY = 300


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
        if not self.realistic_closed:
            return None
        return self._pnl(self.realistic_exit_px)

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
        self._init_csv()

    def _init_csv(self):
        if not CSV_PATH.exists():
            with CSV_PATH.open("w", newline="") as f:
                w = csv.writer(f)
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
                w.writerow(headers)

    def _write_csv(self, t):
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
        with CSV_PATH.open("a", newline="") as fh:
            csv.writer(fh).writerow(row)

    # ---------------- Buffer ----------------
    def add_trade(self, symbol, ts, px, qty, side):
        bucket_ts = int(ts // BUCKET_SEC) * BUCKET_SEC
        buf = self.buffers[symbol]
        usd = px * qty
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
        bg = bs / bf if bf > 0 else (100.0 if bs > 0 else 1.0)
        sg = ss / sf if sf > 0 else (100.0 if ss > 0 else 1.0)
        bg = _cap_growth(bg)
        sg = _cap_growth(sg)
        if q3["buy"] >= q3["sell"]:
            end_side = "buy"
            end_dom = q3["buy"] / max(q3["sell"], 1)
            end_vol = q3["buy"]
        else:
            end_side = "sell"
            end_dom = q3["sell"] / max(q3["buy"], 1)
            end_vol = q3["sell"]
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
            grow_side, die_side = "buy", "sell"
            grow_growth, die_growth = bg, sg
        else:
            grow_side, die_side = "sell", "buy"
            grow_growth, die_growth = sg, bg

        gap = grow_growth / max(die_growth, 0.1)

        if gap < GAP_MIN:
            return None
        if grow_growth < ACCEL_MIN:
            return None
        if die_growth > DECAY_MAX:
            return None
        if f["end_side"] != grow_side:
            return None
        if f["end_dom"] < END_DOM_MIN:
            return None
        if f["end_vol"] < _min_end_for_window(W):
            return None

        return grow_side, gap, grow_growth, die_growth

    # ---------------- Detection ----------------
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
            "(grow %.2fx / die %.2fx) | end_dom=%.2fx | "
            "q_buy=%s q_sell=%s",
            t.id, wname, symbol, side.upper(), entry, gap,
            grow_growth, die_growth, f["end_dom"],
            [int(x) for x in f["q_buy"]],
            [int(x) for x in f["q_sell"]],
        )

    # ---------------- Updates ----------------
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
                        "CLOSE #%d [%s] %s %s | %s | %.8f -> %.8f | "
                        "pnl=%+.3f%%",
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
        self._write_csv(t)

    def force_finalize_timeouts(self, now):
        for t in list(self.active_trades):
            if t.finalized:
                continue
            if now - t.entry_ts > max(HORIZONS) + 300:
                self._finalize(t)

    # ---------------- Summary ----------------
    def print_summary(self):
        runtime_h = (time.time() - self.start_ts) / 3600
        total_sig = sum(s["signals"] for s in self.stats.values())
        total_cls = sum(s["closed"] for s in self.stats.values())
        log.info("")
        log.info("=" * 88)
        log.info("SUMMARY | runtime=%.1fh | signals=%d | closed=%d | active=%d",
                 runtime_h, total_sig, total_cls, len(self.active_trades))
        log.info("-" * 88)
        for wname in WINDOWS:
            s = self.stats.get(wname)
            if not s:
                continue
            if s["signals"] == 0:
                continue
            if s["closed"] == 0:
                log.info("[%s] signals=%d, no closes yet",
                         wname, s["signals"])
                continue
            n = s["closed"]
            wr = s["wins"] / n
            avg = s["pnl_sum"] / n
            log.info("[%s] n=%d WR=%.1f%% avg_pnl=%+.3f%% signals=%d",
                     wname, n, wr * 100, avg, s["signals"])
            rows = []
            for h in HORIZONS:
                hp = s["horizon_pnls"].get(h, [])
                if len(hp) < 3:
                    continue
                rows.append((h, len(hp),
                             sum(1 for x in hp if x > 0) / len(hp),
                             mean(hp)))
            if rows:
                rows.sort(key=lambda x: -x[3])
                for h, hn, hwr, havg in rows[:2]:
                    log.info(
                        "    best horizon: %ds n=%d WR=%.0f%% avg=%+.3f%%",
                        h, hn, hwr * 100, havg,
                    )
        log.info("-" * 88)
        log.info("TOP 10 GAPS SEEN (across all windows)")
        log.info("-" * 88)
        all_top = []
        for wname in WINDOWS:
            for entry in self.stats[wname]["top_signals"]:
                gap, tid, sym, side, px, ts = entry
                all_top.append((gap, tid, sym, side, wname, ts))
        all_top.sort(key=lambda x: -x[0])
        for gap, tid, sym, side, wname, ts in all_top[:10]:
            when = time.strftime("%H:%M", time.localtime(ts))
            log.info("  gap=%.1fx #%d [%s] %s %s @ %s",
                     gap, tid, wname, sym, side.upper(), when)
        log.info("=" * 88)
        log.info("")

    def finalize_all(self):
        for t in list(self.active_trades):
            if not t.finalized:
                self._finalize(t)


# ============================================================
# LOOPS
# ============================================================
async def feed_symbol(ws, bot, symbol):
    while True:
        try:
            trades = await ws.watch_trades(symbol)
            now = time.time()
            for t in trades:
                ts = t["timestamp"] / 1000.0
                px = float(t["price"])
                qty = float(t["amount"])
                side = t["side"]
                bot.add_trade(symbol, ts, px, qty, side)
                bot.on_trade(symbol, px, now)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("ws %s: %s", symbol, type(e).__name__)
            await asyncio.sleep(3)


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
            bot.print_summary()
        except Exception as e:
            log.error("summary error: %s", e)


# ============================================================
# MAIN
# ============================================================
async def main():
    log.info("=" * 88)
    log.info("PAPER EXHAUSTION — growing vs dying side, biggest gap")
    log.info("  windows=%s", list(WINDOWS.keys()))
    log.info("  thresholds: accel>=%.2fx decay<=%.2fx gap>=%.2fx "
             "end_dom>=%.2fx", ACCEL_MIN, DECAY_MAX, GAP_MIN, END_DOM_MIN)
    log.info("  min_end_usd: " + " ".join(
        f"{w}=${_min_end_for_window(W):.0f}"
        for w, W in WINDOWS.items()))
    log.info("  trade: TP=%.1f%% SL=%.1f%% hold=%dx window (cap %ds)",
             TP_PCT, SL_PCT, MAX_HOLD_MULT, MAX_HOLD_CAP)
    log.info("  horizons: %s", HORIZONS)
    log.info("=" * 88)

    log.info("fetching universe (>= $%.0f 24h vol)...", MIN_VOL_USD)
    symbols = get_top_symbols(SYMBOLS_COUNT)
    if not symbols:
        log.error("no symbols — check network")
        return
    log.info("symbols (%d): %s", len(symbols), symbols)

    bot = PaperBot(symbols)
    ws = ccxtpro.bitget({"enableRateLimit": True})

    log.info("starting... (first 5 min = warmup, no signals)")
    feeds = [asyncio.create_task(feed_symbol(ws, bot, s)) for s in symbols]
    tasks = [
        asyncio.create_task(detection_loop(bot)),
        asyncio.create_task(summary_loop(bot)),
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
        bot.print_summary()
        log.info("CSV: %s", CSV_PATH)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("interrupted")
