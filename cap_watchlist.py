"""Build a Bitget-only USDT perpetual activity watchlist.

Bitget does not publish circulating market capitalisation in its futures
instrument/ticker API. This module therefore never guesses market-cap bands.
It groups contracts by Bitget-reported 24h futures turnover instead.
"""
import asyncio
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports/market_cap_watchlist"
BITGET = "https://api.bitget.com"
CATEGORY = "USDT-FUTURES"
MIN_TURNOVER_USDT = 50_000
BANDS = [
    {"name": "under_1m_turnover", "label": "Under $1m 24h futures turnover", "min_usd": 0, "max_usd": 1_000_000},
    {"name": "1m_10m_turnover", "label": "$1m–$10m 24h futures turnover", "min_usd": 1_000_000, "max_usd": 10_000_000},
    {"name": "10m_100m_turnover", "label": "$10m–$100m 24h futures turnover", "min_usd": 10_000_000, "max_usd": 100_000_000},
    {"name": "over_100m_turnover", "label": "$100m+ 24h futures turnover", "min_usd": 100_000_000, "max_usd": None},
]


def number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def classify_turnover(turnover, bands=BANDS):
    value = number(turnover, -1)
    if value < 0:
        return "UNVERIFIED"
    for band in bands:
        if value >= band["min_usd"] and (band["max_usd"] is None or value < band["max_usd"]):
            return band["name"]
    return "UNVERIFIED"


async def get_json(session, path, params=None):
    last_error = None
    for attempt in range(4):
        try:
            async with session.get(BITGET + path, params=params, timeout=20) as response:
                if response.status == 429 or response.status >= 500:
                    raise RuntimeError(f"temporary Bitget HTTP {response.status}")
                response.raise_for_status()
                payload = await response.json()
                if payload.get("code") != "00000":
                    raise RuntimeError(f"Bitget {payload.get('code')}: {payload.get('msg')}")
                return payload
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < 3:
                await asyncio.sleep(min(0.75 * (2 ** attempt), 6))
    raise RuntimeError(f"{path} failed after retries: {last_error}")


