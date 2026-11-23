"""Read-only Bitget USDT perpetual market snapshot for shadow research.

This module uses public market-data endpoints only. It has no credentials,
account access, order placement, leverage, or position-management code.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

BASE_URL = "https://api.bitget.com"
CATEGORY = "USDT-FUTURES"
MIN_TURNOVER_DEFAULT = 500_000.0
DEPTH_LIMIT = 1000
NOTIONALS = (100.0, 500.0, 1000.0)
LOG = logging.getLogger("shadow_research")


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else default
    except (TypeError, ValueError):
        return default


def book_depth(levels: list, mid: float, side: str, band_pct: float) -> float:
    """Return quote notional within band_pct of mid for one side."""
    if mid <= 0:
        return 0.0
    total = 0.0
    for row in levels:
        if len(row) < 2:
            continue
        price, qty = as_float(row[0]), as_float(row[1])
        if price <= 0 or qty <= 0:
            continue
        distance = (price / mid - 1) * 100 if side == "asks" else (1 - price / mid) * 100
        if 0 <= distance <= band_pct:
            total += price * qty
    return total


def simulate_market_fill(levels: list, notional: float, side: str, mid: float) -> dict:
    """Walk visible book levels for quote notional; never submits an order."""
    remaining = float(notional)
    base_filled = 0.0
    quote_spent = 0.0
    for row in levels:
        if len(row) < 2:
            continue
        price, available_qty = as_float(row[0]), as_float(row[1])
        if price <= 0 or available_qty <= 0:
            continue
        available_quote = price * available_qty
        take_quote = min(remaining, available_quote)
        take_qty = take_quote / price
        base_filled += take_qty
        quote_spent += take_quote
        remaining -= take_quote
        if remaining <= 1e-8:
            break
    filled = notional - max(remaining, 0.0)
    vwap = quote_spent / base_filled if base_filled else 0.0
    reference = mid
    slippage_bps = ((vwap / reference) - 1) * 10_000 if reference > 0 and side == "buy" else (
        (1 - vwap / reference) * 10_000 if reference > 0 and vwap > 0 else None
    )
    return {
        "requested_usdt": notional,
        "filled_usdt": round(filled, 8),
        "unfilled_usdt": round(max(remaining, 0.0), 8),
        "vwap": vwap or None,
        "slippage_bps_vs_mid": round(slippage_bps, 4) if slippage_bps is not None else None,
        "fully_filled_visible_book": remaining <= 1e-8,
    }


async def get_json(session: aiohttp.ClientSession, path: str, params: dict) -> dict:
    url = BASE_URL + path
    last_error = None
    for attempt in range(3):
        try:
            async with session.get(url, params=params) as response:
                if response.status in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"Bitget HTTP {response.status}")
                response.raise_for_status()
                payload = await response.json()
                if payload.get("code") != "00000":
                    raise RuntimeError(f"Bitget API error: {payload.get('code')} {payload.get('msg')}")
                return payload
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"Request failed for {path}: {last_error}")


async def collect(min_turnover: float, top_depth: int, output_dir: Path) -> tuple[Path, Path]:
    timeout = aiohttp.ClientTimeout(total=20)
    connector = aiohttp.TCPConnector(limit=8)
    headers = {"User-Agent": "Bitget-Shadow-Research/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
        instruments_payload, tickers_payload = await asyncio.gather(
            get_json(session, "/api/v3/market/instruments", {"category": CATEGORY}),
            get_json(session, "/api/v3/market/tickers", {"category": CATEGORY}),
        )

        instruments = {}
        for item in instruments_payload.get("data", []):
            if item.get("status") != "online":
                continue
            if item.get("type") != "perpetual":
                continue
            instrument_type = item.get("instrumentType") or item.get("symbolType")
            if instrument_type and instrument_type.lower() != "crypto":
                continue
            instruments[item.get("symbol")] = item

        rows = []
        for ticker in tickers_payload.get("data", []):
            symbol = ticker.get("symbol")
            instrument = instruments.get(symbol)
            if not instrument:
                continue
            turnover = as_float(ticker.get("turnover24h"))
            if turnover < min_turnover:
                continue
            bid = as_float(ticker.get("bid1Price"))
            ask = as_float(ticker.get("ask1Price"))
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
            spread_bps = ((ask - bid) / mid * 10_000) if mid > 0 and ask >= bid else None
            rows.append({
                "symbol": symbol,
                "base_coin": instrument.get("baseCoin"),
                "status": instrument.get("status"),
                "contract_type": instrument.get("type"),
                "market_cap_usd": None,
                "market_cap_band": "UNVERIFIED",
                "turnover24h_usdt": turnover,
                "volume24h_base": as_float(ticker.get("volume24h")),
                "last_price": as_float(ticker.get("lastPrice")),
                "mark_price": as_float(ticker.get("markPrice")),
                "index_price": as_float(ticker.get("indexPrice")),
                "bid1": bid,
                "ask1": ask,
                "spread_bps": round(spread_bps, 4) if spread_bps is not None else None,
                "funding_rate": as_float(ticker.get("fundingRate")),
                "open_interest": as_float(ticker.get("openInterest")),
                "ticker_timestamp_ms": ticker.get("ts"),
                "maker_fee_rate": as_float(instrument.get("makerFeeRate")),
                "taker_fee_rate": as_float(instrument.get("takerFeeRate")),
                "depth_timestamp_ms": None,
                "depth_usdt_0_1pct_bids": None,
                "depth_usdt_0_1pct_asks": None,
                "depth_usdt_0_5pct_bids": None,
                "depth_usdt_0_5pct_asks": None,
                "depth_usdt_1pct_bids": None,
                "depth_usdt_1pct_asks": None,
                "market_buy_100": None,
                "market_sell_100": None,
                "market_buy_500": None,
                "market_sell_500": None,
                "market_buy_1000": None,
                "market_sell_1000": None,
            })

        rows.sort(key=lambda item: item["turnover24h_usdt"], reverse=True)
        depth_targets = rows[:max(0, top_depth)]
        semaphore = asyncio.Semaphore(5)

        async def add_depth(row: dict) -> None:
            async with semaphore:
                payload = await get_json(
                    session,
                    "/api/v3/market/orderbook",
                    {"category": CATEGORY, "symbol": row["symbol"], "limit": str(DEPTH_LIMIT)},
                )
                data = payload.get("data") or {}
                asks, bids = data.get("a") or [], data.get("b") or []
                row["depth_timestamp_ms"] = data.get("ts")
                bid, ask = row["bid1"], row["ask1"]
                mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0.0
                for band in (0.1, 0.5, 1.0):
                    key = str(band).replace(".", "_")
                    row[f"depth_usdt_{key}pct_bids"] = round(book_depth(bids, mid, "bids", band), 4)
                    row[f"depth_usdt_{key}pct_asks"] = round(book_depth(asks, mid, "asks", band), 4)
                for amount in NOTIONALS:
                    row[f"market_buy_{int(amount)}"] = simulate_market_fill(asks, amount, "buy", mid)
                    row[f"market_sell_{int(amount)}"] = simulate_market_fill(bids, amount, "sell", mid)

        results = await asyncio.gather(*(add_depth(row) for row in depth_targets), return_exceptions=True)
        for row, result in zip(depth_targets, results):
            if isinstance(result, Exception):
                row["depth_error"] = str(result)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"bitget_usdt_perp_snapshot_{stamp}.json"
    csv_path = output_dir / f"bitget_usdt_perp_snapshot_{stamp}.csv"
    report = {
        "schema_version": 1,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "exchange": "Bitget",
        "market": CATEGORY,
        "data_scope": "public market data only; no account endpoints or trading actions",
        "minimum_turnover_usdt": min_turnover,
        "depth_collected_for_top_n_by_turnover": len(depth_targets),
        "candidate_count": len(rows),
        "market_cap_status": "not supplied by Bitget futures endpoints; must be joined from a separate timestamped source",
        "source_endpoints": [
            "/api/v3/market/instruments?category=USDT-FUTURES",
            "/api/v3/market/tickers?category=USDT-FUTURES",
            "/api/v3/market/orderbook?category=USDT-FUTURES",
        ],
        "candidates": rows,
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if rows:
        fieldnames = list(rows[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    else:
        csv_path.write_text("symbol,turnover24h_usdt\n", encoding="utf-8")
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Bitget USDT perpetual market snapshot")
    parser.add_argument("--min-turnover", type=float, default=MIN_TURNOVER_DEFAULT)
    parser.add_argument("--top-depth", type=int, default=50)
    parser.add_argument("--output-dir", default="reports/shadow")
    args = parser.parse_args()
    if args.min_turnover < 0 or args.top_depth < 0:
        parser.error("min-turnover and top-depth must be non-negative")
    json_path, csv_path = asyncio.run(collect(args.min_turnover, args.top_depth, Path(args.output_dir)))
    print(f"Saved read-only market snapshot: {json_path}")
    print(f"Saved CSV: {csv_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
