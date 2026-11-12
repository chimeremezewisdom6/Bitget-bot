from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from backtester import Params
from config import Config, has_credentials
from models import ActiveTrade, Coin, CoinImbalance, SharedState, Venue
from scanner import measure

if TYPE_CHECKING:
    from exchange_hub import ExchangeHub

log = logging.getLogger("exec")

class Gate:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.streak = 0
        self.unlocked = False
        self.paper_trades = 0
        try:
            with open(cfg.gate_path) as f:
                d = json.load(f)
            self.streak, self.unlocked, self.paper_trades = d["streak"], d["unlocked"], d["paper_trades"]
        except (FileNotFoundError, KeyError, ValueError):
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.cfg.gate_path) or ".", exist_ok=True)
        tmp = self.cfg.gate_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"streak": self.streak, "unlocked": self.unlocked, "paper_trades": self.paper_trades}, f)
        os.replace(tmp, self.cfg.gate_path)

    def record_paper(self, net: float) -> None:
        self.paper_trades += 1
        self.streak = self.streak + 1 if net >= self.cfg.gate_min_net else 0
        if self.streak >= self.cfg.gate_wins and not self.unlocked:
            self.unlocked = True
            log.warning("GATE PASSED: %d consecutive net wins >= %.2f%%", self.cfg.gate_wins, self.cfg.gate_min_net * 100)
            if not self.cfg.live_enabled:
                log.warning("Live trading stays OFF until you set LIVE_TRADING=YES and restart.")
        self._save()

    @property
    def live_allowed(self) -> bool:
        return (self.unlocked and self.cfg.live_enabled and has_credentials(self.cfg.exec_exchange))

    def status(self) -> str:
        state = "UNLOCKED" if self.unlocked else "locked"
        return f"{self.streak}/{self.cfg.gate_wins} consecutive wins >= {self.cfg.gate_min_net:.2%} net ({state})"

@dataclass
class Position:
    base: str
    symbol: str
    side: int
    entry: float
    qty: float
    opened: float
    live: bool
    stop_price: float = 0.0
    stop_order_id: Optional[str] = None

def _top(book) -> bool:
    return bool(book and book.get("bids") and book.get("asks"))

class _Broker:
    live = False
    def __init__(self, hub: "ExchangeHub", cfg: Config) -> None:
        self.hub, self.cfg = hub, cfg

    async def mark(self, pos: Position) -> Optional[float]:
        book = await self.hub.book(self.hub.exec_key, pos.symbol, "live")
        if not _top(book):
            return None
        return float(book["bids"][0][0] if pos.side == 1 else book["asks"][0][0])

class PaperBroker(_Broker):
    live = False
    async def open(self, base: str, venue: Venue, side: int) -> Optional[Position]:
        book = await self.hub.book(self.hub.exec_key, venue.symbol, "live")
        if not _top(book):
            return None
        px = float(book["asks"][0][0] if side == 1 else book["bids"][0][0])
        return Position(base, venue.symbol, side, px, self.cfg.position_usd / px, time.monotonic(), False)

    async def close(self, pos: Position) -> Optional[float]:
        return await self.mark(pos)

class LiveBroker(_Broker):
    live = True
    def __init__(self, hub: "ExchangeHub", cfg: Config) -> None:
        super().__init__(hub, cfg)
        self._lev_set: set[str] = set()

    async def open(self, base: str, venue: Venue, side: int) -> Optional[Position]:
        hub, key = self.hub, self.hub.exec_key
        ex = hub.ex[key]
        book = await hub.book(key, venue.symbol, "live")
        if not _top(book):
            return None
        px = float(book["asks"][0][0] if side == 1 else book["bids"][0][0])
        try:
            amount = float(ex.amount_to_precision(venue.symbol, self.cfg.position_usd / (px * venue.contract_size)))
            min_amt = ((ex.market(venue.symbol).get("limits") or {}).get("amount") or {}).get("min")
            if amount <= 0 or (min_amt and amount < min_amt):
                log.error("order size %s below exchange minimum %s for %s", amount, min_amt, venue.symbol)
                return None
        except Exception as e:
            log.error("cannot size order for %s: %s", venue.symbol, e)
            return None

        if venue.symbol not in self._lev_set:
            await hub.call(key, "set_leverage", self.cfg.leverage, venue.symbol, priority="live")
            self._lev_set.add(venue.symbol)

        order = await hub.call(key, "create_order", venue.symbol, "market", "buy" if side == 1 else "sell", amount, None, {}, priority="live")
        if order is None:
            log.error("entry order failed: %s", hub.last_error.get(key))
            return None
        fill = order.get("average") or order.get("price")
        if not fill and order.get("id"):
            o = await hub.call(key, "fetch_order", order["id"], venue.symbol, priority="live")
            fill = o and (o.get("average") or o.get("price"))
        fill = float(fill or px)

        stop_px = fill * (1 - side * self.cfg.stop_loss)
        try:
            stop_px = float(ex.price_to_precision(venue.symbol, stop_px))
        except Exception:
            pass
        stop = await hub.call(key, "create_order", venue.symbol, "market", "sell" if side == 1 else "buy", amount, None, {"stopLossPrice": stop_px, "reduceOnly": True}, priority="live")
        if stop is None:
            log.error("server-side stop NOT placed (%s); software stop only", hub.last_error.get(key))
        return Position(base, venue.symbol, side, fill, amount, time.monotonic(), True, stop_px, (stop or {}).get("id"))

    async def close(self, pos: Position) -> Optional[float]:
        hub, key = self.hub, self.hub.exec_key
        if pos.stop_order_id:
            await hub.call(key, "cancel_order", pos.stop_order_id, pos.symbol, priority="live")
        order = await hub.call(key, "create_order", pos.symbol, "market", "sell" if pos.side == 1 else "buy", pos.qty, None, {"reduceOnly": True}, priority="live")
        if order is None:
            positions = await hub.call(key, "fetch_positions", [pos.symbol], priority="live")
            if positions is not None and all(abs(float(p.get("contracts") or 0)) == 0 for p in positions):
                log.warning("position already flat (server-side stop likely fired)")
                return pos.stop_price or None
            return None
        fill = order.get("average") or order.get("price")
        return float(fill) if fill else await self.mark(pos)