def render_markdown(report):
    lines = [
        "# Bitget USDT Perpetual Activity Watchlist",
        "",
        f"- Generated UTC: {report['generated_at_utc']}",
        f"- Eligible online perpetual contracts: {report['candidate_count']}",
        f"- Selected contracts: {len(report['watchlist_symbols'])}",
        "- Primary source: Bitget USDT-FUTURES instruments, tickers and order books",
        "- Grouping metric: Bitget 24-hour futures turnover (USDT), NOT market capitalisation",
        "",
        "Bitget's futures market endpoints do not provide circulating market cap. No external market-cap provider or ticker-symbol guess is used.",
    ]
    for band in BANDS:
        rows = report["groups"].get(band["name"], [])
        lines += ["", f"## {band['label']}", ""]
        if not rows:
            lines.append("No eligible contract in this turnover range during this snapshot.")
            continue
        lines += [
            "| Contract | Bitget name | 24h turnover USDT | Spread bps | 0.5% bid depth USDT | 0.5% ask depth USDT | Liquidity flag |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
        for row in rows:
            lines.append(
                f"| {row['symbol']} | {row.get('full_name') or row.get('base_coin') or row['symbol']} "
                f"| {row['turnover24h_usdt']:.0f} | {row.get('spread_bps')} "
                f"| {row.get('depth_0_5pct_bid_usdt', 'n/a')} | {row.get('depth_0_5pct_ask_usdt', 'n/a')} "
                f"| {row.get('liquidity_flag', 'not_checked')} |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        "- Turnover is trading activity, not market cap and not proof of liquidity at the required size.",
        "- A contract can have high reported turnover but a thin visible book, wide spread, or unstable depth.",
        "- Market-cap bands cannot honestly be produced from these Bitget futures endpoints alone.",
        "- The watchlist is a research universe, not a trade recommendation.",
    ]
    return "\n".join(lines) + "\n"


async def build(per_group=3):
    timeout = aiohttp.ClientTimeout(total=35, connect=10)
    headers = {"User-Agent": "Bitget-ReadOnly-Research/2.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        instruments, tickers = await asyncio.gather(
            get_json(session, "/api/v3/market/instruments", {"category": CATEGORY}),
            get_json(session, "/api/v3/market/tickers", {"category": CATEGORY}),
        )
        instrument_map = {
            row["symbol"]: row for row in instruments.get("data", [])
            if row.get("symbol") and row.get("status") == "online"
            and (row.get("type") == "perpetual" or row.get("instrumentType") == "perpetual")
            and row.get("symbolType", "crypto") == "crypto"
        }
        candidates = []
        for ticker in tickers.get("data", []):
            symbol = ticker.get("symbol")
            instrument = instrument_map.get(symbol)
            turnover = number(ticker.get("turnover24h"))
            if not instrument or turnover < MIN_TURNOVER_USDT:
                continue
            bid, ask = number(ticker.get("bid1Price")), number(ticker.get("ask1Price"))
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
            candidates.append({
                "symbol": symbol,
                "base_coin": instrument.get("baseCoin"),
                "full_name": instrument.get("fullName") or instrument.get("baseCoin"),
                "turnover24h_usdt": turnover,
                "last_price": number(ticker.get("lastPrice")),
                "price_change_24h": number(ticker.get("price24hPcnt")),
                "funding_rate": number(ticker.get("fundingRate")),
                "open_interest": number(ticker.get("openInterest")),
                "bid1": bid,
                "ask1": ask,
                "spread_bps": round((ask - bid) / mid * 10000, 4) if mid and ask >= bid else None,
                "activity_band": classify_turnover(turnover),
                "ticker_timestamp_ms": ticker.get("ts"),
                "instrument_status": instrument.get("status"),
            })

        grouped = {band["name"]: [] for band in BANDS}
        for row in candidates:
            grouped[row["activity_band"]].append(row)
        for rows in grouped.values():
            rows.sort(key=lambda row: row["turnover24h_usdt"], reverse=True)

        selected = []
        for band in BANDS:
            selected.extend(grouped[band["name"]][:per_group])

        semaphore = asyncio.Semaphore(6)

        async def enrich(row):
            async with semaphore:
                try:
                    payload = await get_json(session, "/api/v3/market/orderbook", {
                        "category": CATEGORY, "symbol": row["symbol"], "limit": "100"
                    })
                    book = payload.get("data", {})
                    mid = (row["bid1"] + row["ask1"]) / 2 if row["bid1"] and row["ask1"] else 0

                    def depth(levels):
                        return round(sum(number(p) * number(q) for p, q, *_ in levels
                                         if mid and abs(number(p) / mid - 1) <= 0.005), 4)

                    row["depth_0_5pct_bid_usdt"] = depth(book.get("b", []))
                    row["depth_0_5pct_ask_usdt"] = depth(book.get("a", []))
                    row["orderbook_timestamp_ms"] = book.get("ts")
                    min_depth = min(row["depth_0_5pct_bid_usdt"], row["depth_0_5pct_ask_usdt"])
                    row["liquidity_flag"] = (
                        "WIDE_SPREAD" if row["spread_bps"] is None or row["spread_bps"] > 30
                        else "SHALLOW_VISIBLE_DEPTH" if min_depth < 5_000
                        else "INITIAL_SCREEN_ONLY"
                    )
                except Exception as exc:
                    row["depth_error"] = str(exc)[:300]
                    row["liquidity_flag"] = "DEPTH_UNAVAILABLE"

        await asyncio.gather(*(enrich(row) for row in selected))

    stamp = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at_utc": stamp,
        "exchange": "Bitget",
        "market": CATEGORY,
        "grouping_metric": "Bitget 24h futures turnover in USDT; not market capitalisation",
        "market_cap_usd": None,
        "market_cap_source": None,
        "minimum_turnover_usdt": MIN_TURNOVER_USDT,
        "activity_band_definitions": BANDS,
        "candidate_count": len(candidates),
        "watchlist_symbols": [row["symbol"] for row in selected],
        "groups": grouped,
        "selected_groups": {band["name"]: grouped[band["name"]][:per_group] for band in BANDS},
        "candidates": candidates,
        "limitations": [
            "Bitget futures instrument/ticker endpoints do not expose circulating market cap.",
            "Turnover bands must not be relabelled as market-cap bands.",
            "Reported turnover is not executable depth; use repeated order-book snapshots and fills.",
            "At most three contracts are selected per activity band; empty bands remain empty.",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "current_watchlist.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT_DIR / "current_watchlist.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "candidate_count": len(candidates),
        "selected": len(selected),
        "groups": {key: len(value[:per_group]) for key, value in grouped.items()},
        "output": str(OUT_DIR),
    }, indent=2))
    return report


if __name__ == "__main__":
    asyncio.run(build())
