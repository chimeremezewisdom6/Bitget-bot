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


## 13. Market-cap / Bitget-volume watchlist screening (2026-11-23)

**User request:** Select three crypto assets in each market-cap band: below $1m, $1m-$10m, $10m-$100m, and $100m-$1bn; check their current Bitget trading activity. This is a research universe only, not a trade recommendation.

### Source and measurement caveats

- Bitget's own markets pages expose pair, market cap and 24-hour amount/turnover, but search-indexed snapshots are not guaranteed to be synchronized to the same minute.
- CoinGecko's Bitget exchange page reports exchange-specific spot pair volume, spread and ±2% order-book depth; it showed BTC/USDT $429.37m, ETH/USDT $169.15m, SOL/USDT $53.35m, WLD/USDT $2.07m and other rows at the captured snapshot.
- Coinstrooper's Bitget listings page exposes a market-cap and 24h-volume table, but some volume-to-market-cap ratios are extreme and require direct exchange/API confirmation. Treat its small-cap figures as provisional leads, not verified exchange execution quality.
- CoinGecko exchange volume and Bitget perpetual futures volume are different markets. Do not mix spot volume with futures volume in a single ranking. The user should confirm whether the observation universe should be spot, USDT perpetuals, or both; current project strategy historically scans USDT perpetuals, so the final strategy universe should use futures volume and contracts.
- The candidate market cap and Bitget 24h volume are snapshots, not fixed attributes. Recheck before each observation session.

### Provisional candidates from the exchange-listed coin table

The following first three groups are provisional screening leads from Coinstrooper's Bitget listings snapshot. Values are shown exactly as reported by that source:

| Market-cap band | Coin | Reported market cap | Reported Bitget 24h volume | Status |
|---|---|---:|---:|---|
| Below $1m | TCOM | $730,000 | $8.69m | Provisional; verify pair/depth |
| Below $1m | AGENDA 47 (A47) | $587,630 | $7.82m | Provisional; verify pair/depth |
| Below $1m | Redacted Coin (RDAC) | $14,970 | $9.78m | Reject pending verification; volume/cap ratio is extreme |
| $1m-$10m | IKA | $1.65m | $13.72m | Provisional; verify pair/depth |
| $1m-$10m | StakeStone (STO) | $4.71m | $8.60m | Provisional; cross-check market cap source |
| $1m-$10m | Syscoin (SYS) | $1.89m | $7.03m | Provisional; verify pair/depth |
| $10m-$100m | HOME | $17.90m | $17.37m | Provisional; verify pair/depth |
| $10m-$100m | BSquared (B2) | $28.73m | $13.44m | Provisional; verify pair/depth |
| $10m-$100m | River (RIVER) | $16.39m | $13.20m | Provisional; verify pair/depth |

**Important:** The table's volume-to-market-cap ratios are unusually high for several names, especially RDAC, TCOM and A47. This can reflect a genuine event, a very small circulating market cap, a data mismatch, wash trading, or thin liquidity. It is not evidence of reliable executable liquidity. RDAC is deliberately not accepted as a final watchlist coin until corroborated.

### $100m-$1bn band: exchange-specific cross-checks

| Coin | Market cap source snapshot | Bitget spot 24h volume | Bitget spread / depth | Status |
|---|---:|---:|---|---|
| Worldcoin (WLD) | approximately $884m-$899m | approximately $2.09m-$2.42m | CoinGecko snapshot: 0.04% spread; +2% depth $432,550; -2% depth $647,592 | Strongest provisional candidate in this band |
| Official Trump (TRUMP) | approximately $249m-$265m | approximately $431k-$454k | CoinGecko snapshot: 0.11% spread; +2% depth $207,075; -2% depth $245,228 | Provisional; relatively low Bitget spot volume |
| Artificial Superintelligence Alliance (FET) | approximately $265m (confirm current cap before use) | approximately $562k | CoinGecko snapshot: 0.09% spread; +2% depth $60,639; -2% depth $123,700 | Provisional; shallow depth relative to larger assets |

### Screening conclusion

This is not yet a fully verified 12-coin list. The initial exchange-listings source yields nine provisional leads in the first three bands, while WLD, TRUMP and FET have separate Bitget pair-level spot volume/depth cross-checks in the $100m-$1bn band. Several micro-cap listings have suspiciously high volume relative to reported market cap. Do not silently promote them to the approved watchlist.

