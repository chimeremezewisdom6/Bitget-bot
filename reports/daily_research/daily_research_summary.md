# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-25T19:34:33.985989+00:00
- Session ended UTC: not recorded
- Collector cycles: 1
- Distinct symbols observed: 260
- Current Bitget turnover-watchlist contracts: 122
- Market observation rows: 5400
- Candidate signals eligible for entry evaluation: 918
- Watch-only RSI conditions (no entry): 1467
- Two-snapshot order-book shadow outcomes: 7140
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 2321
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 654
- Breakout-based trend starts found: 10349 (LONG: 4617; SHORT: 5732)
- Average direction-matching candle share in first hour: 31.7%
- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 653
- Complete trend events with early-window measurements: 10273

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 10273 | 45.0% | 5470/10273 (53.2%) | 0.1038% |
| 10 | 10273 | 37.6% | 5497/10273 (53.5%) | 0.1172% |
| 15 | 10273 | 35.1% | 5522/10273 (53.8%) | 0.1235% |
| 20 | 10273 | 34.1% | 5398/10273 (52.5%) | 0.0946% |
| 30 | 10273 | 33.0% | 5269/10273 (51.3%) | 0.0668% |
| 60 | 10273 | 31.9% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 250
- LONG/SHORT ignition candidates (score at least 4/7): 40
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| ENSOUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 0.1984% | 0.8487% | 1.0685% | 1.392x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| BEATUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 0.6514% | 0.8234% | 0.8754% | 2.238x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| MEGAUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 0.3801% | 0.9317% | 0.9576% | 8.148x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| MANTAUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 0.2205% | 0.5809% | 1.2409% | 5.294x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PIEVERSEUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 1.5689% | 3.0179% | 2.2898% | 4.396x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CYSUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.1997% | 0.5007% | 0.7805% | 2.352x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CRVUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.4587% | 0.9798% | 1.0993% | 22.154x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| SAHARAUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.3408% | 0.7798% | 0.9459% | 4.364x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PLUMEUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.5556% | 0.6487% | -0.7862% | 2.386x | 3/1 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| GRASSUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.3011% | -0.3721% | 0.7954% | 7.035x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| BUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.2232% | 0.4474% | 0.4685% | 1.143x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| NEARUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.2424% | 0.6825% | 0.6722% | 1.766x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PEPEUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.3421% | 0.8641% | 1.5275% | 1.532x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PROMUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.8297% | 2.0228% | 0.6957% | 1.664x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| ARBUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.312% | -0.2498% | 0.7989% | 15.832x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| LISTAUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -4.1001% | -4.0083% | 0.1927% | 5.23x | 0/5 | NEW_POSITION_BUILDING_AGGREGATE |
| LTCUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2349% | 0.0943% | 0.5824% | 4.693x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| FARTCOINUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | 0.0% | 0.1727% | 0.536% | 1.749x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| XMRUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3968% | -0.6501% | 0.6295% | 1.041x | 0/5 | NEW_POSITION_BUILDING_AGGREGATE |
| FETUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | 0.2752% | 0.0% | 0.3754% | 7.63x | 3/1 | NO_CLEAR_OI_CONFIRMATION |
| LSKUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.4692% | 0.3347% | 0.7225% | 1.433x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PONSUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3696% | -0.6221% | 1.4063% | 1.305x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| PIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.3291% | 0.5129% | 0.7746% | 2.159x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| WIFUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | 0.1608% | 0.3221% | 1.0513% | 1.692x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CHIPUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.153% | -0.6091% | 0.5428% | 7.431x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| SKYAIUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.561% | -0.5316% | 0.1% | 3.504x | 0/4 | NEW_POSITION_BUILDING_AGGREGATE |
| BREVUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1702% | 0.1872% | 0.2499% | 13.335x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| STRKUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3163% | -0.4213% | 0.2552% | 4.087x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| BANKUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.4484% | 0.4484% | 1.4866% | 1.003x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PENDLEUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.6544% | -0.5433% | 0.6973% | 4.633x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| LABUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.2633% | 1.0282% | 1.9618% | 3.697x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| BEAMUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.5394% | 0.3325% | 0.8657% | 1.529x | 0/3 | NEW_POSITION_BUILDING_AGGREGATE |
| UAIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.0346% | 1.3665% | 1.3682% | 2.491x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| MAGICUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1649% | -0.1798% | 0.6614% | 2.509x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| SPACEUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1413% | 1.4891% | 1.3176% | 1.626x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PROSUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -1.1553% | -0.9485% | 0.5429% | 3.451x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| MANTRAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 4.6697% | 6.6688% | 7.5953% | 2.358x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| MOODENGUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.34% | -0.8122% | 0.6535% | 2.014x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| KAIAUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3564% | -0.8862% | -1.8579% | 0.126x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| USUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | 0.5205% | 0.7828% | 1.0421% | 1.574x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |

