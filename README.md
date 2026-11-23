# Bitget Futures Market Research (Read Only)

This repository is a **Bitget-first, research-only market observer**. It reads Bitget USDT perpetual market data and, when configured, uses a Bitget API key for authenticated account-specific fee metadata. It never submits, amends or cancels orders and never changes leverage, margin mode or positions.

## Important distinction: market cap versus Bitget turnover

Bitget's USDT-futures instruments and ticker endpoints provide contract metadata, prices, 24-hour turnover, funding, open interest and order-book data. They do **not** provide circulating market capitalisation. The project therefore removed CoinGecko from the runtime watchlist and now labels the four groups as **Bitget 24-hour futures-turnover activity bands**, not market-cap bands:

- Under $1m 24h futures turnover
- $1m–$10m
- $10m–$100m
- $100m+

The watchlist selects up to three contracts per activity band. These are activity groups, not a substitute for the earlier market-cap grouping. Do not infer a coin's market cap from its ticker or trading volume.

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

## Start the 24-hour experiment

1. Open [Actions → 24-Hour Futures Research (Read Only)](https://github.com/chimeremezewisdom6/Bitget-bot/actions/workflows/daily-futures-research.yml).
2. Choose **Run workflow**, select branch `main`, and choose action **start**.
3. The workflow builds the Bitget-only turnover watchlist and starts the observation session.
4. GitHub Actions attempts a collection cycle every five minutes for 24 hours, with a 30-minute settlement window for pending hypothetical exits.
5. Use action **status** to inspect progress. Use **stop** to end early and preserve the data.

Only start one session at a time. A second start is rejected while the current session or its settlement grace period is active.

## What gets recorded

- Online Bitget USDT perpetual contracts, instrument metadata and 24-hour futures turnover.
- Latest/mark/index prices, 24-hour change, funding rate and open interest.
- One-minute candles, 100-level visible order books, spread and depth within 0.5% of mid.
- Recent public Bitget fills, buy/sell volume and order-book timestamps.
- Account-specific taker fees from the signed read-only fee endpoint when available.
- Public RSS trader/community commentary, deduplicated and labelled unverified.
- Rule-based LONG/SHORT research hypotheses and hypothetical $100/$500/$1,000 order-book entries.
- Fresh hypothetical exit-book walks at 5, 15 and 30 minutes, with VWAP, partial-fill status, slippage and estimated fees.
- API/feed errors and missing/unavailable observations.

The shadow simulator is mathematical only. It does not send orders to Bitget. Its visible-book results are estimates, not guaranteed fills; funding is recorded as context but is not currently included in short-horizon simulated P&L.

## Results and persistence

When the session completes, the workflow uploads an artifact named similar to `bitget-24-hour-futures-research-...`. Open the completed Actions run and download it from **Artifacts**. Durable records are also committed under:

- `reports/daily_research/market_observations.jsonl`
- `reports/daily_research/candles_1m.jsonl`
- `reports/daily_research/public_trader_posts.jsonl`
- `reports/daily_research/shadow_experiments.jsonl`
- `reports/daily_research/collection_errors.jsonl`
- `reports/daily_research/session.json`
- `reports/daily_research/daily_research_summary.md`
- `reports/market_cap_watchlist/current_watchlist.json` and `current_watchlist.md`

## Limitations

GitHub's five-minute schedule is best-effort; runs may be delayed or skipped. Check actual timestamps and cycle counts. Public posts are not authenticated trader histories or proof of fills. Visible-book simulations cannot reproduce queue priority, hidden liquidity, latency or market movement after the snapshot. A 24-hour sample cannot prove a durable profitable edge.

## Project files

- `daily_research.py` — read-only Bitget collector and signed account-fee lookup.
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
python -m py_compile daily_research.py shadow_execution.py research_report.py cap_watchlist.py
python -m unittest discover -s tests -v
```