**Next verification step:** query Bitget's official public spot and USDT-futures instruments/ticker/order-book endpoints for each symbol; confirm online status, exact pair, 24h quote turnover, bid/ask spread, and depth for a fixed hypothetical order size. Independently retrieve circulating market cap with a timestamp. If a candidate fails any check or is not listed in the relevant product, replace it with the next qualifying coin. Keep separate spot and futures volume columns.

### Sources captured 2026-11-23

- Coinstrooper Bitget listings and market-cap/volume table: https://coinstrooper.com/exchange/bitget
- CoinGecko Bitget spot exchange markets (pair-level volume, spread, depth): https://www.coingecko.com/en/exchanges/bitget
- Bitget official spot USDT markets: https://www.bitget.com/markets/spot/USDT
- Bitget official 24h crypto volume overview (explicitly includes assets not listed on Bitget; do not use it alone as proof of listing): https://www.bitget.com/price/crypto-top-volume-24hr
- Worldcoin market cap and Bitget pair: https://www.coingecko.com/en/coins/worldcoin
- Official Trump market/pair comparison: https://www.coingecko.com/en/coins/official-trump
- Artificial Superintelligence Alliance markets: https://www.coingecko.com/en/coins/artificial-superintelligence-alliance

**Decision:** treat the above as an initial candidate screen, not an approved final watchlist or a claim of profitable opportunity. All observation remains shadow-only; no Demo or Live orders.


## 14. Futures-only market-cap screening update (2026-11-23)

**User decision:** the watchlist must be restricted to Bitget **USDT perpetual futures**. Spot markets and Spot turnover are excluded. This supersedes the earlier open question in Section 13; the spot candidates there are not approved for the futures watchlist.

### Evidence gathered

- Bitget's official market-data documentation defines the `USDT-FUTURES` category and documents public futures instruments, tickers, order books, 24-hour turnover, bid/ask, funding and open interest. The public endpoints needed are `/api/v3/market/instruments`, `/api/v3/market/tickers`, and `/api/v3/market/orderbook`. Source: https://www.bitget.com/docs/catalog/market/market-data
- Bitget's official markets page lists USDT perpetual contracts and displayed 24-hour amounts. A search-indexed snapshot on 2026-11-23 showed high turnover examples including BTCUSDT, ETHUSDT, IRYSUSDT, SOXLUSDT, ZECUSDT, SOLUSDT, NEARUSDT, KORUUSDT, WLDUSDT, SUIUSDT, ADAUSDT and others. Source: https://www.bitget.com/markets/
- Loris Tools' Bitget perpetual tracker (snapshot 2026-11-23 06:56 UTC) reported BLESS about $29.15m, MMT about $27.33m, ACE about $25.81m and ELSA about $17.97m 24h futures turnover; this is a third-party tracker, not the official API. Source: https://loris.tools/markets/exchanges/bitget
- CoinGecko historical snapshots dated 2026-11-23 reported market caps: ACE about $7.65m (CoinMarketCap snapshot), BLESS about $29.72m, MMT about $44.46m, and ELSA about $25.69m. Sources: https://coinmarketcap.com/currencies/fusionist/ ; https://www.coingecko.com/en/coins/bless/historical_data ; https://www.coingecko.com/en/coins/momentum-2/historical_data ; https://www.coingecko.com/en/coins/elsa/historical_data
- Bitget's own WLDUSDT perpetual page showed 24h turnover about $9.48m and volume 41.25m WLD in its captured snapshot. Source: https://www.bitget.com/futures/usdt/WLDUSDT
- Bitget's own STOUSDT perpetual page showed only about $28.87k 24h turnover in its captured snapshot. Despite a previous Spot/exchange listing screen suggesting a small market cap, that futures turnover is low and does not meet the historical scanner's $500,000 minimum-volume screen. Source: https://www.bitget.org/futures/usdt/STOUSDT
- Bitget announced DGAIUSDT USDT-M perpetual futures listing on 2026-09-04. CoinGecko/CoinMarketCap snapshots on 2026-11-23 placed DGAI market cap around $148m-$149m, inside the $100m-$1bn band. Listing evidence: https://www.bitget.com/support/articles/12560603894266 ; market cap: https://coinmarketcap.com/currencies/dgrid-ai/