Scoring checks: aligned 5m/15m price acceleration, rising 15m OI, 5m turnover surge versus the prior 20m, directional candle pressure with real candle bodies, 20m breakout, 60m breakout, and higher-high/lower-low structure. Scores are evidence counts, not probabilities. A high score is a research watch candidate, not a buy/sell instruction. Rising aggregate OI means total outstanding positions increased; it does not reveal whether longs or shorts initiated them.

| Symbol | Direction | Trend start (UTC) | Green | Red | Doji | Matching candles | Matching % | First-hour follow-through % |
|---|---|---|---:|---:|---:|---:|---:|---:|
| EVAAUSDT | SHORT | 2026-11-24 03:44 | 19 | 41 | 0 | 41 / 60 | 68.33% | -1.3488%
| SKYUSDT | SHORT | 2026-11-23 07:49 | 17 | 40 | 3 | 40 / 60 | 66.67% | 6.3317%
| SOLUSDT | LONG | 2026-11-24 22:04 | 40 | 20 | 0 | 40 / 60 | 66.67% | 0.3963%
| PROSUSDT | LONG | 2026-11-25 06:48 | 40 | 20 | 0 | 40 / 60 | 66.67% | 11.0494%
| PROMUSDT | LONG | 2026-11-23 14:10 | 39 | 21 | 0 | 39 / 60 | 65.0% | 12.4267%
| PROMUSDT | LONG | 2026-11-23 14:10 | 39 | 21 | 0 | 39 / 60 | 65.0% | 12.4267%
| EVAAUSDT | SHORT | 2026-11-25 01:53 | 20 | 39 | 1 | 39 / 60 | 65.0% | 3.5352%
| PONSUSDT | LONG | 2026-11-25 16:54 | 39 | 21 | 0 | 39 / 60 | 65.0% | 5.3471%
| CYSUSDT | LONG | 2026-11-23 16:29 | 38 | 22 | 0 | 38 / 60 | 63.33% | 10.4336%
| CYSUSDT | LONG | 2026-11-23 16:29 | 38 | 22 | 0 | 38 / 60 | 63.33% | 10.4336%
| XMRUSDT | LONG | 2026-11-24 03:37 | 38 | 18 | 4 | 38 / 60 | 63.33% | 1.7838%
| LABUSDT | LONG | 2026-11-23 13:56 | 38 | 22 | 0 | 38 / 60 | 63.33% | 4.0981%
| UAIUSDT | LONG | 2026-11-23 13:57 | 38 | 22 | 0 | 38 / 60 | 63.33% | 3.1938%
| INITUSDT | SHORT | 2026-11-25 18:23 | 21 | 38 | 1 | 38 / 60 | 63.33% | 1.2657%
| CYSUSDT | LONG | 2026-11-25 01:58 | 38 | 21 | 1 | 38 / 60 | 63.33% | 1.6903%
| HYPEUSDT | LONG | 2026-11-23 08:05 | 37 | 22 | 1 | 37 / 60 | 61.67% | 0.6854%
| ENAUSDT | SHORT | 2026-11-23 01:45 | 22 | 37 | 1 | 37 / 60 | 61.67% | 1.0189%
| TAOUSDT | SHORT | 2026-11-23 01:07 | 19 | 37 | 4 | 37 / 60 | 61.67% | 0.3284%
| TAOUSDT | SHORT | 2026-11-23 12:21 | 20 | 37 | 3 | 37 / 60 | 61.67% | 0.7265%
| BCHUSDT | LONG | 2026-11-23 14:25 | 37 | 23 | 0 | 37 / 60 | 61.67% | -0.2928%
| PONSUSDT | LONG | 2026-11-23 04:47 | 37 | 23 | 0 | 37 / 60 | 61.67% | 0.1246%
| BTWUSDT | SHORT | 2026-11-23 08:48 | 23 | 37 | 0 | 37 / 60 | 61.67% | 1.2253%
| MUBARAKUSDT | LONG | 2026-11-23 07:48 | 37 | 18 | 5 | 37 / 60 | 61.67% | 6.7039%
| TRXUSDT | LONG | 2026-11-23 13:50 | 37 | 21 | 2 | 37 / 60 | 61.67% | 1.037%
| LISTAUSDT | LONG | 2026-11-23 14:02 | 37 | 15 | 8 | 37 / 60 | 61.67% | 10.7115%
| HYPEUSDT | SHORT | 2026-11-24 09:54 | 23 | 37 | 0 | 37 / 60 | 61.67% | 0.499%
| EVAAUSDT | SHORT | 2026-11-24 02:34 | 23 | 37 | 0 | 37 / 60 | 61.67% | 13.2311%
| EVAAUSDT | LONG | 2026-11-24 04:48 | 37 | 23 | 0 | 37 / 60 | 61.67% | -1.2676%
| LISTAUSDT | LONG | 2026-11-23 14:02 | 37 | 15 | 8 | 37 / 60 | 61.67% | 10.7115%
| FARTCOINUSDT | LONG | 2026-11-23 13:55 | 37 | 23 | 0 | 37 / 60 | 61.67% | 6.6959%
| HYPEUSDT | LONG | 2026-11-25 16:25 | 37 | 23 | 0 | 37 / 60 | 61.67% | 2.3505%
| EVAAUSDT | LONG | 2026-11-25 09:38 | 37 | 23 | 0 | 37 / 60 | 61.67% | 8.8695%
| BLESSUSDT | SHORT | 2026-11-25 16:12 | 22 | 37 | 1 | 37 / 60 | 61.67% | 3.6164%
| PIEVERSEUSDT | SHORT | 2026-11-25 07:39 | 23 | 37 | 0 | 37 / 60 | 61.67% | 1.4411%
| OPGUSDT | LONG | 2026-11-25 15:33 | 37 | 20 | 3 | 37 / 60 | 61.67% | 2.6731%
| TAOUSDT | LONG | 2026-11-25 16:56 | 37 | 22 | 1 | 37 / 60 | 61.67% | 3.3353%
| BCHUSDT | LONG | 2026-11-25 16:57 | 37 | 22 | 1 | 37 / 60 | 61.67% | 2.486%
| FILUSDT | LONG | 2026-11-25 16:25 | 37 | 23 | 0 | 37 / 60 | 61.67% | 2.6985%
| BTCUSDT | SHORT | 2026-11-23 17:41 | 24 | 36 | 0 | 36 / 60 | 60.0% | 0.2298%
| SOLUSDT | SHORT | 2026-11-23 01:47 | 24 | 36 | 0 | 36 / 60 | 60.0% | 0.461%
| HYPEUSDT | LONG | 2026-11-23 13:26 | 36 | 24 | 0 | 36 / 60 | 60.0% | 7.9029%
| EVAAUSDT | SHORT | 2026-11-23 15:25 | 24 | 36 | 0 | 36 / 60 | 60.0% | -0.4704%
| PROMUSDT | LONG | 2026-11-23 09:56 | 36 | 24 | 0 | 36 / 60 | 60.0% | 20.2309%
| ARIAUSDT | SHORT | 2026-11-23 14:41 | 24 | 36 | 0 | 36 / 60 | 60.0% | 4.8708%
| QNTUSDT | LONG | 2026-11-23 08:08 | 36 | 22 | 2 | 36 / 60 | 60.0% | 2.0614%
| FILUSDT | LONG | 2026-11-23 05:14 | 36 | 20 | 4 | 36 / 60 | 60.0% | 1.3266%
| RENDERUSDT | SHORT | 2026-11-23 15:09 | 23 | 36 | 1 | 36 / 60 | 60.0% | 0.4643%
| LSKUSDT | LONG | 2026-11-23 13:59 | 36 | 22 | 2 | 36 / 60 | 60.0% | 5.6173%
| HBARUSDT | SHORT | 2026-11-23 18:29 | 18 | 36 | 6 | 36 / 60 | 60.0% | 1.3016%
| FLOCKUSDT | SHORT | 2026-11-23 17:41 | 22 | 36 | 2 | 36 / 60 | 60.0% | 9.635%
| BTCUSDT | SHORT | 2026-11-23 17:41 | 24 | 36 | 0 | 36 / 60 | 60.0% | 0.2298%
| ETHUSDT | SHORT | 2026-11-24 01:50 | 24 | 36 | 0 | 36 / 60 | 60.0% | 1.0024%
| ETHUSDT | LONG | 2026-11-24 04:08 | 36 | 24 | 0 | 36 / 60 | 60.0% | 0.3842%
| HYPEUSDT | LONG | 2026-11-23 13:55 | 36 | 24 | 0 | 36 / 60 | 60.0% | 4.7575%
| PEPEUSDT | LONG | 2026-11-24 00:19 | 36 | 22 | 2 | 36 / 60 | 60.0% | 1.288%
| PEPEUSDT | SHORT | 2026-11-24 02:22 | 24 | 36 | 0 | 36 / 60 | 60.0% | 0.3615%
| EVAAUSDT | SHORT | 2026-11-23 15:25 | 24 | 36 | 0 | 36 / 60 | 60.0% | -0.4704%
| RENDERUSDT | SHORT | 2026-11-23 15:09 | 23 | 36 | 1 | 36 / 60 | 60.0% | 0.4643%
| FARTCOINUSDT | SHORT | 2026-11-24 07:35 | 19 | 36 | 5 | 36 / 60 | 60.0% | 1.2365%
| PROSUSDT | LONG | 2026-11-24 11:02 | 36 | 23 | 1 | 36 / 60 | 60.0% | 5.4634%
| HBARUSDT | SHORT | 2026-11-23 18:29 | 18 | 36 | 6 | 36 / 60 | 60.0% | 1.3016%
| FLOCKUSDT | SHORT | 2026-11-23 17:41 | 22 | 36 | 2 | 36 / 60 | 60.0% | 9.635%
| LSKUSDT | LONG | 2026-11-23 13:59 | 36 | 22 | 2 | 36 / 60 | 60.0% | 5.6173%
| DGAIUSDT | LONG | 2026-11-24 11:25 | 36 | 23 | 1 | 36 / 60 | 60.0% | 1.3522%
| USELESSUSDT | LONG | 2026-11-24 00:15 | 36 | 21 | 3 | 36 / 60 | 60.0% | 1.7788%
| TRXUSDT | LONG | 2026-11-23 13:55 | 36 | 22 | 2 | 36 / 60 | 60.0% | 0.9622%
| INITUSDT | SHORT | 2026-11-23 19:57 | 23 | 36 | 1 | 36 / 60 | 60.0% | 2.2959%
| MAGMAUSDT | SHORT | 2026-11-24 01:06 | 23 | 36 | 1 | 36 / 60 | 60.0% | 0.2651%
| MYXUSDT | LONG | 2026-11-23 13:55 | 36 | 23 | 1 | 36 / 60 | 60.0% | 6.5704%
| MANTAUSDT | LONG | 2026-11-25 07:53 | 36 | 13 | 11 | 36 / 60 | 60.0% | 9.0723%
| ETHUSDT | SHORT | 2026-11-24 23:11 | 23 | 36 | 1 | 36 / 60 | 60.0% | 0.4291%
| ZECUSDT | LONG | 2026-11-25 03:20 | 36 | 24 | 0 | 36 / 60 | 60.0% | 0.2881%
| HYPEUSDT | SHORT | 2026-11-25 00:00 | 24 | 36 | 0 | 36 / 60 | 60.0% | 1.238%
| HYPEUSDT | SHORT | 2026-11-25 13:45 | 24 | 36 | 0 | 36 / 60 | 60.0% | 1.6024%
| PEPEUSDT | SHORT | 2026-11-25 12:37 | 23 | 36 | 1 | 36 / 60 | 60.0% | 2.2481%
| LISTAUSDT | LONG | 2026-11-25 06:54 | 36 | 24 | 0 | 36 / 60 | 60.0% | 8.6771%
| PIEVERSEUSDT | SHORT | 2026-11-25 00:42 | 24 | 36 | 0 | 36 / 60 | 60.0% | 2.3168%
| BNBUSDT | LONG | 2026-11-25 16:21 | 36 | 24 | 0 | 36 / 60 | 60.0% | 0.7472%
| SKYAIUSDT | LONG | 2026-11-25 03:49 | 36 | 24 | 0 | 36 / 60 | 60.0% | 4.4003%
| SKYAIUSDT | LONG | 2026-11-25 05:04 | 36 | 22 | 2 | 36 / 60 | 60.0% | 3.2892%
| BTWUSDT | LONG | 2026-11-25 05:46 | 36 | 24 | 0 | 36 / 60 | 60.0% | 2.0053%
| BTWUSDT | LONG | 2026-11-25 06:49 | 36 | 24 | 0 | 36 / 60 | 60.0% | 5.9231%
| XPLUSDT | LONG | 2026-11-25 16:55 | 36 | 22 | 2 | 36 / 60 | 60.0% | 4.4929%
| MONUSDT | LONG | 2026-11-25 02:34 | 36 | 18 | 6 | 36 / 60 | 60.0% | 3.8257%
| PENGUUSDT | SHORT | 2026-11-25 14:34 | 22 | 36 | 2 | 36 / 60 | 60.0% | -0.7404%
| MANTAUSDT | LONG | 2026-11-25 07:53 | 36 | 13 | 11 | 36 / 60 | 60.0% | 9.0723%
| USUSDT | LONG | 2026-11-25 16:50 | 36 | 22 | 2 | 36 / 60 | 60.0% | 5.7262%
| BTCUSDT | SHORT | 2026-11-23 13:52 | 25 | 35 | 0 | 35 / 60 | 58.33% | -2.599%
| SOLUSDT | LONG | 2026-11-22 21:49 | 35 | 24 | 1 | 35 / 60 | 58.33% | -0.525%
| EVAAUSDT | SHORT | 2026-11-23 12:33 | 25 | 35 | 0 | 35 / 60 | 58.33% | -0.389%
| EVAAUSDT | SHORT | 2026-11-23 17:05 | 25 | 35 | 0 | 35 / 60 | 58.33% | 2.8532%
| PIEVERSEUSDT | LONG | 2026-11-22 23:41 | 35 | 25 | 0 | 35 / 60 | 58.33% | 0.6704%
| PIEVERSEUSDT | LONG | 2026-11-23 16:11 | 35 | 25 | 0 | 35 / 60 | 58.33% | 5.1775%
| BLESSUSDT | LONG | 2026-11-23 08:25 | 35 | 25 | 0 | 35 / 60 | 58.33% | -0.1996%
| ACEUSDT | SHORT | 2026-11-23 02:16 | 22 | 35 | 3 | 35 / 60 | 58.33% | 14.2173%
| SKYUSDT | SHORT | 2026-11-23 15:27 | 21 | 35 | 4 | 35 / 60 | 58.33% | 1.8896%
| XLMUSDT | SHORT | 2026-11-23 16:46 | 25 | 35 | 0 | 35 / 60 | 58.33% | 0.923%
| VVVUSDT | SHORT | 2026-11-23 11:41 | 19 | 35 | 6 | 35 / 60 | 58.33% | 1.23%
| IDOLUSDT | LONG | 2026-11-22 21:36 | 35 | 25 | 0 | 35 / 60 | 58.33% | 2.3276%
| IDOLUSDT | LONG | 2026-11-23 06:10 | 35 | 25 | 0 | 35 / 60 | 58.33% | -0.2609%

