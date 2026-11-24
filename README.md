# Bitget Futures Market Research (Read Only)

This repository is a **Bitget-first, research-only market observer**. It reads Bitget USDT perpetual market data and, when configured, uses a Bitget API key for authenticated account-specific fee metadata. It never submits, amends or cancels orders and never changes leverage, margin mode or positions.

## Important distinction: market cap versus Bitget turnover

Bitget's USDT-futures instruments and ticker endpoints provide contract metadata, prices, 24-hour turnover, funding, open interest and order-book data. They do **not** provide circulating market capitalisation. The project therefore removed CoinGecko from the runtime watchlist and now labels the four groups as **Bitget 24-hour futures-turnover activity bands**, not market-cap bands:

- Under $1m 24h futures turnover
- $1m–$10m
- $10m–$100m
- $100m+

The watchlist selects up to 50 contracts per activity band (up to 200 total). Each five-minute research cycle scans up to 200 online USDT perpetual contracts ranked by Bitget-reported 24-hour futures turnover. These are activity groups, not a substitute for the earlier market-cap grouping. Do not infer a coin's market cap from its ticker or trading volume.

## Configure the Bitget API key safely

In GitHub, open **Settings → Secrets and variables → Actions → New repository secret** and create:

- `BITGET_API_KEY`
- `BITGET_API_SECRET`
- `BITGET_API_PASSPHRASE`

Use a dedicated Bitget API key with **Read-only** permission, no Trade, Transfer or Withdraw permissions, and an IP whitelist where practical. Do not paste keys into source code, issues, workflow logs or chat.

The workflow uses the credentials only for signed GET requests to:
- `/api/v3/account/info` — read the key's permission type.
- `/api/v3/account/all-fee-rate?category=USDT-FUTURES` — retrieve your account-specific futures fee schedule.

If credentials are absent or the fee endpoint is not permitted, public Bitget market research continues and the session records the authentication/fee lookup status. Missing fees are never silently treated as zero. Public market endpoints do not require API credentials; Bitget requires signed credentials for private account-specific information.

## Hands-off research app

The research worker starts itself when the workflow is first deployed and whenever no active 24-hour session remains. You do not need to ping it or manually start a session. GitHub Actions attempts a new Bitget-only collection cycle every five minutes, keeps the session and evidence in the repository, and writes a machine-readable status snapshot after each report build.

The main collector now fails visibly when a collection fails or does not advance the recorded cycle count. A separate staggered GitHub Actions watchdog checks the committed heartbeat between collector slots and dispatches a recovery collection only when the heartbeat is stale/failed and no collector run is queued or running. Both schedules remain subject to GitHub Actions availability; the watchdog is a fallback, not a guarantee during a platform-wide scheduler outage.

When you return, open the latest report and status snapshot below, or simply ask ChatGPT to inspect this repository:
- `reports/daily_research/daily_research_summary.md` — readable research findings.
- `reports/daily_research/research_status.json` — machine-readable health, progress and result summary.
- `reports/daily_research/session.json` — session state and last collection timestamp.

## What gets recorded

- Online Bitget USDT perpetual contracts, instrument metadata and 24-hour futures turnover.
- Latest/mark/index prices, 24-hour change, funding rate and open interest.
- One-minute candles, 100-level visible order books, spread and depth within 0.5% of mid.
- Per-cycle trend-ignition radar for every scanned coin: 5/10/15/20/30/60-minute candle colour and price movement, candle-body/structure checks, volume acceleration, and Bitget 5-minute historical open-interest changes.
- Ranked LONG/SHORT early-pressure candidates in `reports/daily_research/daily_research_summary.md` and raw per-cycle evidence in `trend_ignition.jsonl`.
- Recent public Bitget fills, buy/sell volume and order-book timestamps.
- Account-specific taker fees from the signed read-only fee endpoint when available.
- Rule-based LONG/SHORT research hypotheses and hypothetical $100/$500/$1,000 order-book entries.
- Fresh hypothetical exit-book walks at 5, 15 and 30 minutes, with VWAP, partial-fill status, slippage and estimated fees.
- API/feed errors and missing/unavailable observations.

The shadow simulator is mathematical only. It does not send orders to Bitget. Its visible-book results are estimates, not guaranteed fills; funding is recorded as context but is not currently included in short-horizon simulated P&L.

## Bitget-only data policy

The live collector requests market and (optionally) account fee data from Bitget only. It does not contact Reddit, CoinDesk, Cointelegraph, news sites or social-media feeds. Old `public_trader_posts.jsonl` records, if present, are legacy history only and are not read or updated by the collector.

## Results and persistence

When the session completes, the workflow uploads one artifact named similar to `bitget-24-hour-futures-research-...`. Download it from the completed Actions run under **Summary → Artifacts**. The ZIP includes the original JSONL evidence, CSV exports for spreadsheet analysis, the Markdown report, a package manifest with record counts, and the watchlist. The main CSVs are `market_observations.csv`, `candles_1m.csv`, and `shadow_experiments.csv`. Durable raw records are also committed under:

- `reports/daily_research/market_observations.jsonl`
- `reports/daily_research/candles_1m.jsonl`
- `reports/daily_research/shadow_experiments.jsonl`
- `reports/daily_research/collection_errors.jsonl`
- `reports/daily_research/session.json`
- `reports/daily_research/daily_research_summary.md`
- `reports/market_cap_watchlist/current_watchlist.json` and `current_watchlist.md`

## Limitations

GitHub's five-minute schedule is best-effort; runs may be delayed or skipped. Check actual timestamps and cycle counts. Visible-book simulations cannot reproduce queue priority, hidden liquidity, latency or market movement after the snapshot. A 24-hour sample cannot prove a durable profitable edge.

## Project files

- `daily_research.py` — read-only Bitget collector and signed account-fee lookup.
- `trend_ignition.py` — transparent candle/volume/open-interest trend-development scoring.
- `cap_watchlist.py` — Bitget-only futures-turnover activity watchlist.
- `shadow_execution.py` — pure order-book fill, slippage and fee calculations.
- `research_report.py` — profit/loss and evidence summaries.
- `tests/` — activity-band, authentication and no-order safety tests.
- `archive/legacy_trade_history.json` — retained historical records, not used by the collector.
- `docs/PROJECT_KNOWLEDGE_BASE.md` — dated project decisions and lessons.
- `docs/RESEARCH_RUNBOOK.md` — operating instructions.

## Validation

Python 3.11 or newer:

```bash
python -m pip install -r requirements.txt
python -m py_compile daily_research.py shadow_execution.py research_report.py cap_watchlist.py trend_ignition.py
python -m unittest discover -s tests -v
```