### Preliminary classification (not a complete approved 12-coin watchlist)

| Band | Candidate | Market cap snapshot | Bitget USDT perp evidence | Status |
|---|---|---:|---|---|
| Below $1m | None verified | — | No verified crypto contract with qualifying cap and turnover established in this pass | Keep band empty rather than invent candidates |
| $1m-$10m | ACE | About $7.65m | Bitget futures tracker reported about $25.81m turnover | Strong provisional candidate; confirm via official ticker API |
| $1m-$10m | STO | About $4.71m in earlier third-party screen | Official Bitget STOUSDT page showed about $28.87k turnover | Reject for current scanner universe; below $500k screen |
| $1m-$10m | Other candidates | — | No two additional candidates verified to both cap band and active USDT perp turnover | Do not fill by guess |
| $10m-$100m | BLESS | About $29.72m | Bitget futures tracker about $29.15m turnover | Strong provisional candidate; verify official ticker/order book |
| $10m-$100m | MMT | About $44.46m | Bitget futures tracker about $27.33m turnover | Strong provisional candidate; note exceptional funding/volatility conditions require checking |
| $10m-$100m | ELSA | About $25.69m | Bitget futures tracker about $17.97m turnover | Strong provisional candidate; verify official ticker/order book |
| $100m-$1bn | DGAI | About $148m-$149m | Bitget official listing announcement confirms USDT-M perpetual; current exact turnover not captured from official ticker in this pass | Contract confirmed, turnover pending |
| $100m-$1bn | WLD | About $884m-$899m in prior market-cap screen | Official Bitget WLDUSDT page about $9.48m turnover | Strong provisional candidate |
| $100m-$1bn | Other candidates | — | No third candidate's current cap and Bitget futures turnover both confirmed in this pass | Do not fill by guess |

### Screening decision and next verification

This pass does **not** establish 12 qualified candidates. The under-$1m group has no verified qualifying contract, and the $1m-$10m group currently has only ACE as a promising turnover candidate. This is a real universe/liquidity constraint, not a reason to substitute Spot volume or fabricate picks. The historical scanner's $500,000 24h volume floor is a useful first screen, but turnover alone does not prove depth or low slippage.

Before approving a coin, collect a same-session official Bitget API snapshot for `category=USDT-FUTURES`: instrument status must be `online`; ticker must supply `turnover24h`, `bid1Price`, `ask1Price`, `fundingRate`, `openInterest`, and timestamp; order-book depth must be walked for hypothetical fixed notionals. Independently record circulating market cap and its timestamp. Never use Spot turnover to pass a futures candidate. If fewer than three valid assets exist in a band, record fewer than three and explain why.

**Operating boundary remains observation-only:** no Demo or Live orders, no order placement, no leverage changes, and no position management. All candidate names are watchlist research leads, not trade recommendations or proof of profitability.


## 15. Read-only futures market collector setup (2026-11-23)

**User authorized:** proceed with the USDT-perpetual-only market-cap and liquidity verification. User mentioned a Pollinations API key stored in repository secrets/variables and allowed its use if useful.

### Security and Pollinations decision

- The initial numeric market scan does not need Pollinations or any private credential. Bitget's public market-data API supplies instrument status/type, 24h quote turnover, best bid/ask, mark/index price, funding, open interest and public order-book levels.
- Pollinations is a generative AI API, not an exchange market-data source. It may be useful in a later, separate stage to summarize public trader posts or compare written strategy claims, but it must not determine market-cap bands, volume, fills, slippage or P&L.
- No Pollinations key was read, copied, printed, or added to code/workflow in this setup. Do not put a key in repository files or GitHub Actions Variables. If later needed, use a narrowly scoped, budget-limited GitHub Actions Secret and pass it only to the separate narrative-analysis step. Do not use the key in browser code.
- The existing comment in `scanner.py` saying "POLLINATION KEYS" refers to the historical Bitget multi-key loader and is not an actual Pollinations integration.

### New files committed

- `shadow_research.py`: a separate public-data collector for Bitget `USDT-FUTURES`. It reads only:
  - `GET /api/v3/market/instruments?category=USDT-FUTURES`
  - `GET /api/v3/market/tickers?category=USDT-FUTURES`
  - `GET /api/v3/market/orderbook?category=USDT-FUTURES`