## Mandatory 60-minute same-colour candle experiment

Each eligible symbol is checked up to five separate times. Every check uses the latest 60 fully closed one-minute candles; green and red candles are counted separately, doji candles count toward neither colour, and a result qualifies when either colour reaches at least 40. This is a research filter, not a trade instruction.

| Symbol | Checks recorded | Latest colour | Same-colour count | Qualified |
|---|---:|---|---:|---|
| 0GUSDT | 10 | GREEN | 17 | No |
| 1000BONKUSDT | 11 | GREEN | 20 | No |
| 1000SATSUSDT | 1 | GREEN | 14 | No |
| 2ZUSDT | 5 | GREEN | 11 | No |
| AAVEUSDT | 11 | GREEN | 33 | No |
| ACEUSDT | 11 | GREEN | 21 | No |
| ACUUSDT | 9 | RED | 4 | No |
| ADAUSDT | 11 | GREEN | 29 | No |
| AEONUSDT | 11 | GREEN | 19 | No |
| AEROUSDT | 11 | RED | 21 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AIXBTUSDT | 3 | GREEN | 15 | No |
| AKEUSDT | 11 | GREEN | 33 | No |
| ALGOUSDT | 11 | GREEN | 26 | No |
| ALICEUSDT | 3 | GREEN | 2 | No |
| ALLOUSDT | 11 | GREEN | 29 | No |
| ALTUSDT | 4 | RED | 11 | No |
| AMDLUSDT | 11 | GREEN | 21 | No |
| APRUSDT | 11 | GREEN | 5 | No |
| APTUSDT | 11 | GREEN | 33 | No |
| ARBUSDT | 11 | GREEN | 34 | No |
| ARIAUSDT | 11 | RED | 29 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARTYUSDT | 1 | GREEN | 14 | No |
| ARUSDT | 11 | RED | 16 | No |
| ARXUSDT | 11 | GREEN | 22 | No |
| ASTERUSDT | 11 | GREEN | 25 | No |
| ATOMUSDT | 11 | GREEN | 26 | No |
| ATUSDT | 11 | GREEN | 27 | No |
| AVAXUSDT | 11 | GREEN | 30 | No |
| AXISUSDT | 11 | RED | 21 | No |
| BABYUSDT | 11 | RED | 12 | No |
| BANKUSDT | 11 | GREEN | 23 | No |
| BARDUSDT | 11 | RED | 11 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 11 | GREEN | 38 | No |
| BEAMUSDT | 11 | GREEN | 12 | No |
| BEATUSDT | 11 | GREEN | 30 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 11 | GREEN | 20 | No |
| BIGTIMEUSDT | 4 | GREEN | 29 | No |
| BLESSUSDT | 11 | GREEN | 33 | No |
| BLURUSDT | 11 | RED | 30 | No |
| BNBUSDT | 11 | GREEN | 30 | No |
| BOMEUSDT | 11 | GREEN | 18 | No |
| BREVUSDT | 11 | GREEN | 7 | No |
| BRUSDT | 6 | GREEN | 18 | No |
| BTCUSDT | 11 | GREEN | 31 | No |
| BTWUSDT | 11 | RED | 32 | No |
| BUSDT | 5 | GREEN | 9 | No |
| CAKEUSDT | 4 | GREEN | 9 | No |
| CAPUSDT | 9 | GREEN | 10 | No |
| CFGUSDT | 11 | GREEN | 22 | No |
| CHIPUSDT | 11 | GREEN | 23 | No |
| CLSUSDT | 11 | GREEN | 22 | No |
| COOKIEUSDT | 7 | RED | 4 | No |
| CPUSDT | 10 | RED | 20 | No |
| CROSSUSDT | 11 | GREEN | 9 | No |
| CRVUSDT | 11 | GREEN | 27 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 11 | GREEN | 27 | No |
| CYBERUSDT | 11 | GREEN | 21 | No |
| CYSUSDT | 11 | GREEN | 26 | No |
| DASHUSDT | 7 | RED | 10 | No |
| DEXEUSDT | 11 | GREEN | 24 | No |
| DGAIUSDT | 11 | GREEN | 16 | No |
| DOGEUSDT | 11 | GREEN | 33 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 11 | GREEN | 29 | No |
| DOTUSDT | 11 | GREEN | 21 | No |
| EDGEUSDT | 6 | GREEN | 25 | No |
| EGLDUSDT | 6 | RED | 9 | No |
| EIGENUSDT | 9 | RED | 12 | No |
| ELICEUSDT | 8 | GREEN | 5 | No |
| ELSAUSDT | 11 | RED | 22 | No |
| ENAUSDT | 11 | GREEN | 33 | No |
| ENSOUSDT | 11 | GREEN | 19 | No |
| ENSUSDT | 9 | RED | 11 | No |
| ERAUSDT | 11 | RED | 24 | No |
| ETCUSDT | 11 | GREEN | 31 | No |
| ETHFIUSDT | 11 | GREEN | 20 | No |
| ETHUSDT | 11 | GREEN | 31 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 11 | RED | 36 | No |
| FARTCOINUSDT | 11 | GREEN | 32 | No |
| FCXUSDT | 10 | GREEN | 5 | No |
| FETUSDT | 11 | GREEN | 20 | No |
| FFUSDT | 6 | RED | 7 | No |
| FILUSDT | 11 | GREEN | 31 | No |
| FLOCKUSDT | 8 | GREEN | 9 | No |
| FLOKIUSDT | 11 | GREEN | 19 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 11 | GREEN | 18 | No |
| GPSUSDT | 8 | GREEN | 6 | No |
| GRAMUSDT | 11 | GREEN | 24 | No |
| GRASSUSDT | 11 | GREEN | 28 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 11 | GREEN | 13 | No |
| GWEIUSDT | 11 | RED | 11 | No |
| HBARUSDT | 11 | GREEN | 35 | No |
| HPQUSDT | 4 | GREEN | 19 | No |
| HUMAUSDT | 11 | GREEN | 10 | No |
| HUSDT | 10 | RED | 21 | No |
| HYPEUSDT | 11 | GREEN | 34 | No |
| ICNTUSDT | 11 | GREEN | 24 | No |
| ICPUSDT | 11 | GREEN | 26 | No |
| IDOLUSDT | 11 | RED | 25 | No |
| INFYUSDT | 2 | RED | 11 | No |
| INITUSDT | 11 | RED | 34 | No |
| INJUSDT | 11 | GREEN | 33 | No |
| INXUSDT | 11 | GREEN | 16 | No |
| IOSTUSDT | 10 | RED | 16 | No |
| IRYSUSDT | 11 | GREEN | 22 | No |
| JCTUSDT | 11 | GREEN | 29 | No |
| JNJUSDT | 8 | RED | 10 | No |
| JTOUSDT | 10 | RED | 11 | No |
| JUPUSDT | 11 | GREEN | 30 | No |
| KAIAUSDT | 1 | GREEN | 13 | No |
| KAITOUSDT | 11 | GREEN | 21 | No |
| KASUSDT | 11 | GREEN | 26 | No |
| KAVAUSDT | 9 | RED | 12 | No |
| KERNELUSDT | 11 | GREEN | 4 | No |
| KGENUSDT | 9 | GREEN | 18 | No |
| KITEUSDT | 11 | GREEN | 19 | No |
| KUAISHOUUSDT | 11 | GREEN | 9 | No |
| LABUSDT | 11 | GREEN | 28 | No |
| LAUSDT | 7 | RED | 13 | No |
| LAYERUSDT | 1 | GREEN | 7 | No |
| LDOUSDT | 11 | GREEN | 20 | No |
| LINKUSDT | 11 | GREEN | 34 | No |
| LISTAUSDT | 11 | RED | 33 | No |
| LITUSDT | 11 | GREEN | 26 | No |
| LSKUSDT | 11 | RED | 12 | No |
| LTCUSDT | 11 | GREEN | 32 | No |
| LUNCUSDT | 11 | GREEN | 19 | No |
| MAGICUSDT | 10 | GREEN | 22 | No |
| MAGMAUSDT | 9 | RED | 16 | No |
| MANTAUSDT | 3 | GREEN | 18 | No |
| MANTRAUSDT | 5 | GREEN | 33 | No |
| MARSCOINUSDT | 11 | GREEN | 6 | No |
| MDTUSDT | 2 | GREEN | 3 | No |
| MEGAUSDT | 11 | GREEN | 25 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 7 | RED | 4 | No |
| MEUSDT | 9 | GREEN | 19 | No |
| MMTUSDT | 11 | GREEN | 33 | No |
| MONUSDT | 11 | GREEN | 31 | No |
| MOODENGUSDT | 3 | GREEN | 28 | No |
| MORPHOUSDT | 8 | GREEN | 19 | No |
| MOVEUSDT | 3 | GREEN | 28 | No |
| MOVRUSDT | 3 | GREEN | 19 | No |
| MSUSDT | 7 | RED | 6 | No |
| MUBARAKUSDT | 11 | GREEN | 26 | No |
| MUSDT | 1 | GREEN | 18 | No |
| MYXUSDT | 10 | GREEN | 20 | No |
| NAORISUSDT | 11 | GREEN | 17 | No |
| NEARUSDT | 11 | GREEN | 36 | No |
| NEMUSDT | 7 | RED | 8 | No |
| NIGHTUSDT | 11 | RED | 29 | No |
| NILUSDT | 10 | GREEN | 12 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 11 | GREEN | 34 | No |
| ONEUSDT | 8 | GREEN | 20 | No |
| ONGUSDT | 11 | GREEN | 16 | No |
| OPGUSDT | 9 | GREEN | 32 | No |
| OPUSDT | 11 | GREEN | 16 | No |
| ORCAUSDT | 11 | GREEN | 14 | No |
| ORDERUSDT | 6 | GREEN | 10 | No |
| ORDIUSDT | 11 | GREEN | 21 | No |
| OUSDT | 2 | GREEN | 19 | No |
| PBRUSDT | 8 | RED | 5 | No |
| PENDLEUSDT | 11 | GREEN | 30 | No |
| PENGUUSDT | 11 | GREEN | 26 | No |
| PEOPLEUSDT | 10 | GREEN | 24 | No |
| PEPEUSDT | 11 | GREEN | 33 | No |
| PHAUSDT | 8 | GREEN | 21 | No |
| PIEVERSEUSDT | 11 | GREEN | 36 | No |
| PIPPINUSDT | 11 | GREEN | 28 | No |
| PIUSDT | 11 | GREEN | 23 | No |
| PLUMEUSDT | 11 | GREEN | 19 | No |
| PNUTUSDT | 3 | GREEN | 18 | No |
| POLUSDT | 11 | GREEN | 20 | No |
| PONSUSDT | 11 | GREEN | 29 | No |
| POPCATUSDT | 1 | RED | 16 | No |
| POWERUSDT | 9 | GREEN | 26 | No |
| PROMUSDT | 11 | GREEN | 31 | No |
| PROSUSDT | 7 | GREEN | 20 | No |
| PUMPUSDT | 11 | GREEN | 30 | No |
| PYTHUSDT | 11 | GREEN | 24 | No |
| QNTUSDT | 11 | GREEN | 33 | No |
| QUSDT | 9 | RED | 19 | No |
| RAREUSDT | 11 | GREEN | 14 | No |
| RAVEUSDT | 10 | RED | 13 | No |
| RAYUSDT | 11 | GREEN | 24 | No |
| RENDERUSDT | 11 | GREEN | 31 | No |
| REUSDT | 11 | GREEN | 21 | No |
| RIVERUSDT | 11 | GREEN | 21 | No |
| RPLUSDT | 10 | RED | 5 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 11 | GREEN | 21 | No |
| SANDUSDT | 11 | GREEN | 31 | No |
| SAPIENUSDT | 9 | RED | 12 | No |
| SEIUSDT | 11 | GREEN | 30 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHELLUSDT | 4 | RED | 12 | No |
| SHIBUSDT | 11 | GREEN | 31 | No |
| SIRENUSDT | 4 | GREEN | 11 | No |
| SKYAIUSDT | 11 | GREEN | 24 | No |
| SKYUSDT | 11 | GREEN | 24 | No |
| SLXUSDT | 4 | RED | 28 | No |
| SOLUSDT | 11 | GREEN | 33 | No |
| SOONUSDT | 10 | RED | 13 | No |
| SOPHUSDT | 2 | GREEN | 9 | No |
| SPACEUSDT | 8 | GREEN | 16 | No |
| SPKUSDT | 9 | GREEN | 8 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 9 | RED | 14 | No |
| SSVUSDT | 1 | GREEN | 34 | No |
| STONKUSDT | 2 | GREEN | 20 | No |
| STRKUSDT | 11 | GREEN | 31 | No |
| STXUSDT | 11 | GREEN | 25 | No |
| SUIUSDT | 11 | GREEN | 31 | No |
| SYNUSDT | 1 | RED | 15 | No |
| TAOUSDT | 11 | GREEN | 37 | No |
| TIAUSDT | 11 | GREEN | 29 | No |
| TRBUSDT | 5 | GREEN | 18 | No |
| TRUMPUSDT | 11 | GREEN | 38 | No |
| TRXUSDT | 11 | RED | 20 | No |
| TUSDT | 1 | GREEN | 18 | No |
| TUTUSDT | 10 | GREEN | 14 | No |
| UAIUSDT | 11 | GREEN | 34 | No |
| UBUSDT | 5 | RED | 13 | No |
| UNITASUSDT | 11 | GREEN | 11 | No |
| UNIUSDT | 11 | GREEN | 32 | No |
| USDBRLUSDT | 11 | RED | 15 | No |
| USDJPYUSDT | 10 | GREEN | 5 | No |
| USELESSUSDT | 11 | GREEN | 29 | No |
| USUALUSDT | 11 | RED | 15 | No |
| USUSDT | 1 | GREEN | 35 | No |
| VELVETUSDT | 11 | GREEN | 9 | No |
| VIRTUALUSDT | 11 | GREEN | 25 | No |
| VVVUSDT | 11 | GREEN | 35 | No |
| WAXPUSDT | 3 | GREEN | 18 | No |
| WIFUSDT | 11 | GREEN | 29 | No |
| WLDUSDT | 11 | GREEN | 30 | No |
| WLFIUSDT | 11 | RED | 22 | No |
| XLMUSDT | 11 | GREEN | 34 | No |
| XMRUSDT | 11 | RED | 32 | No |
| XPLUSDT | 11 | GREEN | 36 | No |
| XRPUSDT | 11 | GREEN | 32 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZBTUSDT | 2 | RED | 17 | No |
| ZECUSDT | 11 | GREEN | 33 | No |
| ZENUSDT | 7 | RED | 9 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZKUSDT | 4 | GREEN | 10 | No |
| ZROUSDT | 11 | GREEN | 26 | No |
| 牛来USDT | 11 | GREEN | 16 | No |
| 龙虾USDT | 11 | GREEN | 9 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 50 | 388 |
| $1m–$10m 24h futures turnover | 50 | 407 |
| $10m–$100m 24h futures turnover | 17 | 215 |
| $100m+ 24h futures turnover | 5 | 75 |

