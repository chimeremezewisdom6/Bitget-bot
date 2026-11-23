# Bitget-First Read-Only Futures Research Runbook

## Safety boundary

The research collector reads Bitget USDT perpetual market data and may use a dedicated Bitget API key for signed, read-only account-fee metadata. It does not submit, amend or cancel orders; change leverage or margin mode; or read balances/positions.

Use a dedicated API key with **Read-only** permission and no Trade, Transfer or Withdraw permissions. Do not store credentials in source files.

## Configure credentials

Create these GitHub repository Actions secrets:

- `BITGET_API_KEY`
- `BITGET_API_SECRET`
- `BITGET_API_PASSPHRASE`

The collector uses them only for signed GET requests to `/api/v3/account/info` and `/api/v3/account/all-fee-rate?category=USDT-FUTURES`. These provide permission-type and account-specific taker-fee metadata. If credentials are missing or the endpoint permission is unavailable, public market collection continues and the session records the fee lookup status. Missing fees are not assumed to be zero.

## Market grouping

Bitget's futures instruments/tickers do not expose circulating market capitalisation. CoinGecko is not used by the runtime watchlist. Instead, the watchlist transparently groups contracts by Bitget 24-hour USDT futures turnover:

- Under $1m
- $1m–$10m
- $10m–$100m
- $100m+

These are **turnover activity groups, not market-cap groups**. Up to three contracts are selected per group; empty groups remain empty.

## Start the single observation workflow

1. Open [24-Hour Futures Research (Read Only)](https://github.com/chimeremezewisdom6/Bitget-bot/actions/workflows/daily-futures-research.yml).
2. Select **Run workflow** on branch `main`.
3. Choose action **start** and dispatch once.
4. The workflow builds the Bitget-only turnover watchlist, starts the 24-hour session and commits the initial state.
5. Confirm the initial Actions run succeeds. Scheduled runs then attempt one collection cycle every five minutes.

No separate watchlist workflow or snapshot workflow is required.

## What the collector records

- Eligible online Bitget USDT perpetual contracts, contract metadata and 24-hour futures turnover.
- Prices, 24-hour price change, mark/index prices, funding/open-interest context.
- One-minute candles, 100-level order books, spread and visible depth within 0.5% of mid.
- Recent public Bitget fills and buy/sell base-volume context.
- Account-specific taker fee when the authenticated read-only endpoint is available.
- Deduplicated public RSS commentary approximately every 15 minutes. These are unverified posts, not verified trader fills or audited track records.
- Rule-based signal hypotheses and hypothetical $100, $500 and $1,000 entries by walking the visible order book.
- Fresh exit-book walks at 5, 15 and 30 minutes for the exact hypothetical base quantity, including VWAP, slippage, gross P&L and fee-adjusted P&L.
- Collection errors and missing data.

Funding is recorded as context but excluded from automatic short-horizon net P&L. A visible-book walk is not a guaranteed fill.

## Inspect or stop

Choose action **status** to inspect the current session. Choose **stop** to stop early, preserve collected records, rebuild the report and upload the package.

The session stops creating new signals after 24 hours and allows up to 30 minutes for pending 30-minute hypothetical exits. GitHub schedule execution is best-effort, not guaranteed.

## Download results

Open the completed GitHub Actions run and download the `bitget-24-hour-futures-research-...` artifact from **Artifacts**. The same records are committed under `reports/daily_research/`; the activity watchlist is under `reports/market_cap_watchlist/`.

Key files include `session.json`, `market_observations.jsonl`, `candles_1m.jsonl`, `public_trader_posts.jsonl`, `shadow_experiments.jsonl`, `collection_errors.jsonl` and `daily_research_summary.md`.

## Interpretation rules

- Two-snapshot order-book simulations cannot know queue position, hidden liquidity, latency or intervening book changes.
- Funding is not included in automatic P&L.
- Public trader commentary is unverified; do not assume authors actually traded.
- Turnover groups are not market-cap groups.
- GitHub scheduled runs can be delayed or skipped. Use actual timestamps and cycle counts.
- Repeated sizes and horizons from the same signal are correlated, not independent trades.
- A positive day or small sample does not prove a durable edge. Require larger samples, out-of-sample tests, multiple regimes and full costs.

## After the experiment

Upload the downloaded ZIP in this chat. Analyse outcomes, fees, slippage, adverse movement, unavailable fills, market conditions and trader commentary. Separate measured observations from assumptions and public claims. Only after this review should a future trading scanner be considered.
