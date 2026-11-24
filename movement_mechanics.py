"""Bitget live microstructure sampler and event study.

Runs inside the existing unified read-only scanner. Public market endpoints only:
recent public fills, order book, candles, open interest and platform liquidations.
No order, position, balance, or account mutation endpoints are called.

Historical order-book snapshots and public fills are not backfilled by these APIs;
this collector builds a timestamped forward dataset for real event attribution.
"""
import asyncio
import json
import math
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

BASE = "https://api.bitget.com"
CATEGORY = "USDT-FUTURES"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "daily_research"
SNAPSHOTS = OUT / "movement_mechanics_snapshots.jsonl"
LATEST = OUT / "movement_mechanics_latest.json"
REPORT = OUT / "movement_mechanics_report.md"
MAX_SYMBOLS = 50
KEEP_DAYS = 3
BANDS = (0.001, 0.0025, 0.005, 0.01)


def num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


class Gate:
    def __init__(self, delay=0.065):
        self.delay = delay
        self.lock = asyncio.Lock()
        self.last = 0.0

    async def wait(self):
        async with self.lock:
            delay = self.delay - (time.monotonic() - self.last)
            if delay > 0:
                await asyncio.sleep(delay)
            self.last = time.monotonic()


async def get_json(session, path, params, gates):
    await gates[path].wait()
    async with session.get(BASE + path, params=params) as response:
        if response.status == 429 or response.status >= 500:
            raise RuntimeError("temporary HTTP " + str(response.status))
        response.raise_for_status()
        payload = await response.json()
        if payload.get("code") != "00000":
            raise RuntimeError(str(payload.get("code")) + " " + str(payload.get("msg")))
        return payload.get("data")


