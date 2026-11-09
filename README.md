# Bitget/MEXC Trading Bot — Honest Edition

Two independent paper strategies running side by side:
1. **OFI strategy** (`body.py` + `brain.py` + `lead_lag.py`) — short burst continuations
2. **Scanner strategy** (`scanner.py`) — multi-timeframe momentum + exhaustion, every 10 min

Both are **paper-only** until their respective gate passes.

## File Map

| File | Purpose |
|---|---|
| `setup_orchestrator.py` | FastAPI entrypoint, config contract, SQLite ledger, 4h volume aggregation |
| `brain.py` | Pure OFI decision logic |
| `lead_lag.py` | Cross-exchange gap detector |
| `body.py` | WebSocket executor + MARKET_STATE (incl. trade_buffer) |
| `scanner.py` | Multi-TF momentum scanner, 8-win streak gate |
| `learner.py` | Patient 7-day learning loop, 6 gates, daily reports |
| `test_harness.py` | 20 pure-function startup tests |
| `live_runner.py` | OFI live entrypoint (requires learner stamp) |
| `scanner_live.py` | Scanner live entrypoint (requires 8-win stamp) |
| `best_params.json` | OFI parameters (learner overwrites with stamp) |
| `render.yaml` | Render Blueprint |
| `requirements.txt` | Dependencies |

## Two Gates, Two Strategies

### OFI Strategy Gate
- 7 days minimum collection
- 100 resolved observations
- Top combo: ≥30 trades, ≥40% win rate, positive expectancy
- Confirmed across ≥2 daily reports
- `learner.py` writes `best_params.json` with `_validation` stamp when all pass
- `live_runner.py` refuses live without stamp

### Scanner Strategy Gate
- 8 **consecutive wins** (`move_pct >= 0.42%`)
- `scanner.py` writes `scanner_validation.json` when streak hits 8
- `scanner_live.py` refuses live without stamp
- **Warning:** At 50% win rate, 8 in a row takes ~256 trades. At 45%, ~600 trades. Watch `/scanner/streak` — if the streak never exceeds 4 after 30 trades, the strategy is not working.

## Scanner Endpoints

| Endpoint | What it returns |
|---|---|
| `GET /scanner` | Full state: last scan, position, streak, top 5 |
| `GET /scanner/streak` | Just the win streak and unlock progress |
| `GET /scanner/scans` | Last 6 scans (1 hour of coverage) |
| `GET /scanner/trades` | All closed scanner trades |
| `POST /scanner/force_scan` | Trigger a scan on next tick |

## What You See Every 10 Minutes

In Render logs, one line per scan:
