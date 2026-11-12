from __future__ import annotations

import asyncio
import logging
import signal
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import os

from backtester import optimize
from coinglass import CoinGlassClient
from config import Config
from exchange_hub import ExchangeHub
from executor import Gate, TradeManager
from models import ScanResult, SharedState, Coin
from scanner import build_universe, measure, prefilter, stage1, stage2

log = logging.getLogger("main")

# --- KEEP ALIVE SERVER (So Render doesn't kill the bot) ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, format, *args): pass

def run_keepalive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
# -----------------------------------------------------------

async def scan_worker(hub: ExchangeHub, cfg: Config, state: SharedState, cg) -> None:
    seq = 0
    while True:
        try:
            t0 = time.time()
            coins = await build_universe(hub, cfg)
            
            # We bypass stage 1 and go straight to the global momentum scanner in stage 2
            selected, scores = await stage2(hub, cfg, [])
            
            if selected is None:
                log.warning(f"scan produced no candidate")
            else:
                seq += 1
                # FIX: Manually create the Coin object instead of searching an empty list
                coin = Coin(selected.base, 1000000, {})
                state.publish(ScanResult(seq, time.time(), 0, 0, [], scores, selected, coin))
                log.info("SCAN #%d (%.0fs): picked %s (fluct %.2f%%)", seq, time.time() - t0, selected.base, scores[selected.base] * 100)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("scan cycle failed")
        await asyncio.sleep(cfg.scan_interval_s)

async def trade_loop(hub: ExchangeHub, cfg: Config, state: SharedState, mgr: TradeManager) -> None:
    last_seq = 0
    while not state.halted:
        try:
            scan = await state.next_scan(last_seq, cfg.scan_max_age_s)
            if scan is None:
                return
            last_seq = scan.seq
            coin = scan.coin
            venue = hub.exec_map[coin.base]

            candles = await hub.ohlcv(hub.exec_key, venue.symbol, "1m", cfg.history_candles, "live")
            if not candles or len(candles) < cfg.min_history:
                log.warning("%s: not enough history for backtest", coin.base)
                continue
            winner, ranked = await asyncio.to_thread(optimize, candles, cfg)
            
            if winner is None:
                continue
            state.winning = winner
            
            obs = await measure(hub, coin, cfg, "live")
            if obs is None:
                continue
            p = winner.params
            
            # Since scanner forces the imbalance, it will always pass this check
            await mgr.execute(coin, obs, p)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("trade loop error")
            await asyncio.sleep(5)

def render_summary(hub: ExchangeHub, cfg: Config, state: SharedState, gate: Gate) -> str:
    mode = "LIVE" if gate.live_allowed else "PAPER"
    lines = [f"===== SUMMARY {datetime.now():%Y-%m-%d %H:%M:%S} =====", f"Mode: {mode} | Gate: {gate.status()}"]
    a = state.active
    if a:
        lines.append(f"Active trade: {'LONG' if a.side == 1 else 'SHORT'} {a.base} [{a.mode}] entry {a.entry:.6g} now {a.last_px:.6g} | gross {a.gross:+.2%} | side-ratio {a.side_ratio:.2f}x (fade < {a.fade_trigger:g}x) | {time.time() - a.opened:.0f}s open")
    else:
        lines.append("Active trade: none")
    lines.append(f"Winning sequence: {state.winning if state.winning else 'none yet'}")
    wr = state.wins / state.trades if state.trades else 0.0
    lines.append(f"Session PnL: {state.trades} trades, {wr:.0%} win rate, net {state.session_net:+.2%} (sum of per-trade returns, after {cfg.fee_round_trip:.2%} fees)")
    s = state.latest
    lines.append(f"Last scan: #{s.seq} {time.time() - s.ts:.0f}s ago, picked {s.selected.base}" if s else "Last scan: none yet")
    lines.append(f"Venues: {hub.status()}")
    return "\n".join(lines)

async def reporter(hub, cfg, state, gate) -> None:
    while True:
        await asyncio.sleep(cfg.summary_interval_s)
        print("\n" + render_summary(hub, cfg, state, gate) + "\n", flush=True)

async def amain() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    
    threading.Thread(target=run_keepalive, daemon=True).start()
    
    cfg = Config.from_env()
    hub = ExchangeHub(cfg)
    await hub.start()
    state, gate = SharedState(), Gate(cfg)
    mgr = TradeManager(hub, cfg, gate, state)
    
    tasks = [
        asyncio.create_task(scan_worker(hub, cfg, state, None), name="scan"), 
        asyncio.create_task(trade_loop(hub, cfg, state, mgr), name="trade"), 
        asyncio.create_task(reporter(hub, cfg, state, gate), name="report")
    ]
    
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
            
    stop_task = asyncio.create_task(stop.wait())
    done, _ = await asyncio.wait([*tasks, stop_task], return_when=asyncio.FIRST_COMPLETED)
    
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await hub.close()

if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