- `tests/test_shadow_research.py`: tests for price-band depth, order-book walking, VWAP/slippage and partial visible-book fills.
- `.github/workflows/shadow-market-snapshot.yml`: manually triggered workflow that installs existing dependencies, runs the collector and uploads timestamped JSON/CSV artifacts for 30 days.

### Collector behavior and limitations

- Filters to online perpetual crypto instruments and a configurable minimum 24h turnover (default $500,000 USDT).
- Sorts by Bitget 24h turnover and obtains up to the top 50 order books (configurable).
- Captures spread, funding, open interest, mark/index/last price, maker/taker fee metadata, order-book depth within 0.1%, 0.5% and 1%, and hypothetical market buy/sell walks for $100, $500 and $1,000.
- Uses no Bitget API keys, no account endpoints, no order endpoints, no leverage endpoint, and no position endpoints.
- It does not claim a market cap from Bitget. Market cap must be joined from a separate source with its own timestamp and symbol-identity checks. The report deliberately labels market cap as unverified until that step is complete.
- The script collects visible-book execution estimates only; it cannot know queue position, hidden liquidity, future book movement or guaranteed fills. These are estimates, not actual executions.
- The workflow is manual only. No scheduled or continuous monitoring has been enabled. Artifacts expire after 30 days; GitHub-hosted runner files do not persist automatically.

### Validation state

- GitHub Actions validation was triggered by the new commits. At the time of this knowledge update, the latest run was still queued/in progress; do not mark tests passed until its conclusion is checked.
- The manual snapshot workflow has been committed but has not yet been dispatched. No current live snapshot has been collected by this new script.
- The automated trading workflow remains paused and untouched.

### Commits

- `88cf6d9` — add read-only Bitget USDT perpetual market collector.
- `1615a48` — add depth and slippage unit tests.
- `be091e2` — add manual read-only market snapshot workflow.

### Next steps

1. Confirm the validation workflow result, including the new tests.
2. Run the manual snapshot workflow and inspect the artifact for actual Bitget results.
3. Join each eligible futures base asset to a timestamped market-cap source, with ambiguous symbol matches manually reviewed.
4. Select up to three valid coins in each cap band; leave any band short if fewer than three pass.
5. For shortlisted candidates, collect repeat order-book snapshots and shadow observe entries/exits. Keep trader-post research separate from exchange measurements.


### Validation follow-up (2026-11-23)

- GitHub Actions run `45153088662` for commit `be091e2` completed with conclusion `success`.
- Confirmed steps: dependency install, compile of `scanner.py`, and full `python -m unittest discover -s tests -v` step all succeeded. This includes the new shadow-research unit tests because they are discovered by the existing test command.
- This validates syntax and unit tests, not a live API collection. The manual shadow snapshot workflow still needs to be run by a user from GitHub Actions before any real market snapshot is available.
- Documentation-only commits after that successful run triggered additional validation runs which were queued when checked; no failure was observed in the successful code-validation run.


## 16. First successful official Bitget futures snapshot and cap cross-check (2026-11-23)

### Snapshot execution evidence

- User manually dispatched **Shadow Market Snapshot (Read Only)**. GitHub Actions run: https://github.com/chimeremezewisdom6/Bitget-bot/actions/runs/45153758690
- Run ID: `45153758690`; event: `workflow_dispatch`; conclusion: `success`; started 2026-11-23 10:11:12 UTC and completed 10:11:30 UTC.
- Artifact: `bitget-usdt-perp-shadow-snapshot-45153758690` (artifact ID `14808350074`), containing JSON and CSV. The artifact was retrieved and inspected directly; no user download was required.
- Collector timestamp: `2026-11-23T10:11:25.309973+00:00`.
- Universe: Bitget `USDT-FUTURES`; public market data only; no account endpoints or trading actions.
- Candidate count: 133 online perpetual crypto contracts passing the configured $500,000 24h turnover filter.
- Depth was collected for the top 50 contracts by turnover. The workflow produced a timestamped JSON and CSV report.
- The raw snapshot has no market-cap values: all `market_cap_usd` values are null and `market_cap_band` is `UNVERIFIED`. Market-cap classification below is a separate timestamped external-source join, not a Bitget field.

### Selected futures rows from the snapshot

Values below are from the official Bitget public collector snapshot at 10:11:25 UTC. Turnover is 24h quote turnover in USDT. Spread is in basis points. The 0.5% depth is visible order-book notional on each side within 0.5% of mid-price.