def list_data(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "data", "resultList"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def book_metrics(data):
    if not isinstance(data, dict):
        return {}
    asks = [(num(x[0]), num(x[1])) for x in data.get("a", []) if len(x) >= 2]
    bids = [(num(x[0]), num(x[1])) for x in data.get("b", []) if len(x) >= 2]
    asks = [(p, q) for p, q in asks if p and q and p > 0 and q > 0]
    bids = [(p, q) for p, q in bids if p and q and p > 0 and q > 0]
    if not asks or not bids:
        return {"status": "BOOK_INCOMPLETE"}
    best_ask = min(p for p, _ in asks)
    best_bid = max(p for p, _ in bids)
    mid = (best_ask + best_bid) / 2
    result = {
        "status": "OK", "mid": mid, "best_bid": best_bid, "best_ask": best_ask,
        "spread_bps": (best_ask - best_bid) / mid * 10000 if mid else None,
    }
    for band in BANDS:
        key = str(round(band * 100, 2)).replace(".", "p")
        bid_depth = sum(p * q for p, q in bids if p >= mid * (1 - band))
        ask_depth = sum(p * q for p, q in asks if p <= mid * (1 + band))
        total = bid_depth + ask_depth
        result["bid_depth_usdt_" + key] = bid_depth
        result["ask_depth_usdt_" + key] = ask_depth
        result["book_imbalance_" + key] = (bid_depth - ask_depth) / total if total else None
    return result


def fill_metrics(rows, now_ms):
    buys = sells = 0.0
    valid = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        price, size = num(row.get("price")), num(row.get("size"))
        ts = int(num(row.get("ts"), 0) or 0)
        side = str(row.get("side", "")).lower()
        if price and size and ts and side in ("buy", "sell"):
            value = price * size
            if side == "buy":
                buys += value
            else:
                sells += value
            valid.append(ts)
    total = buys + sells
    return {
        "status": "OK" if valid else "NO_RECENT_PUBLIC_FILLS",
        "buy_notional_usdt": buys, "sell_notional_usdt": sells,
        "buy_sell_imbalance": (buys - sells) / total if total else None,
        "fill_count": len(valid),
        "oldest_fill_age_seconds": (now_ms - min(valid)) / 1000 if valid else None,
        "newest_fill_age_seconds": (now_ms - max(valid)) / 1000 if valid else None,
        "sample_span_seconds": (max(valid) - min(valid)) / 1000 if len(valid) > 1 else 0,
        "side_semantics": "Bitget-reported public fill side; aggressor interpretation is a proxy, not independently verified",
    }


def candle_metrics(rows, now_ms):
    parsed = []
    for row in rows or []:
        try:
            ts = int(row[0])
            if ts + 60_000 > now_ms or len(row) < 7:
                continue
            parsed.append({
                "ts": ts, "o": num(row[1]), "h": num(row[2]), "l": num(row[3]),
                "c": num(row[4]), "turnover": num(row[6], 0.0),
            })
        except (TypeError, ValueError, IndexError):
            continue
    parsed.sort(key=lambda x: x["ts"])
    if not parsed:
        return {"status": "NO_CLOSED_CANDLES"}
    first, last = parsed[0], parsed[-1]
    return {
        "status": "OK", "candle_count": len(parsed),
        "last_closed_candle_ms": last["ts"], "price": last["c"],
        "return_pct": ((last["c"] / first["o"]) - 1) * 100 if first["o"] else None,
        "turnover_usdt": sum(x["turnover"] for x in parsed),
    }


def oi_metrics(data, now_ms):
    rows = list_data(data)
    row = rows[0] if rows else {}
    value = num(row.get("openInterest")) if isinstance(row, dict) else None
    stamp = int(num((data or {}).get("ts"), now_ms) or now_ms) if isinstance(data, dict) else now_ms
    return {"status": "OK" if value is not None else "NO_OI", "open_interest_base": value, "timestamp_ms": stamp}


async def fetch_symbol(session, sem, symbol, now_ms, gates):
    async with sem:
        params = {"category": CATEGORY, "symbol": symbol}
        specs = [
            ("book", "/api/v3/market/orderbook", {**params, "limit": "100"}),
            ("fills", "/api/v3/market/fills", {**params, "limit": "100"}),
            ("candles", "/api/v3/market/candles", {**params, "interval": "1m", "limit": "6", "type": "market"}),
            ("oi", "/api/v3/market/open-interest", params),
        ]
        result = {"symbol": symbol, "timestamp_ms": now_ms}
        for key, path, query in specs:
            try:
                data = await get_json(session, path, query, gates)
                if key == "book":
                    result["book"] = book_metrics(data)
                elif key == "fills":
                    result["fills"] = fill_metrics(list_data(data), now_ms)
                elif key == "candles":
                    result["price_window"] = candle_metrics(data, now_ms)
                else:
                    result["open_interest"] = oi_metrics(data, now_ms)
            except Exception as exc:
                result[key + "_error"] = str(exc)[:180]
        return result


def load_snapshots(now_ms):
    cutoff = now_ms - KEEP_DAYS * 86_400_000
    rows = []
    try:
        for line in SNAPSHOTS.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if int(item.get("timestamp_ms", 0)) >= cutoff:
                    rows.append(item)
            except (ValueError, TypeError):
                continue
    except OSError:
        pass
    return rows


def median(values):
    values = [x for x in values if x is not None and math.isfinite(x)]
    return round(statistics.median(values), 6) if values else None


def pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1) * 100