class TradeManager:
    def __init__(self, hub: "ExchangeHub", cfg: Config, gate: Gate, state: SharedState) -> None:
        self.hub, self.cfg, self.gate, self.state = hub, cfg, gate, state
        self.paper = PaperBroker(hub, cfg)
        self.live = LiveBroker(hub, cfg)

    async def _close(self, broker: _Broker, pos: Position) -> Optional[float]:
        for _ in range(self.cfg.close_retries):
            px = await broker.close(pos)
            if px is not None:
                return px
            await asyncio.sleep(1.0)
        return None

    async def execute(self, coin: Coin, obs: CoinImbalance, params: Params) -> bool:
        cfg, hub = self.cfg, self.hub
        broker: _Broker = self.live if self.gate.live_allowed else self.paper
        mode = "LIVE" if broker.live else "PAPER"
        side = 1 if obs.side == "LONG" else -1
        venue = hub.exec_map[coin.base]

        pos = await broker.open(coin.base, venue, side)
        if pos is None:
            log.warning("[%s] could not open %s %s", mode, obs.side, coin.base)
            return False
        print("[%s] OPEN %s %s @ %.6g (dominance %.1fx, strength %.0f%%) | %s" % (mode, obs.side, coin.base, pos.entry, obs.dominance, obs.strength * 100, params), flush=True)
        act = ActiveTrade(coin.base, side, mode, pos.entry, time.time(), pos.entry, 0.0, obs.side_ratio(side), params.fade_trigger)
        self.state.active = act

        reason, last_px, px_fail, cancelled = "max_duration", pos.entry, 0, False
        deadline = pos.opened + cfg.max_trade_seconds
        obs_task: Optional[asyncio.Task] = None
        try:
            while True:
                tick = time.monotonic()
                obs_task = asyncio.create_task(measure(hub, coin, cfg, "live"))
                px = await broker.mark(pos)
                if px is None:
                    px_fail += 1
                    if px_fail >= cfg.max_price_failures:
                        reason = "blind_exit"
                        break
                else:
                    px_fail, last_px = 0, px
                    act.last_px = px
                    act.gross = side * (px / pos.entry - 1)
                    if act.gross <= -cfg.stop_loss:
                        reason = "stop_loss"
                        break
                if time.monotonic() >= deadline:
                    reason = "max_duration"
                    break
                try:
                    live_obs = await asyncio.wait_for(obs_task, timeout=cfg.monitor_interval_s * 2)
                except asyncio.TimeoutError:
                    live_obs = None
                if live_obs:
                    act.side_ratio = live_obs.side_ratio(side)
                    if act.side_ratio < params.fade_trigger:
                        reason = "fade"
                        break
                await asyncio.sleep(max(0.0, cfg.monitor_interval_s - (time.monotonic() - tick)))
        except asyncio.CancelledError:
            reason, cancelled = "shutdown", True
        finally:
            if obs_task and not obs_task.done():
                obs_task.cancel()

        exit_px = await self._close(broker, pos)
        if exit_px is None:
            if broker.live:
                log.critical("FAILED TO CLOSE LIVE POSITION %s %s -- CLOSE MANUALLY. Halting.", obs.side, coin.base)
                self.state.halted = True
                self.state.active = None
                if cancelled:
                    raise asyncio.CancelledError
                return True
            exit_px = last_px

        gross = side * (exit_px / pos.entry - 1)
        net = gross - cfg.fee_round_trip
        dur = time.monotonic() - pos.opened
        self._record(mode, coin.base, obs.side, pos.entry, exit_px, gross, net, reason, dur, params)
        self.state.active = None
        if cancelled:
            raise asyncio.CancelledError
        return True

    def _record(self, mode, base, side, entry, exit_px, gross, net, reason, dur, params) -> None:
        s = self.state
        s.trades += 1
        s.wins += 1 if net > 0 else 0
        s.session_net += net
        if mode == "PAPER":
            self.gate.record_paper(net)
        print("[%s] CLOSE %s %s %s in %.0fs | gross %+.2f%% net %+.2f%% | gate %s" % (mode, side, base, reason, dur, gross * 100, net * 100, self.gate.status()), flush=True)
        try:
            os.makedirs(os.path.dirname(self.cfg.trades_path) or ".", exist_ok=True)
            with open(self.cfg.trades_path, "a") as f:
                f.write(json.dumps({"ts": time.time(), "mode": mode, "base": base, "side": side, "entry": entry, "exit": exit_px, "gross": gross, "net": net, "reason": reason, "duration_s": round(dur, 1), "params": str(params)}) + "\n")
        except OSError as e:
            log.error("could not write trade log: %s", e)
