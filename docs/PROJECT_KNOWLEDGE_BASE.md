# Project Knowledge Base — Bitget Bot & Shadow-Trading Research

**Last updated:** 2026-11-23  
**Repository:** https://github.com/chimeremezewisdom6/Bitget-bot  
**Branch reviewed:** `main`  
**Purpose:** Preserve project history, verified findings, experiments, test evidence, known failures, research rules, and decisions so future work does not repeat mistakes.

> **Current operating instruction (2026-11-23): OBSERVATION ONLY.** Do not place Live orders or Bitget Demo orders. Do not enable the automated scanner. Research and shadow/paper records must be hypothetical and must never call an exchange order endpoint.

---

## 1. Project objective and operating boundary

The original project was a Bitget USDT-margined futures scanner intended to evaluate short-term market momentum and manage a Demo position. The user has since explicitly asked to stop all Demo and Live trading and instead observe the market, study public trader discussions and experiments, and calculate hypothetical trades with realistic execution costs.

The current research objective is to determine whether any strategy has a repeatable positive expectancy after fees, spread, slippage and (for perpetuals) funding. A strategy is not considered profitable merely because a chart entry looks good or a trader reports a win.

**Non-negotiable safety rules**
- No Live orders.
- No Demo orders.
- No order placement, leverage changes, account transfers, or position closing.
- Public market-data requests may be used for observation. Private account credentials are not required for public market research.
- Do not store API keys, secrets, passphrases, account identifiers, or other credentials in this repository.
- The automated scanner workflow must remain paused.
- A shadow-trade record is a simulation, not an exchange fill. Label it clearly.
- Never claim continuous monitoring unless a scheduled collector is actually deployed and its run history confirms it.

The repository's current `scanner.py` is still a Demo-capable trading program, not yet a dedicated observation-only shadow engine. Its hard Demo lock protects against Live-account routing, but **it does not make ordinary execution observation-only**. Until a separate shadow-only implementation exists, do not run it with `BOT_DRY_RUN=false` or credentials. The manual smoke workflow sets dry-run mode and is read-only; the automated scanner workflow is disabled.

## 2. Verified repository state at review

The `main` branch README describes:
- `scanner.py`: market scanning, account checks, Demo order handling, position supervision and exits.
- `tests/test_scanner_safety.py`: strategy, sizing, price-rounding and dry-run safety tests.
- `.github/workflows/validate.yml`: compile and unit-test workflow.
- `.github/workflows/demo-smoke-test.yml`: manually triggered, read-only Demo account/market check.
- `.github/workflows/scanner.yml`: intentionally paused scanner workflow.
- `live_active_trade.json` and `live_streak.json`: position/streak state files.
- `archive/legacy_trade_history.json`: old records not read by the current scanner.

The README says the scanner hard-locks `BITGET_DEMO_MODE = True`; the value cannot be switched to Live by an environment variable. Authenticated Demo requests add the `paptrading: 1` header. The README also warns that GitHub-hosted runners are ephemeral and state persistence must be deliberately implemented and tested before relying on scheduled or continuous runs.

**Credentials documented by the repository for the historical Demo-only smoke test:** `BITGET_API_KEY`, `BITGET_SECRET_KEY`, and `BITGET_PASSPHRASE`. These are GitHub Actions secret names only; never put their values in source files. The current user instruction is not to trade, so do not configure or use them for trading.

## 3. Strategy parameters found in current source

The current `scanner.py` constants and safety tests show this historical strategy:

| Parameter | Current source value |
|---|---:|
| Product type | `USDT-FUTURES` |
| Minimum 24-hour quote volume | $500,000 |
| Candle interval | 1 minute |
| Candle lookback | 60 completed candles |
| Entry threshold | 42 same-colour candles |
| Direction | Green majority -> LONG; red majority -> SHORT |
| Default leverage constant | 5x, subject to instrument maximum |
| Stop-loss range | Historical strategy described as 0.5%–2.5%; verify dynamic calculation in code before changing |
| Exit candle target | 30 matching-colour candles since entry |
| Maximum duration | 54 minutes |
| Candidate ranking | Dominant-colour count, then 24-hour volume |

Important interpretation:
- The tests assert `MIN_REQUIRED_COLOR_COUNT == 42`; treat this as a threshold of at least 42, not “more than 42.”
- The source filters for at least $500,000 24-hour quote volume. This is a liquidity screen, not proof that the order book can fill a particular order size cheaply.
- The 5x value is a historical default, not a recommendation. Contract maximum leverage is checked and fallback attempts step down rather than increase leverage.
- These parameters are historical strategy settings, **not proven profitable settings**. They must be evaluated in shadow mode before any future reconsideration.
- The strategy's 30 matching candles are counted after entry; the 54-minute cutoff is a maximum holding period. Stop-loss checking is intended to happen before the candle-count exit.