| Contract | 24h turnover | Spread (bps) | 0.5% bid depth | 0.5% ask depth |
|---|---:|---:|---:|---:|
| ACEUSDT | $27.23m | 15.35 | $402 | $1,141 |
| BLESSUSDT | $27.43m | 7.56 | $18,485 | $18,274 |
| MMTUSDT | $20.98m | 13.09 | $31,794 | $28,088 |
| ELSAUSDT | $22.41m | 10.41 | $20,875 | $13,908 |
| DGAIUSDT | $11.52m | 8.95 | $19,932 | $15,563 |
| WLDUSDT | $8.04m | 4.23 | $545,688 | $830,038 |

**Interpretation:** turnover alone is misleading. ACE had $27.23m reported 24h turnover but only about $402 bid depth and $1,141 ask depth within 0.5%, plus a 15.35 bps spread. Do not treat it as liquid for meaningful market orders without much smaller sizing and repeated snapshots. BLESS, MMT, ELSA and DGAI also show shallow 0.5% depth compared with their turnover. WLD has materially deeper visible book in this snapshot, but still needs repeat sampling and fill simulation. A single snapshot cannot establish persistent liquidity.

Other high-turnover examples in this same snapshot included BTCUSDT ($3.024bn), ETHUSDT ($941.29m), PIEVERSEUSDT ($100.65m), SOLUSDT ($95.38m), XRPUSDT ($66.65m), EVAAUSDT ($64.24m), ZECUSDT ($59.93m), HYPEUSDT ($31.05m), NEARUSDT ($28.85m), and PEPEUSDT ($17.51m). These are turnover ranks only; do not assign cap bands without identity-matched cap data.

### Separate market-cap cross-check (2026-11-23)

The following public market-cap pages were checked separately. Market caps can differ across providers and update times; the cap band is provisional and should be timestamped on each future run.

| Band | Candidate | Market cap evidence | Bitget 24h futures turnover in snapshot | Initial decision |
|---|---|---:|---:|---|
| Below $1m | None confirmed | No eligible candidate identified from this pass | — | Leave empty; do not invent a contract |
| $1m-$10m | ACE (Fusionist) | CoinMarketCap about $7.65m; CoinGecko same-day page about $9.06m | $27.23m | Cap fits, but reject from preferred liquidity shortlist for now: book depth is exceptionally thin and current news reported a bridge exploit/trading-pause concern. Recheck instrument and risk status before any future observation. |
| $10m-$100m | BLESS | CoinGecko historical page about $29.72m | $27.43m | Candidate only; shallow book relative to turnover |
| $10m-$100m | MMT (Momentum) | CoinGecko historical page about $44.46m | $20.98m | Candidate only; shallow book and funding/volatility need close review |
| $10m-$100m | ELSA (HeyElsa) | CoinGecko historical page about $25.69m | $22.41m | Candidate only; shallow book relative to turnover |
| $100m-$1bn | DGAI (DGrid AI) | CoinGecko historical page about $147.92m | $11.52m | Candidate only; shallow book |
| $100m-$1bn | WLD (Worldcoin) | CoinGecko historical page about $899.60m | $8.04m | Stronger visible depth in this snapshot; still needs repeat observations |
| Above $1bn (outside requested bands) | PIEVERSE | CoinGecko historical page about $1.011bn | $100.65m | Exclude from $100m-$1bn band; just above the upper boundary |

Sources for cap checks:
- ACE / Fusionist, CoinMarketCap: https://coinmarketcap.com/currencies/fusionist/
- ACE / Fusionist, CoinGecko: https://www.coingecko.com/en/coins/fusionist
- BLESS historical cap: https://www.coingecko.com/en/coins/bless/historical_data
- MMT historical cap: https://www.coingecko.com/en/coins/momentum-2/historical_data
- ELSA historical cap: https://www.coingecko.com/en/coins/elsa/historical_data
- DGAI historical cap: https://www.coingecko.com/en/coins/dgrid-ai/historical_data
- WLD historical cap: https://www.coingecko.com/en/coins/worldcoin/historical_data
- PIEVERSE historical cap: https://www.coingecko.com/en/coins/pieverse/historical_data
- Bitget public futures collector code and raw endpoints are recorded in Section 15; snapshot artifact came from the successful run linked above.