def build_report(rows):
    by_symbol = defaultdict(list)
    for row in rows:
        by_symbol[row.get("symbol")].append(row)
    for values in by_symbol.values():
        values.sort(key=lambda x: x["timestamp_ms"])

    events = []
    controls = []
    for symbol, values in by_symbol.items():
        for i, row in enumerate(values):
            price = row.get("price_window", {}).get("price")
            move = row.get("price_window", {}).get("return_pct")
            if price is None or move is None:
                continue
            direction = "LONG" if move > 0 else "SHORT" if move < 0 else None
            if not direction:
                continue
            previous = values[i - 1] if i else {}
            book = row.get("book", {})
            old_book = previous.get("book", {})
            fills = row.get("fills", {})
            oi = row.get("open_interest", {})
            old_oi = previous.get("open_interest", {})
            oi_change = pct_change(oi.get("open_interest_base"), old_oi.get("open_interest_base"))
            imbalance = fills.get("buy_sell_imbalance")
            taker_aligned = imbalance is not None and (imbalance > 0.10 if direction == "LONG" else imbalance < -0.10)
            band = "0p5"
            opposing_key = ("ask_depth_usdt_" if direction == "LONG" else "bid_depth_usdt_") + band
            depth_change = pct_change(book.get(opposing_key), old_book.get(opposing_key))
            book_withdrawal = depth_change is not None and depth_change <= -15
            liq = row.get("liquidations", {})
            aligned_liq = liq.get("short_liquidation_usdt", 0) if direction == "LONG" else liq.get("long_liquidation_usdt", 0)
            features = {
                "taker_aligned": bool(taker_aligned),
                "opposing_book_depth_withdrawal_15pct": bool(book_withdrawal),
                "open_interest_increased": oi_change is not None and oi_change >= 0.10,
                "aligned_liquidations_present": aligned_liq > 0,
            }
            event = {
                "symbol": symbol, "timestamp_ms": row["timestamp_ms"], "direction": direction,
                "move_5m_pct": move, "turnover_5m_usdt": row.get("price_window", {}).get("turnover_usdt"),
                "taker_imbalance": imbalance, "taker_fill_count": fills.get("fill_count"),
                "fill_sample_span_seconds": fills.get("sample_span_seconds"),
                "fill_newest_age_seconds": fills.get("newest_fill_age_seconds"),
                "spread_bps": book.get("spread_bps"), "opposing_depth_change_pct": depth_change,
                "oi_change_pct_since_previous_sample": oi_change,
                "aligned_liquidation_usdt": aligned_liq, "features": features,
            }
            # A 5m move threshold creates the event cohort; smaller moves are controls.
            if abs(move) >= 0.50:
                events.append(event)
            elif abs(move) <= 0.15:
                controls.append(event)

    # Forward outcome: the next available snapshot around +10 minutes.
    def add_forward(group):
        for event in group:
            values = by_symbol[event["symbol"]]
            future = min(
                (x for x in values if x["timestamp_ms"] >= event["timestamp_ms"] + 8 * 60_000),
                key=lambda x: x["timestamp_ms"], default=None
            )
            if future and future["timestamp_ms"] <= event["timestamp_ms"] + 18 * 60_000:
                p0 = next((x.get("price_window", {}).get("price") for x in values if x["timestamp_ms"] == event["timestamp_ms"]), None)
                p1 = future.get("price_window", {}).get("price")
                raw = ((p1 / p0) - 1) * 100 if p0 and p1 else None
                event["forward_10m_return_pct"] = raw if event["direction"] == "LONG" else (-raw if raw is not None else None)
            else:
                event["forward_10m_return_pct"] = None
    add_forward(events)
    add_forward(controls)

    def cohort_stats(group):
        valid = [x for x in group if x.get("forward_10m_return_pct") is not None]
        out = {
            "observations": len(group), "with_forward_outcome": len(valid),
            "median_forward_10m_directional_return_pct": median([x["forward_10m_return_pct"] for x in valid]),
            "positive_forward_rate_pct": round(100 * sum(x["forward_10m_return_pct"] > 0 for x in valid) / len(valid), 2) if valid else None,
        }
        for key in ("taker_aligned", "opposing_book_depth_withdrawal_15pct", "open_interest_increased", "aligned_liquidations_present"):
            subset = [x for x in valid if x["features"].get(key)]
            out[key] = {
                "count": len(subset),
                "median_forward_return_pct": median([x["forward_10m_return_pct"] for x in subset]),
                "positive_forward_rate_pct": round(100 * sum(x["forward_10m_return_pct"] > 0 for x in subset) / len(subset), 2) if subset else None,
            }
        combined = [x for x in valid if sum(bool(v) for v in x["features"].values()) >= 2]
        out["two_or_more_fuels"] = {
            "count": len(combined),
            "median_forward_return_pct": median([x["forward_10m_return_pct"] for x in combined]),
            "positive_forward_rate_pct": round(100 * sum(x["forward_10m_return_pct"] > 0 for x in combined) / len(combined), 2) if combined else None,
        }
        return out

    return {
        "events": cohort_stats(events), "controls": cohort_stats(controls),
        "event_rows": events[-500:], "control_rows": controls[-500:],
        "symbols": len(by_symbol), "snapshots": len(rows),
        "first_snapshot_utc": datetime.fromtimestamp(min((x["timestamp_ms"] for x in rows), default=0) / 1000, timezone.utc).isoformat() if rows else None,
        "last_snapshot_utc": datetime.fromtimestamp(max((x["timestamp_ms"] for x in rows), default=0) / 1000, timezone.utc).isoformat() if rows else None,
    }


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    gates = {
        "/api/v3/market/instruments": Gate(),
        "/api/v3/market/tickers": Gate(),
        "/api/v3/market/orderbook": Gate(),
        "/api/v3/market/fills": Gate(),
        "/api/v3/market/candles": Gate(),
        "/api/v3/market/open-interest": Gate(),
        "/api/v3/market/liquidations": Gate(0.25),
    }
    timeout = aiohttp.ClientTimeout(total=35, connect=12)
    connector = aiohttp.TCPConnector(limit=30)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        instruments, tickers, liquidation_data = await asyncio.gather(
            get_json(session, "/api/v3/market/instruments", {"category": CATEGORY}, gates),
            get_json(session, "/api/v3/market/tickers", {"category": CATEGORY}, gates),
            get_json(session, "/api/v3/market/liquidations", {"category": CATEGORY, "limit": "100"}, gates),
        )
        eligible = {
            x.get("symbol") for x in instruments or []
            if x.get("symbol") and x.get("status") == "online"
            and (x.get("instrumentType") == "crypto" or x.get("symbolType", "crypto") == "crypto")
            and (x.get("type") == "perpetual" or x.get("instrumentType") == "crypto" or x.get("symbolType") == "crypto")
        }
        universe = sorted(
            [x for x in tickers or [] if x.get("symbol") in eligible],
            key=lambda x: num(x.get("turnover24h"), 0) or 0, reverse=True
        )[:MAX_SYMBOLS]
        sem = asyncio.Semaphore(24)
        current = await asyncio.gather(*(
            fetch_symbol(session, sem, item["symbol"], now_ms, gates) for item in universe
        ))

    # The liquidation endpoint is global and returns only its latest page (max 100).
    # Filter it to the current collection interval; never imply complete market coverage.
    previous_rows = load_snapshots(now_ms)
    last_sample_ms = max((x["timestamp_ms"] for x in previous_rows), default=now_ms - 6 * 60_000)
    liq_by_symbol = defaultdict(lambda: {"long_liquidation_usdt": 0.0, "short_liquidation_usdt": 0.0, "records": 0})
    for item in list_data(liquidation_data):
        if not isinstance(item, dict):
            continue
        ts = int(num(item.get("ts"), 0) or 0)
        if not (last_sample_ms - 60_000 <= ts <= now_ms + 60_000):
            continue
        symbol = item.get("symbol")
        side = str(item.get("side", "")).lower()
        value = (num(item.get("price"), 0) or 0) * (num(item.get("amount"), 0) or 0)
        if symbol and value > 0:
            if side == "buy":  # Bitget documents buy as long-position liquidation.
                liq_by_symbol[symbol]["long_liquidation_usdt"] += value
            elif side == "sell":  # sell is short-position liquidation.
                liq_by_symbol[symbol]["short_liquidation_usdt"] += value
            liq_by_symbol[symbol]["records"] += 1

    previous_by_symbol = {}
    for row in previous_rows:
        previous_by_symbol[row.get("symbol")] = row
    for row in current:
        row["liquidations"] = liq_by_symbol[row["symbol"]]
        prev = previous_by_symbol.get(row["symbol"], {})
        book, old_book = row.get("book", {}), prev.get("book", {})
        row["book_depth_change_pct_vs_previous"] = {
            band: {
                side: pct_change(book.get(side + "_depth_usdt_" + band), old_book.get(side + "_depth_usdt_" + band))
                for side in ("bid", "ask")
            } for band in ("0p1", "0p25", "0p5", "1p")
        }
        row["open_interest_change_pct_vs_previous"] = pct_change(
            row.get("open_interest", {}).get("open_interest_base"),
            prev.get("open_interest", {}).get("open_interest_base"),
        )

    batch = {
        "timestamp_ms": now_ms,
        "timestamp_utc": datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat(),
        "symbols_requested": len(universe),
        "symbols_with_book": sum(x.get("book", {}).get("status") == "OK" for x in current),
        "symbols_with_fills": sum(x.get("fills", {}).get("status") == "OK" for x in current),
        "symbols_with_oi": sum(x.get("open_interest", {}).get("status") == "OK" for x in current),
        "liquidation_records_seen_in_recent_global_page": len(list_data(liquidation_data)),
        "liquidation_records_in_collection_interval": sum(x["records"] for x in liq_by_symbol.values()),
        "trading_enabled": False,
    }
    # Compact rows retain only the data needed for event/control attribution.
    compact = []
    for row in current:
        compact.append({
            "timestamp_ms": now_ms, "symbol": row["symbol"],
            "price_window": row.get("price_window", {}),
            "fills": row.get("fills", {}),
            "book": row.get("book", {}),
            "open_interest": row.get("open_interest", {}),
            "open_interest_change_pct_vs_previous": row.get("open_interest_change_pct_vs_previous"),
            "book_depth_change_pct_vs_previous": row.get("book_depth_change_pct_vs_previous"),
            "liquidations": row.get("liquidations", {}),
        })
    all_rows = previous_rows + compact
    cutoff = now_ms - KEEP_DAYS * 86_400_000
    all_rows = [x for x in all_rows if int(x.get("timestamp_ms", 0)) >= cutoff]
    SNAPSHOTS.write_text("".join(json.dumps(x, separators=(",", ":")) + "\n" for x in all_rows), encoding="utf-8")
    summary = build_report(all_rows)
    summary["latest_collection"] = batch
    LATEST.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    ev, ctl = summary["events"], summary["controls"]
    lines = [
        "# Bitget movement mechanics: live microstructure event study", "",
        "Generated UTC: " + datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat(),
        "This is a forward-collected observational study. Historical order-book depth and recent public fills are not backfilled by these endpoints.",
        "Universe: top " + str(MAX_SYMBOLS) + " eligible online USDT perpetuals by current 24h turnover; existing candle scanner covers its wider universe.",
        "Latest cycle: " + json.dumps(batch, sort_keys=True), "",
        "## What is being measured",
        "- Aggressive-flow proxy: Bitget-reported buy/sell side of the latest public fills, weighted by price × size. The side is a proxy; do not label it proven aggressor flow without exchange-side semantic validation.",
        "- Liquidity withdrawal: change in opposing-side order-book notional within 0.5% of mid versus the prior collection snapshot. A snapshot is not proof of spoofing or cancellation intent.",
        "- Position expansion: change in aggregate open interest since the prior snapshot. OI does not identify which side opened.",
        "- Liquidation pressure: public platform liquidation records; Bitget documents buy as long liquidation and sell as short liquidation. The global endpoint returns only its latest page (up to 100), so coverage is incomplete.",
        "- Outcome: direction-adjusted price return from the movement snapshot to the next available snapshot at least 8 minutes later (accepted up to 18 minutes).",
        "",
        "## Event versus control cohorts",
        "Event = absolute 5m candle return >= 0.50%; control = absolute 5m candle return <= 0.15%.",
        "Events: " + json.dumps(ev, indent=2),
        "Controls: " + json.dumps(ctl, indent=2),
        "",
        "## Interpretation limits",
        "- First collection has no prior book/OI snapshot; liquidity withdrawal and OI change become measurable only after repeat samples.",
        "- The 100-fill public endpoint is a recent rolling sample, not a complete fixed five-minute tape. Fill age and sample span are stored so stale samples can be excluded.",
        "- The 100-record global liquidation page is not guaranteed to include every symbol or liquidation in the interval.",
        "- Order-book depth is a displayed snapshot and may change or cancel; it is not executed volume.",
        "- These are associations and forward observations, not causal proof or a profitable strategy. No orders are placed.",
        "- Minimum useful sample: several days with repeated snapshots and adequate fill/book/OI coverage.",
        "",
        "Raw snapshots: movement_mechanics_snapshots.jsonl",
        "Latest structured result: movement_mechanics_latest.json",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "latest_collection": batch,
                      "event_observations": ev["observations"],
                      "control_observations": ctl["observations"],
                      "snapshots_retained": len(all_rows), "trading_enabled": False}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