## 4. Engineering findings and changes recorded in Git history

The following changes are visible in the repository commit history reviewed on 2026-11-23:

| Commit (short SHA) | Recorded change / lesson |
|---|---|
| `2488c7c` | Candle ordering corrected; use the latest 60 completed one-minute candles in chronological order rather than an older slice. |
| `7660f60` / `5258a2e` | Tests added for chronological selection and completed-candle boundary. |
| `886238d` / `09faf76` | Use one stable Bitget API key/account identity for a scanner run; do not rotate keys across balance, positions, orders and closes. |
| `d07fb65` | Harden Demo stop-loss and filled-position state recovery. |
| `41e5d16` | Document single-account API-key safety. |
| `34406a4` / `a6e6f8b` | Prevent leverage fallback from exceeding instrument maximum; test fallback only steps down. |
| `2c302cc` | Reconcile accepted order responses against exchange positions before treating an order as unfilled. |
| `c6ddd73` / `41b60c6` / `c7f7648` | Correct and test LONG/SHORT position-fill recovery, including delayed order details and ambiguous order submissions. |
| `31ede3b` / `dc298ab` | Keep existing-position risk supervision available when equity/free margin is zero; retry recovery after ambiguous results. |
| `e6b2785` | Improve safe Demo balance diagnostics: validate response shape, treat missing USDT asset row as zero available margin, and log exchange error code/message without exposing secrets. |

Other historical cleanup commits removed obsolete or disconnected files. The README was updated to explain the remaining architecture and safety requirements.

### Why these changes matter

1. **Candle order and completion:** selecting the wrong end of an exchange response or including the still-forming candle can create a signal that did not exist at decision time. The corrected helper sorts by timestamp, excludes incomplete candles, and selects the latest requested count.
2. **One account identity:** rotating API keys during one scan could read balance from one account and positions/orders from another. The scanner now deliberately uses the first configured key set consistently.
3. **Exchange-confirmed fills:** an HTTP/order response alone is not enough to assert a position exists. The code attempts to reconcile the symbol and side against exchange positions and recover the average fill and quantity.
4. **Leverage fallback:** fallback must only reduce leverage and must respect the instrument's maximum.
5. **Risk supervision:** inability to open a new position due to zero equity/free margin must not prevent checking an already-open position.
6. **Diagnostics:** API failures should report safe exchange error details, never credentials or signed request headers.

## 5. Tests and validation evidence

The current test file contains 11 test methods. They cover:
1. Stable API-key selection (no rotation).
2. Demo-only lock and key strategy thresholds.
3. Quantity step, minimum notional, margin and leverage calculation.
4. Confirmed position-fill recovery by matching symbol and side.
5. Leverage fallback steps down only.
6. Instrument maximum leverage is never exceeded.
7. Invalid contract rules fail closed.
8. Latest completed candles are selected in chronological order.
9. Incomplete candles are excluded.
10. Stop-price rounding respects exchange tick direction.
11. Dry-run never attempts to change leverage.

The validation workflow runs Python 3.11, installs `requirements.txt`, compiles `scanner.py`, and runs `python -m unittest discover -s tests -v`.

**Prior session report:** 11/11 tests passed after the code changes. This is a historical report, not a fresh test run during this documentation update. Unit tests do not prove API connectivity, order fills, stop execution, or profitability.

### Smoke-test finding

A prior manual read-only Demo smoke test failed at balance verification. The scanner safely placed no order. The subsequent `e6b2785` change improved the diagnostic output so the Bitget response code/message is visible without exposing secrets.

This means account connectivity/balance verification was **not confirmed**. Do not describe the Demo integration as fully operational.

### Still unverified engineering work

- A complete supervised Demo order lifecycle was not verified: accepted order, confirmed fill, stop-loss, reduce-only close, and exchange-realized P&L.
- Position/state persistence across GitHub Actions runner restarts remains unresolved/unverified. Hosted runners are ephemeral.
- The automated scanner remains disabled.
- No evidence in the reviewed test suite proves real-time order-book slippage estimates.
- No verified strategy profitability result exists from the unit tests.

## 6. Legacy trade-history warning

`archive/legacy_trade_history.json` contains historical-looking records dated 2026-11-19 and 2026-11-20. The records mix `PAPER` and `LIVE` labels and include symbols and instruments that may not be ordinary crypto perpetuals. Some entries report large percentage results over only a few minutes, and the file is explicitly archived and not read by the current scanner.

**Do not treat these records as verified exchange executions or validated strategy performance.** Their origin, order IDs, exchange fills, fee calculations, funding, and reconciliation against Bitget account history have not been established. Preserve them as legacy data, but exclude them from performance statistics unless independently reconciled.