### Current watchlist status and decision

- The first successful snapshot validates the collector and gives a real, timestamped futures dataset.
- It does **not** produce three approved coins in every band. Below $1m remains empty. The $1m-$10m band has ACE as a cap match but its visible depth is too thin for preferred execution research at ordinary notionals. The $10m-$100m band has three turnover/cap matches, but all have relatively shallow visible depth. The $100m-$1bn band has DGAI and WLD; WLD has the stronger visible depth of the two.
- Do not force 12 picks. Keep the four bands distinct, preserve gaps, and prioritize execution quality rather than raw turnover.
- Next research step: repeat public order-book snapshots at intervals for candidates; compare depth stability, spread, book walk for $100/$500/$1,000, and fees/funding. For ACE, verify the exploit/trading-pause situation before retaining it. Continue searching for alternatives that genuinely pass cap band, Bitget USDT perpetual status, $500,000 turnover and minimum depth/spread criteria.
- No shadow trade has been opened or closed from this snapshot. It is a market-liquidity baseline only. No Demo or Live order was placed.


## 17. 24-hour read-only futures research recorder (2026-11-23)

### Purpose and operating model

The user wants a full-day experiment file, not just a one-time market snapshot. Added `daily_research.py` and `.github/workflows/daily-futures-research.yml` to record a 24-hour Bitget USDT perpetual futures research session.

- Start manually from GitHub Actions with action `start`. This creates a UTC start/end time and activates the session for 24 hours.
- A GitHub Actions schedule invokes the collector every five minutes. Each invocation runs as a short job, reads the session state, and records a cycle only while the 24-hour session is active. This avoids relying on a single GitHub-hosted job running continuously; hosted jobs have a six-hour maximum.
- Each scheduled run commits new research records to the repository using the workflow's `GITHUB_TOKEN` and `contents: write` permission. No Bitget key is used.
- Scheduled invocations may be delayed or skipped by GitHub; timestamps and collection errors must be inspected. Do not describe this as guaranteed uninterrupted monitoring.
- The scheduled workflow remains installed after the 24-hour session and performs no-op checks when inactive. Consider disabling the schedule after a completed experiment or changing the workflow to stop scheduling automatically in a later engineering pass.

### Market observations collected

- Public Bitget USDT-FUTURES instruments and tickers; only online perpetual contracts.
- Candidates with at least $500,000 24h quote turnover; top 15 by turnover sampled per cycle.
- For each selected contract: last/mark/index price, 24h turnover, funding rate, open interest, best bid/ask, spread, order-book timestamp, visible bid/ask depth within 0.5%, and recent 1-minute candle availability.
- No market-cap value is fabricated. Market cap remains UNVERIFIED until joined from a timestamped, identity-matched external source.
- Public RSS feeds are polled for Reddit BitcoinMarkets, Daytrading, CryptoCurrency, CoinDesk and Cointelegraph posts/articles. These are public commentary and are not proof of a trader's identity, positions, fills or profitability. X/Twitter coverage is not implemented.

### Shadow experiments

The collector records rule-generated hypotheses from completed 1-minute candles:
- EMA 9/21 trend continuation with price and quote-turnover confirmation.
- 20-bar breakout / breakdown with quote-turnover confirmation.
- RSI14 extreme-level watch signals (explicitly not treated as reversal confirmation).

For each new signal, the script records hypothetical reference-price entry and schedules 5-, 15-, and 30-minute forward reference-price evaluations. Net estimate subtracts a spread + two taker-fee estimate. These are not executable fills and omit funding, changing spread, dynamic impact, queue position, hidden liquidity and stop execution. They must not be presented as verified strategy profitability.

### Output files

- `reports/daily_research/market_observations.jsonl`: repeated market observations.
- `reports/daily_research/candles_1m.jsonl`: deduplicated raw one-minute OHLCV and quote-turnover candles.
- `reports/daily_research/public_trader_posts.jsonl`: deduplicated public RSS items with explicit unverified classification.
- `reports/daily_research/shadow_experiments.jsonl`: signal hypotheses and forward reference-price evaluations.
- `reports/daily_research/collection_errors.jsonl`: source and API failures.
- `reports/daily_research/session.json`: session timing and counters.
- `reports/daily_research/daily_research_summary.md`: generated end-of-session summary.

### Evidence policy and research questions

