"""Orchestrator: scan worker + trade loop + reporter run as independent asyncio tasks, so the slow
500-800 coin scan never blocks the 1-second trade monitor.

A tiny aiohttp web server is bound to 0.0.0.0:$PORT FIRST (before any exchange / ccxt work) so hosts such as
Render's free Web Service see an open port instantly. The bot runs under a supervisor that restarts it on
failure without ever taking the web server down.

Run:  python main.py            (paper mode by default)
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from datetime import datetime
from typing import TYPE_CHECKING

from aiohttp import web

from backtester import optimize
from coinglass import CoinGlassClient
from config import Config
from executor import Gate, TradeManager
from models import ScanResult, SharedState
from scanner import build_universe, measure, prefilter, stage1, stage2

if TYPE_CHECKING:
    from exchange_hub import ExchangeHub

log = logging.getLogger("main")


# ====================================================================== bot workers (unchanged logic)
async def scan_worker(hub: "ExchangeHub", cfg: Config, state: SharedState, cg) -> None:
    seq = 0
    while True:
        try:
            t0 = time.time()
            coins = await build_universe(hub, cfg)
            universe = len(coins)
            if cg:
                coins = prefilter(coins, await cg.aggregated_depth(), cfg)
            top, measured = await stage1(hub, cfg, coins)
            selected, scores = await stage2(hub, cfg, top) if top else (None, {})
            if selected is None:
                log.warning("scan produced no candidate (measured %d/%d)", measured, len(coins))
            else:
                seq += 1
                coin = next(c for c in coins if c.base == selected.base)
                state.publish(ScanResult(seq, time.time(), universe, measured, top, scores, selected, coin))
                table = ", ".join(f"{t.base} {t.strength:.0%}{'L' if t.side == 'LONG' else 'S'}" for t in top)
                log.info("SCAN #%d (%.0fs): %d/%d measured | top: %s | picked %s (fluct %.2f%%)", seq,
                         time.time() - t0, measured, universe, table, selected.base,
                         scores[selected.base] * 100)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("scan cycle failed")
        await asyncio.sleep(cfg.scan_interval_s)


async def trade_loop(hub: "ExchangeHub", cfg: Config, state: SharedState, mgr: TradeManager) -> None:
    last_seq = 0
    while not state.halted:
        try:
            scan = await state.next_scan(last_seq, cfg.scan_max_age_s)
            if scan is None:
                return
            last_seq = scan.seq
            coin = scan.coin
            venue = hub.exec_map[coin.base]

            # ---- Stage 3: 100-sequence optimisation on the selected coin
            candles = await hub.ohlcv(hub.exec_key, venue.symbol, "1m", cfg.history_candles, "live")
            if not candles or len(candles) < cfg.min_history:
                log.warning("%s: not enough history for backtest", coin.base)
                continue
            winner, ranked = await asyncio.to_thread(optimize, candles, cfg)
            log.info("BACKTEST %s on %d candles. Top 3: %s", coin.base, len(candles),
                     " || ".join(str(r) for r in ranked[:3]))
            if winner is None:
                log.info("%s: no sequence qualified (min %d trades%s) -> skipping", coin.base,
                         cfg.min_backtest_trades, ", net>0" if cfg.require_positive_backtest else "")
                continue
            state.winning = winner
            log.info("WINNING SEQUENCE: %s", winner)

            # ---- Stage 4: entry check on the fresh live book, using the winning parameters
            obs = await measure(hub, coin, cfg, "live")
            if obs is None:
                log.info("%s: live book unavailable -> skipping", coin.base)
                continue
            p = winner.params
            if obs.dominance < p.ratio_trigger or obs.strength < p.strength_trigger:
                log.info("%s: live imbalance %.1fx / %.0f%% below winning triggers -> no entry", coin.base,
                         obs.dominance, obs.strength * 100)
                continue
            await mgr.execute(coin, obs, p)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("trade loop error")
            await asyncio.sleep(5)


def render_summary(hub: "ExchangeHub", cfg: Config, state: SharedState, gate: Gate) -> str:
    mode = "LIVE" if gate.live_allowed else "PAPER"
    lines = [f"===== SUMMARY {datetime.now():%Y-%m-%d %H:%M:%S} =====",
             f"Mode: {mode} | Gate: {gate.status()}"]
    a = state.active
    if a:
        lines.append(f"Active trade: {'LONG' if a.side == 1 else 'SHORT'} {a.base} [{a.mode}] entry {a.entry:.6g} "
                     f"now {a.last_px:.6g} | gross {a.gross:+.2%} | side-ratio {a.side_ratio:.2f}x "
                     f"(fade < {a.fade_trigger:g}x) | {time.time() - a.opened:.0f}s open")
    else:
        lines.append("Active trade: none")
    lines.append(f"Winning sequence: {state.winning if state.winning else 'none yet'}")
    wr = state.wins / state.trades if state.trades else 0.0
    lines.append(f"Session PnL: {state.trades} trades, {wr:.0%} win rate, net {state.session_net:+.2%} "
                 f"(sum of per-trade returns, after {cfg.fee_round_trip:.2%} fees)")
    s = state.latest
    lines.append(f"Last scan: #{s.seq} {time.time() - s.ts:.0f}s ago, picked {s.selected.base}" if s
                 else "Last scan: none yet")
    lines.append(f"Venues: {hub.status()}")
    return "\n".join(lines)


async def reporter(hub, cfg, state, gate) -> None:
    while True:
        await asyncio.sleep(cfg.summary_interval_s)
        print("\n" + render_summary(hub, cfg, state, gate) + "\n", flush=True)


# ====================================================================== web server (binds first)
async def start_web(ctx: dict) -> web.AppRunner:
    """Bind 0.0.0.0:$PORT immediately. Runs as part of the event loop; independent of the bot."""

    async def root(_request):
        return web.Response(text="OFI bot is running\n")

    async def health(_request):
        return web.json_response({"ok": True, "uptime_s": int(time.time() - ctx["started"]),
                                  "bot": ctx["phase"]})

    async def status(_request):
        try:
            hub, gate = ctx.get("hub"), ctx.get("gate")
            if hub is None or gate is None:
                return web.Response(text=f"bot phase: {ctx['phase']}\n")
            return web.Response(text=f"bot phase: {ctx['phase']}\n"
                                     + render_summary(hub, ctx["cfg"], ctx["state"], gate) + "\n")
        except Exception as e:  # noqa: BLE001
            return web.Response(status=500, text=f"status error: {e!r}\n")

    app = web.Application()
    app.add_routes([web.get("/", root), web.get("/health", health), web.get("/status", status)])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("web server listening on 0.0.0.0:%d", port)
    return runner


# ====================================================================== bot session + supervisor
async def run_bot(ctx: dict) -> None:
    """One bot session. Raises when anything fatal happens so the supervisor can restart it."""
    from exchange_hub import ExchangeHub  # lazy: ccxt import must not delay the port bind

    cfg, state = ctx["cfg"], ctx["state"]
    hub = ExchangeHub(cfg)
    tasks: list[asyncio.Task] = []
    try:
        ctx["phase"] = "connecting to exchanges"
        await hub.start()
        gate = Gate(cfg)
        mgr = TradeManager(hub, cfg, gate, state)
        cg = CoinGlassClient.from_env()
        ctx["hub"], ctx["gate"], ctx["started_ok"], ctx["phase"] = hub, gate, True, "running"
        log.info("bot running in %s mode | %s | CoinGlass prefilter: %s",
                 "LIVE" if gate.live_allowed else "PAPER", gate.status(), "on" if cg else "off")

        tasks = [asyncio.create_task(scan_worker(hub, cfg, state, cg), name="scan"),
                 asyncio.create_task(trade_loop(hub, cfg, state, mgr), name="trade"),
                 asyncio.create_task(reporter(hub, cfg, state, gate), name="report")]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            if not t.cancelled() and t.exception():
                log.error("task %s died: %r", t.get_name(), t.exception())
        raise RuntimeError("a worker task exited")
    finally:
        for t in tasks:
            t.cancel()
        if tasks:  # the trade task closes any open position when cancelled
            await asyncio.gather(*tasks, return_exceptions=True)
        ctx["hub"], ctx["gate"] = None, None
        await hub.close()


async def supervisor(ctx: dict) -> None:
    delay = 5
    while True:
        try:
            await run_bot(ctx)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("bot session ended: %s", e)
            ctx["phase"] = f"retrying after error: {type(e).__name__}"
        if ctx["state"].halted:
            ctx["phase"] = "HALTED - live position could not be closed; check the exchange manually"
            log.critical(ctx["phase"])
            await asyncio.Event().wait()          # keep the web server up, never restart trading
        if ctx.pop("started_ok", False):
            delay = 5
        log.info("restarting bot in %ds", delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 120)


# ====================================================================== entry point
async def amain() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    ctx: dict = {"started": time.time(), "phase": "starting", "cfg": Config.from_env(),
                 "state": SharedState(), "hub": None, "gate": None}

    runner = await start_web(ctx)                 # FIRST: open the port before any heavy work

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass

    sup = asyncio.create_task(supervisor(ctx), name="supervisor")
    stop_task = asyncio.create_task(stop.wait())
    await asyncio.wait([sup, stop_task], return_when=asyncio.FIRST_COMPLETED)

    log.info("shutting down (open position, if any, will be closed)...")
    sup.cancel()
    await asyncio.gather(sup, return_exceptions=True)
    await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