## 7. Shadow-trading research protocol (current direction)

The new research system must be separate from the order-capable scanner and must not call private trade endpoints.

### Observation universe

The user requested three coins from each of four market-cap groups:
- Lower cap: 3 coins.
- Small cap: 3 coins.
- Mid cap: 3 coins.
- Mega cap: 3 coins.

This gives 12 candidates. The earlier suggested list (GMX, ATH, HNT; AKT, RENDER, TAO; LINK, ADA, UNI; BTC, ETH, SOL) was only a provisional suggestion. It was **not verified** for current market-cap classification, Bitget USDT perpetual listing, or sufficient order-book liquidity. Do not mark it as a final watchlist until checked against current data. Define market-cap bands explicitly and record the timestamp/source used for classification.

### What to observe

For each candidate:
- Exchange symbol and contract availability/status.
- Market cap and category snapshot, source and timestamp.
- 24-hour quote volume.
- Best bid/ask, spread in basis points, mark/index/last price.
- Order-book depth at several price distances and estimated fill for a stated order notional.
- Volatility, candle structure, volume changes and market regime.
- Open interest and funding rate where available.
- Public trader posts/ideas and described entry/exit logic, each with URL, author/handle, timestamp, and whether the claim is self-reported or independently verifiable.
- Evidence that contradicts the trader's thesis, not just supporting comments.

Public trader posts are not verified fills. Never imply access to private positions or exact fills unless the trader publishes evidence that can be checked.

### Hypothetical trade record

Every shadow setup should capture:
- Unique ID, observation timestamp and data-source timestamps.
- Coin/contract, direction, strategy/version and market regime.
- Signal facts available at the time (avoid look-ahead bias).
- Intended entry and executable estimated entry.
- Bid/ask and order-book snapshot or archived depth used for fill calculation.
- Order type assumption (market or limit), quantity/notional, estimated partial fill and unfilled remainder.
- Entry and exit spread/slippage separately.
- Fee schedule assumption and maker/taker assumption, with source/date.
- Funding paid/received if the holding interval crosses a funding event.
- Stop, target, time exit, actual observed exit market and executable estimated exit.
- Gross P&L, all costs, net P&L, R-multiple, maximum favourable/adverse excursion.
- Outcome: win/loss/breakeven/no-fill/rejected/no-trade.
- Whether the rules were followed and why the setup was skipped or invalidated.

### Execution-cost rules

- For a hypothetical market buy, walk the ask levels for the chosen size; for a market sell, walk the bid levels. Calculate volume-weighted average fill rather than assuming the top-of-book price fills the entire order.
- Model entry and exit separately. Do not apply a single generic slippage number to all coins and sizes.
- A limit order is not filled just because the candle touches its price. Record it as unfilled unless queue/volume evidence supports a fill assumption; if queue position cannot be known, label the fill assumption conservative/uncertain.
- Model stop orders with adverse slippage under fast-market conditions.
- Include both entry and exit trading fees. Include funding when applicable.
- Report gross and net results separately. Never use leverage to disguise underlying price movement; show price return, notional P&L, margin return and liquidation risk distinctly.
- Keep the assumed order size fixed or explicitly record it. Slippage depends on size and depth.

### Trader-research quality rules

Classify evidence:
- **A — independently verifiable:** timestamped public fills/positions or reproducible exchange data with enough detail to verify.
- **B — detailed self-report:** entry, exit, timeframe and reasoning published, but not independently verified.
- **C — opinion/claim:** directional commentary without verifiable trade details.
- **D — promotional/unsubstantiated:** affiliate or paid claims, screenshots without context, edited win-only histories.

Do not copy a trader's position blindly. Extract the setup rules, independently evaluate them, and run a forward shadow test. Include losing examples, deleted/failed ideas where visible, and no-trade periods to reduce survivorship bias.

## 8. Public market-data sources to use

Prefer official exchange market-data endpoints and timestamp every snapshot. Bitget's public market-data documentation:
- Market data catalog: https://www.bitget.com/docs/catalog/market/market-data
- Best-practices guide (including order-book WebSocket channels): https://www.bitget.com/docs/uta/best-practices-guide

The documented market-data endpoints include futures tickers and order-book depth. Use public market-data routes for shadow research; do not use order placement endpoints. Check current API documentation, symbol status, rate limits and response schema before implementation.

## 9. Research hypotheses — not established facts

These are candidate areas to investigate, not signals that should automatically trigger a trade:
- Trend continuation and pullback entries.
- Liquidity sweeps and failed breakouts.
- Breakout/retest versus breakout-chase entries.
- Order-book imbalance and depth changes.
- Open-interest expansion/contraction alongside price.
- Funding extremes and crowded positioning.
- Liquidation events and post-liquidation price behaviour.
- Spot/perpetual divergence.
- Volatility regime filters and time-of-day effects.
- Market orders versus passive limit entries and the resulting fill/cost trade-off.

