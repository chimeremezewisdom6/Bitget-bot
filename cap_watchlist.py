"""Build a provisional 4-band Bitget USDT perpetual watchlist.

Uses public Bitget futures data and CoinGecko public search/market-cap data.
Ticker-symbol matches are not treated as verified identities unless a human
adds an explicit verified override in config/asset_identity_overrides.json.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent
BANDS_PATH = ROOT / "config/market_cap_bands.json"
OVERRIDES_PATH = ROOT / "config/asset_identity_overrides.json"
OUT_DIR = ROOT / "reports/market_cap_watchlist"
BITGET = "https://api.bitget.com"
COINGECKO = "https://api.coingecko.com/api/v3"


def number(value, default=0.0):
    try:
        x = float(value)
        return x if x == x and abs(x) != float("inf") else default
    except (TypeError, ValueError):
        return default


def classify_market_cap(market_cap, bands):
    if market_cap is None:
        return "UNVERIFIED"
    cap = number(market_cap, -1)
    if cap < 0:
        return "UNVERIFIED"
    for band in bands:
        low = number(band["min_usd"])
        high = band.get("max_usd")
        if cap >= low and (high is None or cap < number(high)):
            return band["name"]
    return "OUT_OF_BANDS"


def match_exact_symbol(base_coin, search_coins, override=None):
    if override:
        if isinstance(override, str):
            return override, "manual_override_unverified"
        if isinstance(override, dict) and override.get("coingecko_id"):
            status = "manually_verified_override" if override.get("verified") is True else "manual_override_unverified"
            return override["coingecko_id"], status
    matches = {}
    for coin in search_coins or []:
        if str(coin.get("symbol", "")).lower() == str(base_coin).lower() and coin.get("id"):
            matches[coin["id"]] = coin
    if len(matches) == 1:
        return next(iter(matches)), "unique_exact_symbol_needs_review"
    if len(matches) > 1:
        return None, "ambiguous_exact_symbol"
    return None, "no_exact_symbol_match"


def select_watchlist(candidates, bands, per_group=3):
    grouped = {band["name"]: [] for band in bands}
    for row in candidates:
        name = row.get("market_cap_band")
        if name in grouped and row.get("identity_status") in (
            "unique_exact_symbol_needs_review", "manually_verified_override"
        ):
            grouped[name].append(row)
    result = {}
    for band in bands:
        rows = grouped[band["name"]]
        rows.sort(key=lambda x: (number(x.get("turnover24h_usdt")), -number(x.get("spread_bps"), 1e9)), reverse=True)
        result[band["name"]] = rows[:per_group]
    return result


async def get_json(session, url, params=None):
    last = None
    for attempt in range(4):
        try:
            async with session.get(url, params=params, timeout=25) as response:
                if response.status == 429 or response.status >= 500:
                    raise RuntimeError(f"HTTP {response.status}")
                response.raise_for_status()
                payload = await response.json()
                if "api.bitget.com" in url and payload.get("code") != "00000":
                    raise RuntimeError(f"Bitget {payload.get('code')}: {payload.get('msg')}")
                return payload
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
            last = exc
            if attempt < 3:
                await asyncio.sleep(1.5 * (2 ** attempt))
    raise RuntimeError(f"GET failed: {url}: {last}")


async def build():
    config = json.loads(BANDS_PATH.read_text(encoding="utf-8"))
    override_config = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    overrides = override_config.get("coingecko_ids_by_base_coin", {})
    bands = config["bands"]
    min_turnover = number(config.get("minimum_turnover_usdt"), 500000)
    per_group = int(config.get("contracts_per_group", 3))
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": "Bitget-Cap-Watchlist-Research/1.0"}
    errors = []
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        instruments_payload, tickers_payload = await asyncio.gather(
            get_json(session, BITGET + "/api/v3/market/instruments", {"category": "USDT-FUTURES"}),
            get_json(session, BITGET + "/api/v3/market/tickers", {"category": "USDT-FUTURES"}),
        )
        instruments = {
            x.get("symbol"): x for x in instruments_payload.get("data", [])
            if x.get("symbol") and x.get("status") == "online" and x.get("type") == "perpetual"
        }
        ticker_by_symbol = {x.get("symbol"): x for x in tickers_payload.get("data", []) if x.get("symbol")}
        eligible = []
        for symbol, instrument in instruments.items():
            ticker = ticker_by_symbol.get(symbol)
            if not ticker or number(ticker.get("turnover24h")) < min_turnover:
                continue
            eligible.append((instrument, ticker))
        eligible.sort(key=lambda pair: number(pair[1].get("turnover24h")), reverse=True)

        identity_by_base = {}
        for instrument, _ticker in eligible:
            base = str(instrument.get("baseCoin") or "").strip()
            if not base or base in identity_by_base:
                continue
            override = overrides.get(base.upper()) or overrides.get(base)
            try:
                if override:
                    coin_id, identity_status = match_exact_symbol(base, [], override)
                else:
                    search = await get_json(session, COINGECKO + "/search", {"query": base})
                    coin_id, identity_status = match_exact_symbol(base, search.get("coins", []))
                    await asyncio.sleep(2.1)
                identity_by_base[base] = (coin_id, identity_status)
            except Exception as exc:
                identity_by_base[base] = (None, "lookup_error")
                errors.append({"base_coin": base, "error": str(exc)[:300]})

        ids = sorted({value[0] for value in identity_by_base.values() if value[0]})
        markets = {}
        for start in range(0, len(ids), 100):
            batch = ids[start:start + 100]
            try:
                rows = await get_json(session, COINGECKO + "/coins/markets", {
                    "vs_currency": config.get("currency", "usd"),
                    "ids": ",".join(batch),
                    "per_page": 100,
                    "page": 1,
                    "sparkline": "false",
                })
                for row in rows:
                    markets[row.get("id")] = row
            except Exception as exc:
                errors.append({"market_cap_batch": batch, "error": str(exc)[:300]})

        candidates = []
        for instrument, ticker in eligible:
            symbol = instrument["symbol"]
            base = str(instrument.get("baseCoin") or "")
            coin_id, identity_status = identity_by_base.get(base, (None, "no_base_coin"))
            market = markets.get(coin_id, {}) if coin_id else {}
            cap = market.get("market_cap")
            band = classify_market_cap(cap, bands)
            bid, ask = number(ticker.get("bid1Price")), number(ticker.get("ask1Price"))
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
            spread = (ask - bid) / mid * 10000 if mid > 0 and ask >= bid else None
            candidates.append({
                "symbol": symbol,
                "base_coin": base,
                "contract_status": instrument.get("status"),
                "contract_type": instrument.get("type"),
                "turnover24h_usdt": number(ticker.get("turnover24h")),
                "last_price": number(ticker.get("lastPrice")),
                "bid1": bid,
                "ask1": ask,
                "spread_bps": spread,
                "funding_rate": number(ticker.get("fundingRate")),
                "open_interest": number(ticker.get("openInterest")),
                "coingecko_id": coin_id,
                "asset_name": market.get("name"),
                "market_cap_usd": cap,
                "market_cap_updated_at": market.get("last_updated"),
                "market_cap_band": band,
                "identity_status": identity_status,
                "identity_note": "Unique ticker match is provisional; manually verify project identity before calling the watchlist final."
            })

        watchlist = select_watchlist(candidates, bands, per_group)
        selected = [row for group in watchlist.values() for row in group]
        semaphore = asyncio.Semaphore(4)

        async def add_depth(row):
            async with semaphore:
                payload = await get_json(session, BITGET + "/api/v3/market/orderbook", {
                    "category": "USDT-FUTURES", "symbol": row["symbol"], "limit": "1000"
                })
                book = payload.get("data", {})
                asks, bids = book.get("a", []), book.get("b", [])
                mid = (row["bid1"] + row["ask1"]) / 2 if row["bid1"] and row["ask1"] else 0
                def depth(levels):
                    return round(sum(number(p) * number(q) for p, q in levels
                                     if mid and abs(number(p) / mid - 1) <= 0.005), 4)
                row["depth_0_5pct_bid_usdt"] = depth(bids)
                row["depth_0_5pct_ask_usdt"] = depth(asks)
                row["orderbook_timestamp_ms"] = book.get("ts")
                row["liquidity_warning"] = (
                    "WIDE_SPREAD_OR_SHALLOW_VISIBLE_DEPTH"
                    if row.get("spread_bps") is None or row["spread_bps"] > 30
                    or min(row["depth_0_5pct_bid_usdt"], row["depth_0_5pct_ask_usdt"]) < 5000
                    else "NO_IMMEDIATE_WARNING; repeat snapshots still required"
                )

        depth_results = await asyncio.gather(*(add_depth(row) for row in selected), return_exceptions=True)
        for row, result in zip(selected, depth_results):
            if isinstance(result, Exception):
                row["depth_error"] = str(result)[:300]

    stamp = datetime.now(timezone.utc).isoformat()
    symbols = sorted({row["symbol"] for row in selected})
    report = {
        "generated_at_utc": stamp,
        "exchange": "Bitget",
        "market": "USDT-FUTURES",
        "market_cap_source": "CoinGecko public search and coins/markets API",
        "minimum_turnover_usdt": min_turnover,
        "cap_band_definitions": bands,
        "candidate_count": len(candidates),
        "eligible_contracts_with_cap_identity": sum(bool(row.get("market_cap_usd")) for row in candidates),
        "watchlist_symbols": symbols,
        "groups": watchlist,
        "candidates": candidates,
        "lookup_errors": errors,
        "important": [
            "Bitget public USDT perpetual contracts only; Spot turnover is not used.",
            "A unique exact ticker match is provisional and can still be the wrong asset; manually verify identity.",
            "Ambiguous or unmatched symbols remain unverified and are not assigned a cap band.",
            "Market caps are provider snapshots with their own timestamp, not Bitget data.",
            "Three contracts per group is a maximum, not a quota. Empty/short groups must remain short.",
            "Spread and visible depth are a one-time screen, not proof of persistent liquidity or profitable execution."
        ]
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "current_watchlist.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT_DIR / "current_watchlist.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "selected": len(symbols),
                      "groups": {k: len(v) for k, v in watchlist.items()},
                      "errors": len(errors), "output": str(OUT_DIR)}, indent=2))


def render_markdown(report):
    lines = [
        "# Provisional Bitget USDT Perpetual Market-Cap Watchlist",
        "",
        f"- Generated UTC: {report['generated_at_utc']}",
        f"- Eligible contracts: {report['candidate_count']}",
        f"- Selected contracts: {len(report['watchlist_symbols'])}",
        f"- Market-cap source: {report['market_cap_source']}",
        "",
        "A unique symbol match is provisional until manually identity-checked. This is a research watchlist, not a trade recommendation.",
    ]
    for band in report["cap_band_definitions"]:
        rows = report["groups"].get(band["name"], [])
        lines += ["", f"## {band['label']} ({band['name']})", ""]
        if not rows:
            lines.append("No verified-enough candidate found in this pass. Do not fill the group by guessing.")
            continue
        lines += ["| Contract | Asset | Market cap USD | 24h futures turnover | Spread bps | 0.5% bid/ask depth USD | Identity | Liquidity flag |",
                  "|---|---|---:|---:|---:|---:|---|---|"]
        for row in rows:
            depth = f"{row.get('depth_0_5pct_bid_usdt', 'n/a')} / {row.get('depth_0_5pct_ask_usdt', 'n/a')}"
            lines.append(f"| {row['symbol']} | {row.get('asset_name') or row['base_coin']} | {row.get('market_cap_usd')} | {row['turnover24h_usdt']:.0f} | {row.get('spread_bps')} | {depth} | {row['identity_status']} | {row.get('liquidity_warning', row.get('depth_error', 'pending'))} |")
    lines += ["", "## Rules", ""]
    lines += [f"- {item}" for item in report["important"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    asyncio.run(build())
