from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_EXCHANGES = (
    "binance", "bybit", "okx", "bitget", "hyperliquid", "kucoin", "coinbase", "bingx",
)

DEFAULT_RPS = {
    "binance": 10, "bybit": 8, "okx": 8, "bitget": 8,
    "hyperliquid": 4, "kucoin": 6, "coinbase": 5, "bingx": 5,
}

ORDERBOOK_LIMITS = {
    "binance": 100, "bybit": 200, "okx": 100, "bitget": 100,
    "kucoin": 100, "bingx": 100, "hyperliquid": None, "coinbase": None,
}

QUOTES = ("USDT", "USDC", "USD")
STABLES = {
    "USDT", "USDC", "USD", "DAI", "TUSD", "FDUSD", "USDE", "PYUSD", "BUSD", "USDD",
    "EUR", "GBP", "USDS", "USD1",
}

def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default

@dataclass(frozen=True)
class Config:
    exchanges: tuple = DEFAULT_EXCHANGES
    exec_exchange: str = "bitget"         
    sandbox: bool = False
    live_enabled: bool = False            

    min_agg_volume_usd: float = 1_000_000
    max_scan_coins: int = 800
    depth_pct: float = 0.01
    min_book_usd: float = 25_000
    min_venues: int = 2
    top_n: int = 10
    scan_concurrency: int = 60
    scan_interval_s: float = 60
    scan_max_age_s: float = 600
    prefilter_keep: int = 60

    rps: dict = field(default_factory=lambda: dict(DEFAULT_RPS))
    scan_budget_fraction: float = 0.7
    request_timeout_s: float = 12

    candle_minutes: int = 10
    history_candles: int = 1000
    min_history: int = 150
    backtest_trades: int = 10
    min_backtest_trades: int = 3
    require_positive_backtest: bool = True
    proxy_window: int = 5

    fee_round_trip: float = 0.0012
    stop_loss: float = 0.015
    max_trade_seconds: int = 600
    monitor_interval_s: float = 1.0
    max_price_failures: int = 10
    close_retries: int = 5
    gate_wins: int = 8
    gate_min_net: float = 0.0042
    position_usd: float = 1.50            
    leverage: int = 5                     

    summary_interval_s: float = 600
    gate_path: str = "state/gate.json"
    trades_path: str = "state/trades.jsonl"

    @staticmethod
    def from_env() -> "Config":
        return Config(
            exec_exchange=os.getenv("EXEC_EXCHANGE", "bitget"),
            sandbox=os.getenv("EXEC_SANDBOX", "0") == "1",
            live_enabled=os.getenv("LIVE_TRADING", "") == "YES",
            position_usd=_f("POSITION_USD", 1.50),
            leverage=int(_f("LEVERAGE", 5)),
        )

def credentials(eid: str) -> dict:
    up = eid.upper()
    if eid == "hyperliquid":
        return {
            "walletAddress": os.getenv("HYPERLIQUID_WALLET", ""),
            "privateKey": os.getenv("HYPERLIQUID_PRIVATE_KEY", ""),
        }
    creds = {"apiKey": os.getenv(f"{up}_API_KEY", ""), "secret": os.getenv(f"{up}_SECRET", "")}
    pw = os.getenv(f"{up}_PASSWORD") or os.getenv(f"{up}_PASSPHRASE")
    if pw:
        creds["password"] = pw
    return creds

def has_credentials(eid: str) -> bool:
    c = credentials(eid)
    if eid == "hyperliquid":
        return bool(c["walletAddress"] and c["privateKey"])
    return bool(c["apiKey"] and c["secret"])
