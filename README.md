# Bitget Demo Scanner

A Python scanner for Bitget USDT-margined futures. The repository is deliberately locked to **Bitget Demo trading**.

## Project knowledge and research history

Read [docs/PROJECT_KNOWLEDGE_BASE.md](docs/PROJECT_KNOWLEDGE_BASE.md) for the dated project history, verified engineering findings, strategy parameters, test coverage, known failures, shadow-trading research protocol, and experiment log. Update that file whenever a meaningful test, finding, strategy decision, or limitation changes.

**Current user instruction (2026-11-23): observation-only research.** Do not place Live or Demo orders. The scanner remains order-capable in Demo mode; keep automated trading paused and do not run it with `BOT_DRY_RUN=false`.

## Safety status

- `scanner.py` hard-locks `BITGET_DEMO_MODE = True`; an environment variable cannot switch it to live trading.
- Demo authenticated requests include Bitget's required `paptrading: 1` header.
- `BOT_DRY_RUN=true` performs a read-only scan and must not change leverage or submit orders.
- The automated scanner workflow is intentionally paused. Do not remove its safety condition until a supervised Demo test has verified account access, order placement, fill confirmation, position monitoring, and reduce-only closing—and only after explicit authorization. The current instruction is no Demo or Live trading.
- Passing unit tests is not proof that the exchange connection or a real Demo order lifecycle works.

## Repository layout

| Path | Purpose |
| --- | --- |
| `scanner.py` | Market scanning, account checks, Demo order handling, position supervision and exits |
| `requirements.txt` | Python dependencies |
| `tests/test_scanner_safety.py` | Strategy, sizing, price-rounding and dry-run safety tests |
| `.github/workflows/validate.yml` | Compile and run unit tests on pushes and manual dispatch |
| `.github/workflows/demo-smoke-test.yml` | Manual, read-only Bitget Demo account/market smoke test |
| `.github/workflows/scanner.yml` | Deliberately paused automated scanner workflow |
| `live_active_trade.json` | Persistent local state for the currently supervised Demo position |
| `live_streak.json` | Persistent Demo win-streak state |
| `archive/legacy_trade_history.json` | Historical records retained for reference; not read by the current scanner |

Runtime-generated files such as decision logs and live trade history are not source code. Do not commit API credentials or private keys.

## GitHub Actions secrets

For the historical manual Demo smoke test, the workflow reads these repository Actions secrets using a **Bitget Demo API key**, never a live-trading key:

- `BITGET_API_KEY`
- `BITGET_SECRET_KEY`
- `BITGET_PASSPHRASE`

The smoke-test workflow sets `BOT_DRY_RUN=true` and `CONTINUOUS_247_LOOP=false`. It checks the account and market data without placing orders. Configure one API key set for the intended Demo account. If extra key sets are present, the scanner deliberately uses only the first so balance, positions, entries and exits cannot accidentally target different accounts.

## Local validation

Use Python 3.11 or newer:

```bash
python -m pip install -r requirements.txt
python -m py_compile scanner.py
python -m unittest discover -s tests -v
```

## Before enabling automated Demo trading

Trading is currently prohibited by the user's observation-only instruction. Do not enable it. The following historical checklist is retained for engineering context only:

1. Confirm credentials are a Bitget Demo API key with the required permissions.
2. Run the manual read-only smoke test and inspect its logs.
3. Verify account mode, available Demo balance, instrument rules and open positions.
4. Test a supervised Demo entry, confirmed fill, stop-loss, and reduce-only close.
5. Confirm position state survives workflow restarts. GitHub-hosted runners are ephemeral; state persistence must be deliberately implemented and tested before relying on scheduled or continuous runs.

Never use this project with live-account credentials.


## Read-only shadow market research

A separate collector now exists at `shadow_research.py`. It reads only Bitget public **USDT perpetual futures** instruments, tickers and order books. It does not use account credentials or call trading endpoints.

Run locally:

```bash
python shadow_research.py --min-turnover 500000 --top-depth 50
```

Or open **Actions → Shadow Market Snapshot (Read Only) → Run workflow**. The run uploads timestamped JSON and CSV artifacts. The default screen is $500,000 24-hour USDT turnover, with order-book depth collected for the 50 highest-turnover eligible contracts.

The collector estimates visible-book market buy/sell fills at $100, $500 and $1,000, plus spread and depth inside 0.1%, 0.5% and 1%. These are hypothetical estimates, not fills. Bitget futures endpoints do not supply circulating market cap; market caps must be joined separately and timestamped before any coin is assigned to a cap band.