Keep measured exchange data, public trader claims, rule-generated hypotheses, and model interpretations separate. Record both favorable and adverse observations, including no-signal periods, missing data, false breakouts, failed reversals, trend continuation, liquidity deterioration and estimated trading costs. A one-day run is exploratory and cannot prove a strategy is profitable or establish a robust risk/reward edge. Require larger out-of-sample and forward-shadow samples before strategy promotion.

Questions to investigate in later analysis:
- Why apparent highs keep extending or apparent lows keep breaking (trend persistence, new information, positioning/liquidations, liquidity imbalance); these are candidate explanations, not conclusions from this collector alone.
- Which reversals receive confirmation and which are only countertrend bounces.
- Whether turnover aligns with executable depth and tolerable spread.
- Whether strategy results remain positive after realistic fees, slippage and funding.
- Which market regimes and coin groups produce the largest adverse excursions and losses.

### Safety

- Observation-only: public endpoints, no private API keys, account endpoints, orders, leverage changes, position changes or closes.
- The existing scanner and trading workflows remain untouched and must stay paused.
- The Pollinations key is not used; it is not a market-data source. Do not expose or paste the secret.

### Initial implementation status

- Added `daily_research.py`.
- Added manual start/status plus every-five-minute scheduled workflow `.github/workflows/daily-futures-research.yml`.
- Hardened Atom/RSS element parsing and added handling for missing delayed forward-evaluation prices.
- **Not yet run or validated end-to-end.** The user must start the 24-hour session once from the new workflow. The first run's logs and resulting files must be inspected before treating the collector as proven.

- Additional raw dataset: `reports/daily_research/candles_1m.jsonl` stores deduplicated 1-minute OHLCV/quote-turnover candles so later analysis can independently recompute signals and inspect price paths.


## 18. Shadow execution and 24-hour research hardening (2026-11-23)

### Changes committed

- Added `shadow_execution.py`, a pure calculation module with no network access. It walks visible asks for hypothetical buys and visible bids for hypothetical sells, supports quote-notional entry and base-quantity exit, computes VWAP, and reports incomplete/partial fills without inventing a full execution.
- Added round-trip calculations for LONG and SHORT positions, separate entry/exit taker fees, and an explicitly supplied signed funding assumption. The module does not infer funding settlements or submit orders.
- Integrated the daily collector with order-book shadow observations. At a signal it attempts hypothetical $100, $500 and $1,000 entries using the current visible book. It only schedules an outcome when the full hypothetical entry size is visible and a taker-fee rate is available from Bitget instrument metadata. Missing fee metadata fails closed rather than assuming zero fees.
- At 5, 15 and 30 minutes, the collector requests a fresh public order book and attempts to close the exact hypothetical base quantity. It records separate entry/exit VWAP and slippage, gross P&L, entry and exit fees, net P&L after trading fees, and partial/unavailable exit states. Funding is retained as context but excluded from these short-horizon automatic results because the collector does not yet verify whether a funding settlement timestamp was crossed.
- Added `research_report.py` to summarize actual cycle counts, symbols, observations, commentary, signals, two-snapshot order-book outcomes, unavailable outcomes, and collection errors. Ticker-only legacy outcomes are kept separate.
- Added a 30-minute settlement grace period after the 24-hour signal-generation window so pending 30-minute shadow exits can be evaluated. No new signals or RSS commentary are added during the grace period. Starting a second session while one is active is rejected.
- Updated GitHub Actions validation to compile the shadow modules and run the expanded unit suite. Added a static boundary test that checks the research modules contain no account/order/trade routes and no HTTP POST calls.

### New files

- `shadow_execution.py`
- `research_report.py`
- `tests/test_shadow_execution.py`
- `tests/test_research_report.py`
- `tests/test_shadow_only_boundary.py`

### Important limitations retained

- A two-snapshot book walk is still a hypothetical estimate. It cannot guarantee execution, queue priority, hidden liquidity, network latency, or unchanged depth between snapshots.
- The automated outcome currently deducts the instrument taker-fee metadata when present. It does not yet include funding settlement costs, liquidation effects, or a separately calibrated adverse stop-market model.
- The daily universe includes the top 15 online USDT perpetual contracts above the $500,000 24-hour turnover threshold plus any selected contracts from the current provisional four-band watchlist. The four-band watchlist still requires manual identity review before it is considered approved.
- The Bitget futures API does not supply market cap. Asset identity and cap must be joined from an independent timestamped source; ambiguous symbols must remain unverified.
- The public RSS feeds provide commentary, not verified trader identities, actual positions, or audited trade histories.
- GitHub cron is best-effort, not guaranteed five-minute continuous monitoring. The actual cycle timestamps and missing intervals must be reviewed.
- No Demo or Live trading was enabled. The automated scanner workflow remains paused.