## Profit-versus-loss summary (hypothetical book-walk outcomes)

- Positive outcomes: 2678; negative outcomes: 4462; flat: 0
- Win rate among scored outcomes: 37.5%
- Gross positive outcomes: 19470.610720 USDT
- Gross negative outcomes: 36338.424649 USDT
- Total estimated net after trading fees: -16867.813930 USDT
- Profit factor (gross gains / gross losses): 0.536
- Average winning outcome: 7.270579 USDT
- Average losing outcome: -8.143977 USDT
- Mean estimated net result: -42.65 bps

These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.

- Ticker-only reference outcomes (separate, not executable): 0

## Strategy breakdown

| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |
|---|---:|---:|---:|---:|
| breakdown | 1206 | 567 | 639 | -12.70 |
| breakout | 627 | 112 | 515 | -62.30 |
| ema_volume | 5307 | 1999 | 3308 | -47.14 |

## Legacy Trader discussion records

Older trader discussion records, if present in the repository, are historical and unverified. The Bitget-only collector does not fetch, update or use them in research conclusions.

## Limitations

- The collector uses Bitget USDT perpetual market endpoints only. It samples the highest-turnover eligible contracts plus selected contracts from the current provisional four-band watchlist; market capitalisation is not inferred from ticker symbols.
- Bitget futures endpoints do not provide circulating market cap; this report groups coins by Bitget 24h futures turnover instead.
- GitHub scheduled runs may be delayed or skipped; cycles and timestamps show actual collection, not guaranteed continuous monitoring.
- Funding is not included in the automatic short-horizon net P&L. Fees are estimated from instrument metadata and may differ from the account's actual fee tier.
- Any ticker-only legacy outcomes are reference-price calculations and are kept separate from two-snapshot order-book shadow outcomes.
- Small samples, repeated signals, correlated coins and changing regimes can distort apparent performance.
- No Demo or Live orders were placed.

## Research files

- market_observations.jsonl — timestamped ticker/order-book summaries.
- candles_1m.jsonl — de-duplicated one-minute candles.
- trend_first_hour_backtest.jsonl — rolling 24-hour breakout trend starts and first-hour candle-colour counts.
- trend_early_window_backtest.jsonl — separate 5/10/15/20/30/60-minute candle-window measurements and continuation outcomes.
- trend_ignition.jsonl — per-cycle LONG/SHORT trend-development scores combining Bitget 1m candle structure, turnover acceleration and historical 5m open interest.
- shadow_experiments.jsonl — signals, partial entry/exit records, book-walk outcomes and unavailable evaluations.
- collection_errors.jsonl — Bitget API and processing failures.