No Pollinations key is needed for numeric market collection. Pollinations may later be used for separate text analysis of public trader research, but never as the source of market prices, volume, order-book depth or P&L. Keep any future Pollinations credential in a budget-limited Actions Secret, never in source code or repository Variables.


## Four-band market-cap watchlist

Before starting the 24-hour recorder, run **Actions → Build Four-Band Futures Watchlist (Read Only) → Run workflow**. It screens online Bitget USDT perpetuals with at least $500,000 24-hour futures turnover, attempts exact CoinGecko symbol matching, fetches timestamped market caps, and checks visible depth for up to three candidates in each group. It commits `reports/market_cap_watchlist/current_watchlist.json` and a Markdown report. The daily collector then adds those selected contracts to its normal top-15 turnover sample.

Default editable ranges are in `config/market_cap_bands.json`: lower cap below $10m; smaller cap $10m–$100m; mid cap $100m–$1bn; mega cap $1bn and above. These are provisional definitions and should be confirmed before treating group labels as final. Exact ticker matches are provisional until manually checked; ambiguous symbols remain unclassified. Add a manually verified CoinGecko ID to `config/asset_identity_overrides.json` only after confirming the asset identity.

## 24-hour read-only research experiment

Follow [docs/RESEARCH_RUNBOOK.md](docs/RESEARCH_RUNBOOK.md) for the exact start, status, output and interpretation steps.

A separate research recorder is available at `daily_research.py`. Open **Actions → 24-Hour Futures Research (Read Only) → Run workflow**, choose `start`, and run it once. Scheduled GitHub Actions invocations then attempt a collection cycle every five minutes for 24 hours. The collector records Bitget USDT perpetual market observations, one-minute candles, public RSS trader/community commentary and rule-generated signal hypotheses. For each signal it attempts hypothetical $100/$500/$1,000 market entries by walking the visible order book, then at 5/15/30 minutes attempts a fresh exit-book walk for the exact hypothetical base quantity. It deducts the instrument taker-fee metadata when available and records partial/unavailable fills instead of inventing a completed trade. Funding is recorded as context but is not included in these short-horizon P&L estimates.

Research files are committed under `reports/daily_research/`:
- `candles_1m.jsonl` (de-duplicated completed candle observations)
- `market_observations.jsonl`
- `public_trader_posts.jsonl`
- `shadow_experiments.jsonl`
- `collection_errors.jsonl`
- `daily_research_summary.md` (generated when the session expires)

This is not guaranteed uninterrupted monitoring: GitHub scheduled runs can be delayed or skipped. Public posts are unverified claims, signals are hypotheses, and forward outcomes are reference-price calculations rather than fills. Market cap remains unverified until a separate timestamped source is joined. One day cannot prove profitability. No Bitget private key is used and no order, leverage, or position action is possible through this collector. See Section 17 of the project knowledge base.


### Shadow execution math and validation

- `shadow_execution.py` is a pure calculation module. It does not make HTTP requests and cannot place orders. It walks asks for hypothetical buys and bids for hypothetical sells, supports quote-notional entry and base-quantity exit, reports partial fills, and computes two-sided fees plus an explicitly supplied funding assumption.
- The daily recorder uses visible entry and later exit books for its shadow outcomes. Funding is deliberately excluded from the automatic short-horizon result unless a future implementation can verify that a settlement event occurred during the holding period. The funding rate at entry is retained as context.
- `research_report.py` creates `daily_research_summary.md` and reports two-snapshot book-walk outcomes separately from any legacy ticker-reference outcomes.
- The test suite now includes order-book execution, partial-fill handling, fee/funding arithmetic and report aggregation. GitHub Actions validation compiles the shadow modules and runs all tests.
- These are estimates, not exchange fills. Hidden liquidity, queue position, network latency, book changes between observations and actual funding settlement can change results.

### Watchlist readiness limitation

The existing daily collector samples the highest-turnover eligible Bitget USDT perpetual contracts. It does **not** yet constitute an approved 12-coin watchlist across the user's four requested market-cap groups. Market-cap data must be identity-matched to each contract, timestamped, and checked against a separately agreed band definition. Do not infer a coin's cap group from its ticker, and do not force three picks into a band when fewer than three genuinely qualify. The historical cap candidates in the knowledge base remain research leads, not a current approved watchlist.