### Validation state after these commits

The validation workflow is triggered by pushes to `main`. Do not claim the expanded tests passed until the latest GitHub Actions validation run has completed successfully. The research session itself has not been started by these code changes; the user must manually dispatch **24-Hour Futures Research (Read Only)** with action `start`.

### Additional collector safeguards (same update)

- Added bounded retries with exponential backoff for transient Bitget HTTP/API failures.
- Reuses one exit-book snapshot per symbol per collection cycle when several hypothetical sizes/horizons become due, reducing redundant requests.
- Fetches public RSS commentary every third cycle (approximately 15 minutes), rather than every five-minute market cycle.
- RSI overbought/oversold extremes are explicitly classified as watch-only conditions. They do not initiate shadow entries without a separate reversal-confirmation rule.
- The latest successful validation recorded before these final small safeguards was run #85 (commit 72e48110). A newer validation is triggered by subsequent commits and must be checked before calling the final repository state fully validated.


## 19. Four-band market-cap watchlist builder (2026-11-23)

### New workflow and files

- Added `cap_watchlist.py` and manual GitHub Actions workflow `.github/workflows/market-cap-watchlist.yml`.
- The builder obtains online Bitget `USDT-FUTURES` instruments and tickers, screens for at least $500,000 24-hour futures turnover, attempts exact CoinGecko symbol matching, joins CoinGecko USD market-cap snapshots, and collects a 0.5% order-book depth snapshot for selected contracts.
- It selects up to three candidates per group by futures turnover and spread. It does not force three picks when fewer qualify.
- It writes `reports/market_cap_watchlist/current_watchlist.json` and `current_watchlist.md`, uploads a 30-day workflow artifact, and commits the current files so the daily collector can use them.
- The daily 24-hour recorder now samples the top 15 turnover contracts plus selected contracts from the current cap watchlist. Market-cap value, band, source update timestamp and identity status are recorded with market observations.

### Configurable default groups

`config/market_cap_bands.json` defines provisional boundaries:
- Lower cap: below $10 million.
- Smaller cap: $10 million to below $100 million.
- Mid cap: $100 million to below $1 billion.
- Mega cap: $1 billion and above.

These are operational defaults, not a claim that the user previously approved exact thresholds. Change the configuration if the intended category definitions differ.

### Asset identity safeguards

- A unique exact CoinGecko ticker-symbol match is still marked `unique_exact_symbol_needs_review`; ticker equality alone does not prove that two assets are the same project.
- Multiple exact symbol matches are classified as ambiguous and are not assigned a market-cap band.
- Manual overrides live in `config/asset_identity_overrides.json`. Set `verified: true` only after independently checking the exact project identity and CoinGecko ID.
- The report retains source timestamps and visible spread/depth. A one-time liquidity snapshot does not prove persistent liquidity or safe execution.

### Validation and execution status

- GitHub Actions validation run #101, commit `c6b48426`, completed successfully. It compiled the research modules and ran 29 unit tests successfully, including cap-band boundaries, ambiguous-symbol handling, watchlist shortfall handling, shadow execution math, report aggregation, and the no-order/account-route boundary test.
- The market-cap watchlist workflow has been added but has not yet been manually dispatched. No current four-band watchlist artifact has been produced by this new workflow.
- The 24-hour research session has not been started. User should first run **Build Four-Band Futures Watchlist (Read Only)**, inspect/verify asset identities and the provisional bands, then start **24-Hour Futures Research (Read Only)**.
- No Demo or Live trading was enabled; the automated scanner remains paused.


### Session control refinement (2026-11-23)

- Added a manual stop action to the 24-hour workflow. It marks the session inactive and preserves all records; scheduled cycles then stop collecting. Status remains read-only. A second start is rejected while the previous session or its exit-settlement grace period is active.
- Unverified manual CoinGecko ID overrides are excluded from the selected watchlist. They must be marked verified: true after independent identity confirmation.
