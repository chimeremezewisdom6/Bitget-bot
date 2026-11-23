"""24-hour Bitget USDT futures research collector; read-only, no orders."""
import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import aiohttp

from shadow_execution import walk_book

ROOT = Path(__file__).resolve().parent
R = ROOT / "reports/daily_research"
S = R / "session.json"
O = R / "market_observations.jsonl"
C = R / "candles_1m.jsonl"
P = R / "public_trader_posts.jsonl"
E = R / "shadow_experiments.jsonl"
F = R / "candle_streak_checks.jsonl"
T = R / "trend_early_window_backtest.jsonl"
Q = R / "pending.json"
SUMMARY = R / "daily_research_summary.md"
WATCH = ROOT / "reports/market_cap_watchlist/current_watchlist.json"
BITGET = "https://api.bitget.com"
CATEGORY = "USDT-FUTURES"
FEEDS = [
    "https://www.reddit.com/r/BitcoinMarkets/new/.rss",
    "https://www.reddit.com/r/Daytrading/new/.rss",
    "https://www.reddit.com/r/CryptoCurrency/new/.rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]
HEADERS = {"User-Agent": "Bitget-ReadOnly-Research/2.0"}
MAX_SYMBOLS = 200
SYMBOL_CONCURRENCY = 6


def now():
    return datetime.now(timezone.utc)


def iso():
    return now().isoformat()


def number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def add(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def _first_env(*names):
    """Return the first non-empty credential variable, supporting common secret names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def credentials():
    # Bitget calls this value the API passphrase. Some users store it under
    # "password" or the shorter passphrase name in GitHub Actions secrets.
    return (
        _first_env("BITGET_API_KEY", "BITGET_KEY"),
        _first_env("BITGET_API_SECRET", "BITGET_SECRET_KEY", "BITGET_SECRET"),
        _first_env(
            "BITGET_API_PASSPHRASE", "BITGET_PASSPHRASE",
            "BITGET_API_PASSWORD", "BITGET_PASSWORD",
        ),
    )


def make_signature(secret, timestamp, method, request_path, query_string=""):
    """Bitget HMAC-SHA256/Base64 signature for a GET request."""
    suffix = ("?" + query_string) if query_string else ""
    message = f"{timestamp}{method.upper()}{request_path}{suffix}"
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def auth_headers(method, path, params=None):
    api_key, secret, passphrase = credentials()
    if not all((api_key, secret, passphrase)):
        raise RuntimeError("Bitget API credentials are not configured in GitHub Actions secrets.")
    query = urlencode(sorted((params or {}).items()))
    timestamp = str(int(time.time() * 1000))
    signature = make_signature(secret, timestamp, method, path, query)
    return {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "locale": "en-US",
        "Content-Type": "application/json",
    }, query


async def get_json(session, path, params=None, authenticated=False):
    last_error = None
    headers = None
    query = None
    if authenticated:
        headers, query = auth_headers("GET", path, params)
        url = BITGET + path + (("?" + query) if query else "")
    else:
        url = BITGET + path
    for attempt in range(4):
        try:
            async with session.get(
                url, params=None if authenticated else params,
                headers=headers, timeout=20
            ) as response:
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
    raise RuntimeError(f"GET {path} failed after retries: {last_error}")


async def load_private_fee_rates(session):
    """Fetch account-specific futures fees only; never query balances or positions."""
    api_key, secret, passphrase = credentials()
    if not all((api_key, secret, passphrase)):
        return {}, "NOT_CONFIGURED"
    try:
        info = await get_json(session, "/api/v3/account/info", authenticated=True)
        account = info.get("data", {}) or {}
        permission_type = account.get("permType", "unknown")
        fees = await get_json(
            session, "/api/v3/account/all-fee-rate",
            {"category": CATEGORY}, authenticated=True
        )
        data = fees.get("data", [])
        if isinstance(data, dict):
            data = data.get("list", [])
        fee_map = {
            row.get("symbol"): row for row in data
            if isinstance(row, dict) and row.get("symbol")
        }
        status = "OK_READ_ONLY_KEY" if permission_type == "read-only" else f"KEY_PERMISSION_{permission_type}"
        return fee_map, status
    except Exception as exc:
        # Do not log credentials, request headers, or signed URLs.
        return {}, "AUTHENTICATED_FEE_LOOKUP_FAILED: " + str(exc)[:220]


def ema(values, period):
    if len(values) < period:
        return None
    result = sum(values[:period]) / period
    alpha = 2 / (period + 1)
    for value in values[period:]:
        result = value * alpha + result * (1 - alpha)
    return result


def rsi(values):
    if len(values) < 15:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))][-14:]
    gains = sum(max(value, 0) for value in changes) / 14
    losses = sum(max(-value, 0) for value in changes) / 14
    return 100 if losses == 0 else 100 - 100 / (1 + gains / losses)


def strategy(candles):
    rows = sorted(candles or [], key=lambda row: int(row[0]))
    closed_before = int(time.time() * 1000) - 60_000
    rows = [row for row in rows if int(row[0]) < closed_before]
    closes = [number(row[4]) for row in rows if number(row[4]) > 0]
    if len(closes) < 30:
        return []
    fast, slow = ema(closes, 9), ema(closes, 21)
    relative_strength = rsi(closes)
    average_turnover = sum(number(row[6]) for row in rows[-21:-1]) / 20
    last_turnover = number(rows[-1][6])
    signals = []
    if fast and slow and fast > slow and closes[-1] > fast and last_turnover > average_turnover * 1.2:
        signals.append(("ema_volume", "LONG", "EMA9>EMA21, close>EMA9, 1m turnover>1.2x recent mean"))
    if fast and slow and fast < slow and closes[-1] < fast and last_turnover > average_turnover * 1.2:
        signals.append(("ema_volume", "SHORT", "EMA9<EMA21, close<EMA9, 1m turnover>1.2x recent mean"))
    high = max(number(row[2]) for row in rows[-21:-1])
    low = min(number(row[3]) for row in rows[-21:-1])
    if closes[-1] > high and last_turnover > average_turnover * 1.5:
        signals.append(("breakout", "LONG", "20-bar high break with >1.5x turnover"))
    if closes[-1] < low and last_turnover > average_turnover * 1.5:
        signals.append(("breakdown", "SHORT", "20-bar low break with >1.5x turnover"))
    if relative_strength is not None and relative_strength < 25:
        signals.append(("oversold_watch", "LONG", f"RSI14 {relative_strength:.1f}; context only, not entry confirmation"))
    if relative_strength is not None and relative_strength > 75:
        signals.append(("overbought_watch", "SHORT", f"RSI14 {relative_strength:.1f}; context only, not entry confirmation"))
    return signals


def evaluate_candle_streak(symbol, candles):
    """Record up to five separate checks of the latest 60 fully closed 1m candles."""
    rows = []
    cutoff_ms = int(time.time() * 1000) - 60_000
    for row in candles or []:
        try:
            if int(row[0]) + 60_000 <= cutoff_ms:
                rows.append(row)
        except (TypeError, ValueError, IndexError):
            continue
    rows.sort(key=lambda row: int(row[0]))
    rows = rows[-60:]
    if len(rows) < 60:
        return None
    green = sum(number(row[4]) > number(row[1]) for row in rows)
    red = sum(number(row[4]) < number(row[1]) for row in rows)
    doji = 60 - green - red
    dominant = "GREEN" if green >= red else "RED"
    dominant_count = max(green, red)
    return {
        "type": "same_colour_60m_candle_test",
        "at": iso(), "symbol": symbol, "candles_checked": 60,
        "green_candles": green, "red_candles": red, "doji_candles": doji,
        "dominant_colour": dominant, "dominant_count": dominant_count,
        "threshold": 40, "qualifies": dominant_count >= 40,
        "first_candle_timestamp_ms": rows[0][0],
        "last_candle_timestamp_ms": rows[-1][0],
        "meaning": "Research condition only; not a trade instruction."
    }


def analyze_first_hour_trends(symbol, candles, window_start_ms, window_end_ms):
    """Find 60-minute range breakouts and measure candle colours in their first hour.

    A trend start is a fully closed 1m candle closing above the previous 60
    candles' highs (LONG) or below their lows (SHORT). Each event is measured
    over that breakout candle plus the next 59 fully closed 1m candles.
    Events must have a complete, gap-free first hour. This is a transparent
    breakout proxy, not a claim that every market trend starts this way.
    """
    rows_by_time = {}
    for row in candles or []:
        try:
            ts = int(row[0])
            if window_start_ms <= ts and ts + 60_000 <= window_end_ms:
                rows_by_time[ts] = row
        except (TypeError, ValueError, IndexError):
            continue
    rows = [rows_by_time[key] for key in sorted(rows_by_time)]
    events = []
    last_event_index = -60
    for i in range(60, len(rows) - 59):
        first_hour = rows[i:i + 60]
        if len(first_hour) != 60:
            continue
        timestamps = [int(row[0]) for row in first_hour]
        if any(timestamps[j] - timestamps[j - 1] != 60_000 for j in range(1, 60)):
            continue
        if i - last_event_index < 60:
            continue
        previous = rows[i - 60:i]
        previous_high = max(number(row[2]) for row in previous)
        previous_low = min(number(row[3]) for row in previous)
        start_close = number(rows[i][4])
        if start_close > previous_high:
            direction = "LONG"
        elif start_close < previous_low:
            direction = "SHORT"
        else:
            continue

        green = sum(number(row[4]) > number(row[1]) for row in first_hour)
        red = sum(number(row[4]) < number(row[1]) for row in first_hour)
        doji = 60 - green - red
        matching = green if direction == "LONG" else red
        opposing = red if direction == "LONG" else green
        end_close = number(first_hour[-1][4])
        follow_through = (
            (end_close / start_close - 1) * 100 if direction == "LONG" and start_close
            else (start_close / end_close - 1) * 100 if direction == "SHORT" and end_close
            else None
        )
        early_windows = []
        for minutes in (5, 10, 15, 20, 30, 60):
            prefix = first_hour[:minutes]
            window_green = sum(number(row[4]) > number(row[1]) for row in prefix)
            window_red = sum(number(row[4]) < number(row[1]) for row in prefix)
            window_doji = minutes - window_green - window_red
            window_matching = window_green if direction == "LONG" else window_red
            window_close = number(prefix[-1][4])
            remaining = first_hour[minutes:]
            if remaining and window_close > 0 and end_close > 0:
                continuation = (
                    (end_close / window_close - 1) * 100 if direction == "LONG"
                    else (window_close / end_close - 1) * 100
                )
                favorable_values = [
                    ((number(row[2]) / window_close - 1) * 100 if direction == "LONG"
                     else (window_close / number(row[3]) - 1) * 100)
                    for row in remaining
                    if (number(row[2]) > 0 if direction == "LONG" else number(row[3]) > 0)
                ]
                adverse_values = [
                    ((number(row[3]) / window_close - 1) * 100 if direction == "LONG"
                     else (window_close / number(row[2]) - 1) * 100)
                    for row in remaining
                    if (number(row[3]) > 0 if direction == "LONG" else number(row[2]) > 0)
                ]
                max_favorable = max(favorable_values) if favorable_values else None
                max_adverse = min(adverse_values) if adverse_values else None
            else:
                continuation = max_favorable = max_adverse = None
            early_windows.append({
                "minutes": minutes,
                "green_candles": window_green,
                "red_candles": window_red,
                "doji_candles": window_doji,
                "direction_matching_candles": window_matching,
                "direction_matching_pct": round(window_matching / minutes * 100, 2),
                "window_close": window_close,
                "direction_adjusted_continuation_to_hour_end_pct": (
                    round(continuation, 4) if continuation is not None else None
                ),
                "max_favorable_excursion_after_window_pct": (
                    round(max_favorable, 4) if max_favorable is not None else None
                ),
                "max_adverse_excursion_after_window_pct": (
                    round(max_adverse, 4) if max_adverse is not None else None
                ),
                "remaining_candles_after_window": len(remaining),
            })

        events.append({
            "direction": direction,
            "trend_start_timestamp_ms": int(rows[i][0]),
            "first_hour_end_timestamp_ms": int(first_hour[-1][0]),
            "trend_start_close": start_close,
            "first_hour_end_close": end_close,
            "green_candles": green,
            "red_candles": red,
            "doji_candles": doji,
            "direction_matching_candles": matching,
            "direction_opposing_candles": opposing,
            "direction_matching_pct": round(matching / 60 * 100, 2),
            "first_hour_follow_through_pct": round(follow_through, 4) if follow_through is not None else None,
            "candles_in_first_hour": 60,
            "early_window_analysis": early_windows,
        })
        last_event_index = i

    return {
        "type": "first_hour_trend_candle_backtest",
        "symbol": symbol,
        "window_start_ms": window_start_ms,
        "window_end_ms": window_end_ms,
        "candles_available": len(rows),
        "events_found": len(events),
        "long_trends": sum(event["direction"] == "LONG" for event in events),
        "short_trends": sum(event["direction"] == "SHORT" for event in events),
        "events": events,
        "trend_definition": "1m close breaks above prior 60-candle high (LONG) or below prior 60-candle low (SHORT); first hour includes breakout candle plus next 59 closed candles.",
        "caveat": "Breakout-based trend proxy. Describes historical candle behaviour; not a prediction or trading instruction."
    }


async def fetch_first_hour_trend_backtest(session, symbol):
    """Fetch a rolling 24h of 1m candles in two public-data pages."""
    end_ms = (int(time.time() * 1000) // 60_000) * 60_000
    start_ms = end_ms - 24 * 60 * 60 * 1000
    midpoint_ms = start_ms + 12 * 60 * 60 * 1000

    async def page(start, end):
        payload = await get_json(session, "/api/v3/market/candles", {
            "category": CATEGORY, "symbol": symbol, "interval": "1m",
            "startTime": str(start), "endTime": str(end), "limit": "1000"
        })
        return payload.get("data", []) or []

    first, second = await asyncio.gather(
        page(start_ms, midpoint_ms), page(midpoint_ms, end_ms)
    )
    merged = {int(row[0]): row for row in first + second if row and len(row) >= 7}
    result = analyze_first_hour_trends(
        symbol, [merged[key] for key in sorted(merged)], start_ms, end_ms
    )
    result["collected_at_utc"] = iso()
    return result

def watchlist_activity_map():
    watchlist = read(WATCH, {})
    result = {}
    for group_name, rows in (watchlist.get("selected_groups") or watchlist.get("groups") or {}).items():
        for row in rows:
            if row.get("symbol"):
                result[row["symbol"]] = group_name
    return result


async def collect_symbol(session, symbol, ticker, instrument, fee_map, activity_map, state):
    """Fetch one symbol's public market evidence concurrently; never places orders."""
    try:
        book_payload, candle_payload, fills_payload = await asyncio.gather(
            get_json(session, "/api/v3/market/orderbook", {
                "category": CATEGORY, "symbol": symbol, "limit": "100"
            }),
            get_json(session, "/api/v3/market/candles", {
                "category": CATEGORY, "symbol": symbol, "interval": "1m", "limit": "100"
            }),
            get_json(session, "/api/v3/market/fills", {
                "category": CATEGORY, "symbol": symbol, "limit": "100"
            }),
        )
        book = book_payload.get("data", {}) or {}
        asks, bids = book.get("a", []), book.get("b", [])
        bid, ask = number(ticker.get("bid1Price")), number(ticker.get("ask1Price"))
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else number(ticker.get("lastPrice"))
        spread = (ask - bid) / mid * 10000 if mid and ask >= bid else None

        def depth(levels):
            return round(sum(number(price) * number(qty) for price, qty, *_ in levels
                             if mid and abs(number(price) / mid - 1) <= 0.005), 4)

        candle_rows = candle_payload.get("data", []) or []
        seen = set(state.setdefault("candle_ids", []))
        new_candles = []
        for candle in candle_rows:
            candle_id = f"{symbol}:{candle[0]}"
            if candle_id in seen:
                continue
            record = {
                "symbol": symbol, "candle_timestamp_ms": candle[0],
                "open": number(candle[1]), "high": number(candle[2]),
                "low": number(candle[3]), "close": number(candle[4]),
                "base_volume": number(candle[5]), "quote_turnover": number(candle[6]),
                "collected_at_utc": iso(),
            }
            add(C, record)
            new_candles.append(candle_id)
            seen.add(candle_id)
        state["candle_ids"] = list(seen)[-12000:]

        fills = fills_payload.get("data", []) or []
        buy_volume = sum(number(fill.get("size")) for fill in fills if fill.get("side") == "buy")
        sell_volume = sum(number(fill.get("size")) for fill in fills if fill.get("side") == "sell")
        fee_row = fee_map.get(symbol, {})
        fee_raw = fee_row.get("takerFeeRate", instrument.get("takerFeeRate"))
        fee_bps = number(fee_raw, -1) * 10000 if fee_raw is not None else -1
        observation = {
            "at": iso(), "symbol": symbol, "base_coin": instrument.get("baseCoin"),
            "full_name": instrument.get("fullName"),
            "turnover24h_usdt": number(ticker.get("turnover24h")),
            "activity_band": activity_map.get(symbol, "UNCLASSIFIED_BY_TURNOVER"),
            "last": number(ticker.get("lastPrice")), "mark": number(ticker.get("markPrice")),
            "index": number(ticker.get("indexPrice")), "price_change_24h": number(ticker.get("price24hPcnt")),
            "funding_rate": number(ticker.get("fundingRate")),
            "open_interest": number(ticker.get("openInterest")),
            "spread_bps": spread, "depth_0_5pct_bid_usdt": depth(bids),
            "depth_0_5pct_ask_usdt": depth(asks), "orderbook_ts": book.get("ts"),
            "candle_rows_returned": len(candle_rows), "new_candles_saved": len(new_candles),
            "public_fills_count": len(fills), "public_fills_buy_base": buy_volume,
            "public_fills_sell_base": sell_volume,
            "public_fills_buy_sell_ratio": buy_volume / sell_volume if sell_volume else None,
            "taker_fee_bps": fee_bps if fee_bps >= 0 else None,
            "fee_source": "Bitget authenticated account fee-rate" if fee_row else (
                "Bitget instrument metadata" if fee_raw is not None else "UNAVAILABLE"
            ),
        }
        add(O, observation)
        return {"symbol": symbol, "ticker": ticker, "instrument": instrument,
                "book": book, "candles": candle_rows, "mid": mid,
                "spread_bps": spread, "fee_bps": fee_bps, "error": None}
    except Exception as exc:
        add(R / "collection_errors.jsonl", {
            "at": iso(), "symbol": symbol, "error": str(exc)[:350]
        })
        return {"symbol": symbol, "error": str(exc)[:350]}


def record_signals_and_entries(result, state):
    if result.get("error"):
        return 0
    symbol = result["symbol"]
    signals_found = strategy(result["candles"]) if now().timestamp() < state["end_epoch"] else []
    signal_count = 0
    for strategy_name, direction, reason in signals_found:
        candle_id = max((row[0] for row in result["candles"]), key=lambda value: int(value)) if result["candles"] else "no-candle"
        signal_id = f"{symbol}:{strategy_name}:{candle_id}"
        seen = state.setdefault("signal_ids", [])
        if signal_id in seen:
            continue
        seen.append(signal_id)
        state["signal_ids"] = seen[-3000:]
        signal_count += 1
        add(E, {
            "type": "watch_condition" if strategy_name in ("oversold_watch", "overbought_watch") else "signal",
            "id": signal_id, "at": iso(), "symbol": symbol, "strategy": strategy_name,
            "direction": direction, "reason": reason, "reference_price": result["mid"],
            "status": "unverified research hypothesis",
        })
        if strategy_name in ("oversold_watch", "overbought_watch"):
            continue
        fee_bps = result["fee_bps"]
        if fee_bps < 0:
            add(E, {"type": "shadow_entry_not_simulated", "id": signal_id, "at": iso(),
                    "symbol": symbol, "reason": "Bitget taker fee unavailable; refusing to assume zero fees."})
            continue
        entry_side = "buy" if direction == "LONG" else "sell"
        entry_levels = result["book"].get("a" if entry_side == "buy" else "b", [])
        pending = read(Q, [])
        for amount in (100, 500, 1000):
            entry = walk_book(entry_levels, entry_side, quote_target=amount)
            if not entry["complete"]:
                add(E, {"type": "shadow_entry_partial_or_unfilled", "id": signal_id, "at": iso(),
                        "symbol": symbol, "direction": direction, "notional_usdt": amount,
                        "entry_fill": entry, "reason": "Visible entry book could not fill full hypothetical notional."})
                continue
            for horizon in (5, 15, 30):
                pending.append({
                    "id": f"{signal_id}:{amount}:{horizon}", "signal_id": signal_id,
                    "symbol": symbol, "strategy": strategy_name, "direction": direction,
                    "notional_usdt": amount, "entry_base": entry["filled_base"],
                    "entry_quote": entry["filled_quote_usdt"], "entry_vwap": entry["vwap"],
                    "entry_fee_usdt": entry["filled_quote_usdt"] * fee_bps / 10000,
                    "fee_bps": fee_bps, "entry_mid": result["mid"],
                    "entry_spread_bps": result["spread_bps"],
                    "funding_rate_at_entry": number(result["ticker"].get("fundingRate")),
                    "due": now().timestamp() + horizon * 60, "horizon_min": horizon,
                })
        Q.write_text(json.dumps(pending, indent=2), encoding="utf-8")
    return signal_count


async def evaluate_due_exits(session):
    pending = read(Q, [])
    keep = []
    exit_books = {}
    for item in pending:
        if now().timestamp() < item["due"]:
            keep.append(item)
            continue
        try:
            symbol = item["symbol"]
            if symbol not in exit_books:
                payload = await get_json(session, "/api/v3/market/orderbook", {
                    "category": CATEGORY, "symbol": symbol, "limit": "100"
                })
                exit_books[symbol] = payload.get("data", {}) or {}
            book = exit_books[symbol]
            exit_side = "sell" if item["direction"] == "LONG" else "buy"
            levels = book.get("b" if exit_side == "sell" else "a", [])
            exit_fill = walk_book(levels, exit_side, base_target=item["entry_base"])
            if exit_fill["complete"]:
                exit_fee = exit_fill["filled_quote_usdt"] * item["fee_bps"] / 10000
                gross = (
                    exit_fill["filled_quote_usdt"] - item["entry_quote"]
                    if item["direction"] == "LONG"
                    else item["entry_quote"] - exit_fill["filled_quote_usdt"]
                )
                net = gross - item["entry_fee_usdt"] - exit_fee
                best_bid = number(book.get("b", [[0, 0]])[0][0]) if book.get("b") else 0
                best_ask = number(book.get("a", [[0, 0]])[0][0]) if book.get("a") else 0
                exit_mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
                exit_slippage = (
                    (1 - exit_fill["vwap"] / exit_mid) * 10000 if exit_side == "sell"
                    else (exit_fill["vwap"] / exit_mid - 1) * 10000
                ) if exit_mid else None
                entry_slippage = (
                    (item["entry_vwap"] / item["entry_mid"] - 1) * 10000
                    if item["direction"] == "LONG"
                    else (1 - item["entry_vwap"] / item["entry_mid"]) * 10000
                ) if item["entry_mid"] else None
                add(E, {
                    "type": "orderbook_shadow_outcome", "at": iso(), **item,
                    "exit_fill": exit_fill, "exit_book_timestamp": book.get("ts"),
                    "exit_fee_usdt": exit_fee, "gross_pnl_usdt": gross,
                    "net_after_trading_fees_usdt": net,
                    "entry_slippage_bps": entry_slippage, "exit_slippage_bps": exit_slippage,
                    "funding_included": False,
                    "funding_rate_at_entry_context_only": item.get("funding_rate_at_entry"),
                    "caveat": "Two-snapshot visible-book estimate; no queue, latency or hidden depth; funding excluded.",
                })
            elif now().timestamp() < item["due"] + 600:
                keep.append(item)
            else:
                add(E, {"type": "evaluation_unavailable", "at": iso(), **item,
                        "exit_fill": exit_fill,
                        "note": "Visible exit book could not close the full hypothetical quantity within 10 minutes."})
        except Exception as exc:
            if now().timestamp() < item["due"] + 600:
                keep.append(item)
            else:
                add(E, {"type": "evaluation_unavailable", "at": iso(), **item,
                        "note": "Exit-book retrieval failed: " + str(exc)[:250]})
    Q.write_text(json.dumps(keep, indent=2), encoding="utf-8")


async def collect():
    state = read(S, {})
    if not state.get("active"):
        print("No active research session")
        return
    if now().timestamp() >= state.get("settle_epoch", state.get("end_epoch", 0)):
        state["active"] = False
        state["ended_at_utc"] = iso()
        S.write_text(json.dumps(state, indent=2), encoding="utf-8")
        SUMMARY.write_text(
            "# 24-Hour Bitget Futures Research\n\n"
            + json.dumps(state, indent=2)
            + "\n\n## Evidence cautions\n"
            "Activity groups are based on Bitget 24h futures turnover, not market cap. "
            "Signals are hypotheses. Shadow fills are visible-book estimates, not executable fills. "
            "Funding is recorded as context but excluded from short-horizon P&L. "
            "GitHub scheduled runs are best-effort, not continuous monitoring. No orders were submitted.\n",
            encoding="utf-8",
        )
        print("Research session ended")
        return

    R.mkdir(parents=True, exist_ok=True)
    new_posts = 0
    post_errors = 0
    symbol_errors = 0
    signal_count = 0
    errors = []
    state["last_cycle_started_at_utc"] = iso()
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        fee_map, auth_status = await load_private_fee_rates(session)
        state["bitget_auth_status"] = auth_status
        try:
            instruments_payload, tickers_payload = await asyncio.gather(
                get_json(session, "/api/v3/market/instruments", {"category": CATEGORY}),
                get_json(session, "/api/v3/market/tickers", {"category": CATEGORY}),
            )
            instruments = {
                row["symbol"]: row for row in instruments_payload.get("data", [])
                if row.get("symbol") and row.get("status") == "online"
                and (row.get("type") == "perpetual" or row.get("instrumentType") == "perpetual")
                and row.get("symbolType", "crypto") == "crypto"
            }
            tickers = {
                row["symbol"]: row for row in tickers_payload.get("data", [])
                if row.get("symbol") in instruments
            }
            activity_map = watchlist_activity_map()
            ranked = sorted(
                tickers.values(),
                key=lambda row: number(row.get("turnover24h")),
                reverse=True,
            )
            # Scan up to 200 online USDT perpetuals, ranked by live 24h
            # futures turnover. Keep the four-band watchlist as labels/context;
            # it must not restrict the research universe to its small shortlist.
            selected_symbols = [row["symbol"] for row in ranked[:MAX_SYMBOLS]]
            semaphore = asyncio.Semaphore(SYMBOL_CONCURRENCY)

            async def bounded(symbol):
                async with semaphore:
                    return await collect_symbol(
                        session, symbol, tickers[symbol], instruments[symbol],
                        fee_map, activity_map, state
                    )

            results = await asyncio.gather(*(bounded(symbol) for symbol in selected_symbols))

            # Historical first-hour trend experiment: run once per symbol per
            # research session, using a rolling 24h of public 1m candles.
            completed_backtests = set(state.setdefault("trend_backtest_symbols_completed", []))
            pending_backtests = [symbol for symbol in selected_symbols if symbol not in completed_backtests]
            backtest_semaphore = asyncio.Semaphore(SYMBOL_CONCURRENCY)

            async def bounded_backtest(symbol):
                async with backtest_semaphore:
                    try:
                        return await fetch_first_hour_trend_backtest(session, symbol)
                    except Exception as exc:
                        add(R / "collection_errors.jsonl", {
                            "at": iso(), "symbol": symbol,
                            "source": "first_hour_trend_backtest", "error": str(exc)[:350]
                        })
                        return None

            backtest_results = await asyncio.gather(
                *(bounded_backtest(symbol) for symbol in pending_backtests)
            )
            for backtest in backtest_results:
                if backtest is not None:
                    add(R / "trend_first_hour_backtest.jsonl", backtest)
                    completed_backtests.add(backtest["symbol"])
            state["trend_backtest_symbols_completed"] = sorted(completed_backtests)
            state["trend_backtest_symbols_this_cycle"] = sum(x is not None for x in backtest_results)
            state["trend_backtest_events_this_cycle"] = sum(
                backtest.get("events_found", 0) for backtest in backtest_results if backtest is not None
            )

            # Separate early-window experiment: recalculate all symbols once into
            # its own file so legacy first-hour records remain untouched.
            early_completed = set(state.setdefault("trend_early_window_symbols_completed", []))
            early_pending = [symbol for symbol in selected_symbols if symbol not in early_completed]
            same_cycle_backtests = {
                item["symbol"]: item for item in backtest_results if item is not None
            }
            async def bounded_early_backtest(symbol):
                if symbol in same_cycle_backtests:
                    return same_cycle_backtests[symbol]
                async with backtest_semaphore:
                    try:
                        return await fetch_first_hour_trend_backtest(session, symbol)
                    except Exception as exc:
                        add(R / "collection_errors.jsonl", {
                            "at": iso(), "symbol": symbol,
                            "source": "early_window_trend_backtest", "error": str(exc)[:350]
                        })
                        return None
            early_results = await asyncio.gather(
                *(bounded_early_backtest(symbol) for symbol in early_pending)
            )
            for backtest in early_results:
                if backtest is not None:
                    add(T, backtest)
                    early_completed.add(backtest["symbol"])
            state["trend_early_window_symbols_completed"] = sorted(early_completed)
            state["trend_early_window_symbols_this_cycle"] = sum(
                item is not None for item in early_results
            )
            state["trend_early_window_events_this_cycle"] = sum(
                item.get("events_found", 0) for item in early_results if item is not None
            )

            symbol_errors = sum(1 for result in results if result.get("error"))
            signal_count = sum(record_signals_and_entries(result, state) for result in results)

            # Mandatory experiment: test each symbol up to five separate times.
            # Persist per-symbol counts so scheduled runs do not reset them.
            check_counts = state.setdefault("candle_streak_checks_by_symbol", {})
            checks_this_cycle = 0
            qualified_this_cycle = 0
            for result in results:
                if result.get("error") or check_counts.get(result["symbol"], 0) >= 5:
                    continue
                check = evaluate_candle_streak(result["symbol"], result.get("candles", []))
                if check is None:
                    continue
                add(F, check)
                check_counts[result["symbol"]] = check_counts.get(result["symbol"], 0) + 1
                checks_this_cycle += 1
                qualified_this_cycle += int(check["qualifies"])
            state["candle_streak_checks_total"] = state.get("candle_streak_checks_total", 0) + checks_this_cycle
            state["candle_streak_qualifications_total"] = state.get("candle_streak_qualifications_total", 0) + qualified_this_cycle
            state["candle_streak_checks_this_cycle"] = checks_this_cycle
            state["candle_streak_qualifications_this_cycle"] = qualified_this_cycle
            await evaluate_due_exits(session)
            if state.get("cycles", 0) % 3 == 0 and now().timestamp() < state["end_epoch"]:
                new_posts, post_errors = await collect_public_posts(session)
        except Exception as exc:
            errors.append(str(exc)[:500])
            add(R / "collection_errors.jsonl", {"at": iso(), "error": str(exc)[:500]})

    state["cycles"] = state.get("cycles", 0) + 1
    state["last_at"] = iso()
    state["signals"] = state.get("signals", 0) + signal_count
    state["posts"] = state.get("posts", 0) + new_posts
    state["errors"] = state.get("errors", 0) + len(errors) + symbol_errors + post_errors
    state["symbol_errors"] = state.get("symbol_errors", 0) + symbol_errors
    state["feed_errors"] = state.get("feed_errors", 0) + post_errors
    state["symbols_last_cycle"] = len(selected_symbols) if "selected_symbols" in locals() else 0
    S.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps({
        "cycle": state["cycles"], "symbols": state["symbols_last_cycle"],
        "signals": signal_count, "new_posts": new_posts, "errors": len(errors) + symbol_errors + post_errors,
        "bitget_auth_status": auth_status,
        "candle_streak_checks_this_cycle": state.get("candle_streak_checks_this_cycle", 0),
        "candle_streak_qualifications_this_cycle": state.get("candle_streak_qualifications_this_cycle", 0),
        "candle_streak_checks_total": state.get("candle_streak_checks_total", 0),
        "trend_backtest_symbols_this_cycle": state.get("trend_backtest_symbols_this_cycle", 0),
        "trend_backtest_symbols_completed": len(state.get("trend_backtest_symbols_completed", [])),
        "trend_backtest_events_this_cycle": state.get("trend_backtest_events_this_cycle", 0),
        "trend_early_window_symbols_this_cycle": state.get("trend_early_window_symbols_this_cycle", 0),
        "trend_early_window_symbols_completed": len(state.get("trend_early_window_symbols_completed", [])),
        "trend_early_window_events_this_cycle": state.get("trend_early_window_events_this_cycle", 0),
        "ends": state.get("ends_at_utc"),
    }))


async def collect_public_posts(session):
    known = set()
    if P.exists():
        for line in P.read_text(encoding="utf-8").splitlines():
            try:
                known.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    count = 0
    error_count = 0
    for feed in FEEDS:
        try:
            async with session.get(feed, timeout=15) as response:
                response.raise_for_status()
                raw = await response.text()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw)
            entries = root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry")
            for entry in entries[:25]:
                def value(key):
                    element = entry.find(key)
                    if element is None:
                        element = entry.find("{http://www.w3.org/2005/Atom}" + key)
                    if element is None:
                        return ""
                    if key == "link" and element.get("href"):
                        return element.get("href")
                    return (element.text or "").strip()
                title, link = value("title"), value("link")
                identity = hashlib.sha256((link or title).encode()).hexdigest()
                if not title or identity in known:
                    continue
                add(P, {
                    "id": identity, "source": feed, "title": title[:500],
                    "url": link, "published": value("pubDate") or value("published"),
                    "summary": (value("description") or value("summary"))[:2500],
                    "collected_at_utc": iso(),
                    "classification": "UNVERIFIED_PUBLIC_CLAIM_OR_COMMENTARY",
                    "verification": "No proof of identity, actual fills or profitable track record.",
                })
                known.add(identity)
                count += 1
        except Exception as exc:
            error_count += 1
            add(R / "collection_errors.jsonl", {
                "at": iso(), "feed": feed, "error": str(exc)[:300]
            })
    return count, error_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "collect", "status", "stop"])
    action = parser.parse_args().action
    if action == "start":
        R.mkdir(parents=True, exist_ok=True)
        existing = read(S, {})
        if existing.get("active") and now().timestamp() < existing.get("settle_epoch", existing.get("end_epoch", 0)):
            raise SystemExit("A research session is already active; inspect it with status.")
        end = now().timestamp() + 86400
        settle = end + 1800
        state = {
            "active": True, "started_at_utc": iso(), "end_epoch": end,
            "ends_at_utc": datetime.fromtimestamp(end, timezone.utc).isoformat(),
            "settle_epoch": settle,
            "settle_until_utc": datetime.fromtimestamp(settle, timezone.utc).isoformat(),
            "cycles": 0, "signals": 0, "posts": 0, "errors": 0, "signal_ids": [],
            "candle_ids": [], "bitget_auth_status": "NOT_CHECKED",
            "data_source": "Bitget USDT-FUTURES",
            "trading_enabled": False,
        }
        S.write_text(json.dumps(state, indent=2), encoding="utf-8")
        Q.write_text("[]", encoding="utf-8")
        print("Started 24-hour Bitget read-only research until " + state["ends_at_utc"])
    elif action == "collect":
        asyncio.run(collect())
    elif action == "stop":
        R.mkdir(parents=True, exist_ok=True)
        state = read(S, {"active": False})
        state["active"] = False
        state["stopped_at_utc"] = iso()
        S.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print("Research collection stopped; existing records preserved.")
    else:
        print(json.dumps(read(S, {"active": False}), indent=2))


if __name__ == "__main__":
    main()