A strategy should only advance after a pre-registered rule set, out-of-sample test, forward shadow sample, realistic costs, and comparison against a simple benchmark. Track sample size and confidence intervals; do not declare an edge from a small streak.

## 10. Experiment log template

Append a new dated entry for every experiment. Never overwrite a failed experiment; add a new version and explain the change.

| Field | Required detail |
|---|---|
| Experiment ID | Unique ID and date |
| Hypothesis | What behaviour is expected and why |
| Strategy version | Exact rule/config version |
| Universe | Coins, exchange and contracts |
| Data | Source, timeframe, start/end, missing-data checks |
| Entry/exit | Fully specified, no hindsight |
| Costs | Fees, spread, slippage, funding and size assumptions |
| Sample | Trades, no-trades, market regimes |
| Results | Gross/net P&L, expectancy, win rate, profit factor, drawdown, MAE/MFE |
| Robustness | Out-of-sample, parameter sensitivity, benchmark |
| Decision | Reject, revise, or continue shadow test |
| Artifacts | Commit SHA, dataset/log path, source URLs |

### Experiment entries recorded so far

**E-000 — Repository safety and strategy unit tests (2026-11-22)**
- Scope: code-level checks for strategy constants, candle selection, sizing, leverage limits, position recovery, price rounding and dry-run safety.
- Evidence: 11 test methods in `tests/test_scanner_safety.py`; prior session reported 11/11 passing.
- Result: code-level assertions passed in the prior session.
- Limitation: no verified end-to-end exchange trade lifecycle and no profitability conclusion.
- Decision: keep automated workflow paused; require a separate observation-only implementation.

**E-001 — Read-only Bitget Demo connectivity check (2026-11-22)**
- Scope: manual `Bitget Demo Smoke Test (No Orders)` workflow.
- Result: balance verification failed; no order was placed.
- Follow-up: `e6b2785` improved safe diagnostics.
- Decision: account connectivity is unresolved; no Demo trading.

**E-002 — Trader strategy literature/community review (2026-11-23)**
- Scope: preliminary review of public trader experiments and strategy-testing claims.
- Key lesson: apparent chart/backtest profitability can disappear after fees and slippage; short timeframes are especially sensitive to execution assumptions. Public self-reports are not audited evidence.
- Status: preliminary research notes only. Individual studies, datasets, exact methodology, source URLs and replication status must be added before relying on any numeric claim.
- Decision: prioritize independently reproducible tests and forward shadow observations.

## 11. Known risks and next engineering tasks

1. **Build a separate shadow-only program.** It must not import or call order placement, leverage configuration, position closing, or private account methods. Add tests that patch/spy on any order endpoint and prove it is never called.
2. **Add public market-data collection.** Record timestamped tickers, candles and order-book snapshots for the 12 approved coins; add retry/backoff, rate-limit handling, clock normalization and raw-data retention.
3. **Implement execution simulator.** Walk book levels for market orders; conservative limit-fill model; independent entry/exit costs; fees and funding.
4. **Create append-only shadow trade ledger.** Store no-trade and rejected signals as well as fills and outcomes. Use stable IDs and schema versioning.
5. **Create reproducible research reports.** Separate in-sample, out-of-sample and forward shadow results; compare to buy/hold or simple directional baselines where appropriate.
6. **Fix persistence intentionally.** Do not assume GitHub Actions filesystem changes survive between runs. Use a deliberate artifact/database strategy and test recovery.
7. **Keep trading disabled.** The current automated scanner workflow contains an always-false job condition. Do not remove it as part of research work.

## 12. Change-control rules for future assistants/contributors

- Read this file and the current README before changing strategy or workflow code.
- Inspect current source and tests; do not assume this history is still current after later commits.
- Every code change must include a test for the failure it addresses.
- Update this file in the same change/commit when a test, finding, strategy rule, limitation or architecture decision changes.
- Record commit SHA, test command, result, and any tests not run.
- Separate facts observed in source, facts reported by prior sessions, and hypotheses. Label uncertainty explicitly.
- Never fabricate a test, market observation, trader quote, fill, result, or source.
- Do not turn an experimental strategy into an execution rule without explicit user authorization and a successful safety review.
- Preserve failed experiments and explain why they failed.
- Do not claim the bot is “perfect,” profitable, continuously monitoring, or exchange-verified without direct evidence.

---

**End of current knowledge snapshot.** Add future discoveries below the appropriate section and append dated experiment entries rather than replacing historical evidence.
