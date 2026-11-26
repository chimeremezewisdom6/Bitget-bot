# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-25T19:34:33.985989+00:00
- Session ended UTC: not recorded
- Collector cycles: 2
- Distinct symbols observed: 261
- Current Bitget turnover-watchlist contracts: 122
- Market observation rows: 5600
- Candidate signals eligible for entry evaluation: 952
- Watch-only RSI conditions (no entry): 1556
- Two-snapshot order-book shadow outcomes: 7455
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 2521
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 666
- Breakout-based trend starts found: 10531 (LONG: 4714; SHORT: 5817)
- Average direction-matching candle share in first hour: 31.6%
- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 665
- Complete trend events with early-window measurements: 10455

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 10455 | 44.9% | 5561/10455 (53.2%) | 0.1052% |
| 10 | 10455 | 37.5% | 5589/10455 (53.5%) | 0.1185% |
| 15 | 10455 | 35.0% | 5609/10455 (53.6%) | 0.1231% |
| 20 | 10455 | 34.0% | 5494/10455 (52.5%) | 0.0946% |
| 30 | 10455 | 32.8% | 5366/10455 (51.3%) | 0.0679% |
| 60 | 10455 | 31.7% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 251
- LONG/SHORT ignition candidates (score at least 4/7): 40
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| ELSAUSDT | LONG | 7 / 7 | IGNITION_CANDIDATE | 0.4652% | 1.3354% | 0.9502% | 1.595x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CFGUSDT | LONG | 7 / 7 | IGNITION_CANDIDATE | 0.8075% | 1.9048% | 4.4226% | 1.386x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| QNTUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 0.1775% | 0.7207% | 0.7311% | 0.147x | 4/0 | NEW_POSITION_BUILDING_AGGREGATE |
| DOSUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 1.0013% | 1.503% | 1.8745% | 0.771x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| ICPUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.1479% | 0.7437% | 0.6894% | 1.248x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| SAHARAUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.3279% | 0.6385% | 0.9984% | 15.65x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| 牛来USDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.7807% | 1.8632% | 5.7782% | 0.615x | 4/0 | NEW_POSITION_BUILDING_AGGREGATE |
| PONSUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.2815% | 1.4118% | 1.9795% | 1.356x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ETCUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.1004% | 0.5884% | 0.5416% | 1.573x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| HUMAUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.8208% | 1.2363% | 0.7011% | 0.451x | 5/0 | NEW_POSITION_BUILDING_AGGREGATE |
| RAREUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.4996% | 0.7513% | 0.6232% | 2.86x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| ALLOUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.1446% | 0.6296% | 0.4648% | 1.256x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| 1000SATSUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.1361% | 0.4093% | 0.6938% | 0.756x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| TUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.4104% | 0.5135% | 0.5026% | 1.028x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| BTCUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1016% | 0.215% | 0.6798% | 1.03x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ETHUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.0012% | 0.1817% | 0.2653% | 1.527x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ENAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1757% | 0.5586% | 0.527% | 0.934x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| BNBUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.0018% | 0.2153% | 0.2631% | 0.817x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| INJUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.293% | 0.9502% | 0.1581% | 8.014x | 5/0 | NEW_POSITION_BUILDING_AGGREGATE |
| VVVUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2196% | -0.6955% | -0.7913% | 1.118x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| PENGUUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1353% | 0.6576% | 0.6947% | 12.253x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| SEIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.2612% | 0.9643% | 0.9247% | 0.343x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| HBARUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.3552% | 0.8643% | 7.4201% | 28.37x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| CYBERUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.2845% | 0.4274% | 0.4023% | 2.627x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| KASUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1117% | 1.5873% | 1.141% | 0.902x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| CTUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.4837% | 0.4613% | 1.3176% | 1.23x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| WIFUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.6829% | 1.2977% | 1.9431% | 2.284x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| XPLUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1883% | -0.1883% | 0.1976% | 0.606x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| BREVUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1702% | 0.1872% | 0.2499% | 13.335x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| USUALUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.4409% | 0.7073% | 0.799% | 6.413x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| STXUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1897% | 0.5329% | 0.5258% | 0.943x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| GWEIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.5176% | 0.5176% | 0.3106% | 5.329x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| KAITOUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1873% | 0.5639% | 1.1748% | 3.387x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| BEAMUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1861% | 0.3106% | 0.5277% | 2.928x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| FLOKIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1792% | 0.4192% | 0.2922% | 2.677x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| UAIUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3413% | -0.6465% | -0.5579% | 0.103x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| ARXUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2283% | 0.0866% | 0.2847% | 8.07x | 0/3 | NEW_POSITION_BUILDING_AGGREGATE |
| BIGTIMEUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2445% | -0.2771% | 0.3379% | 0.218x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| SLXUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.695% | 0.9875% | 2.5074% | 0.793x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| KAIAUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3564% | -0.8862% | -1.8579% | 0.126x | 0/2 | NO_CLEAR_OI_CONFIRMATION |

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
| 0GUSDT | 11 | GREEN | 21 | No |
| 1000BONKUSDT | 12 | GREEN | 14 | No |
| 1000SATSUSDT | 2 | RED | 8 | No |
| 2ZUSDT | 6 | GREEN | 10 | No |
| AAVEUSDT | 12 | GREEN | 28 | No |
| ACEUSDT | 12 | RED | 33 | No |
| ACUUSDT | 9 | RED | 4 | No |
| ADAUSDT | 12 | GREEN | 23 | No |
| AEONUSDT | 11 | GREEN | 19 | No |
| AEROUSDT | 12 | GREEN | 10 | No |
| AGLDUSDT | 1 | RED | 5 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AIXBTUSDT | 3 | GREEN | 15 | No |
| AKEUSDT | 12 | RED | 38 | No |
| ALGOUSDT | 12 | GREEN | 16 | No |
| ALICEUSDT | 4 | RED | 9 | No |
| ALLOUSDT | 12 | GREEN | 21 | No |
| ALTUSDT | 4 | RED | 11 | No |
| AMDLUSDT | 12 | RED | 30 | No |
| APRUSDT | 12 | GREEN | 13 | No |
| APTUSDT | 12 | GREEN | 29 | No |
| ARBUSDT | 12 | GREEN | 32 | No |
| ARIAUSDT | 12 | RED | 31 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARTYUSDT | 2 | GREEN | 5 | No |
| ARUSDT | 12 | GREEN | 9 | No |
| ARXUSDT | 12 | RED | 15 | No |
| ASTERUSDT | 12 | GREEN | 15 | No |
| ATOMUSDT | 12 | GREEN | 15 | No |
| ATUSDT | 12 | RED | 21 | No |
| AVAXUSDT | 12 | GREEN | 26 | No |
| AXISUSDT | 12 | RED | 8 | No |
| BABYUSDT | 12 | GREEN | 21 | No |
| BANKUSDT | 12 | GREEN | 6 | No |
| BARDUSDT | 11 | RED | 11 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 12 | GREEN | 35 | No |
| BEAMUSDT | 12 | GREEN | 10 | No |
| BEATUSDT | 12 | GREEN | 18 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 12 | GREEN | 13 | No |
| BIGTIMEUSDT | 5 | RED | 33 | No |
| BLESSUSDT | 12 | GREEN | 30 | No |
| BLURUSDT | 12 | GREEN | 22 | No |
| BNBUSDT | 12 | GREEN | 33 | No |
| BOMEUSDT | 12 | GREEN | 14 | No |
| BREVUSDT | 11 | GREEN | 7 | No |
| BRUSDT | 6 | GREEN | 18 | No |
| BTCUSDT | 12 | GREEN | 34 | No |
| BTWUSDT | 12 | RED | 23 | No |
| BUSDT | 6 | GREEN | 6 | No |
| CAKEUSDT | 4 | GREEN | 9 | No |
| CAPUSDT | 9 | GREEN | 10 | No |
| CFGUSDT | 12 | GREEN | 28 | No |
| CHIPUSDT | 12 | RED | 18 | No |
| CLSUSDT | 12 | RED | 3 | No |
| COOKIEUSDT | 7 | RED | 4 | No |
| CPUSDT | 11 | GREEN | 17 | No |
| CROSSUSDT | 12 | GREEN | 17 | No |
| CRVUSDT | 12 | GREEN | 24 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 12 | GREEN | 17 | No |
| CYBERUSDT | 12 | GREEN | 14 | No |
| CYSUSDT | 12 | RED | 23 | No |
| DASHUSDT | 7 | RED | 10 | No |
| DEXEUSDT | 12 | GREEN | 9 | No |
| DGAIUSDT | 12 | RED | 21 | No |
| DOGEUSDT | 12 | GREEN | 32 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 12 | GREEN | 27 | No |
| DOTUSDT | 12 | GREEN | 9 | No |
| EDGEUSDT | 7 | GREEN | 6 | No |
| EGLDUSDT | 6 | RED | 9 | No |
| EIGENUSDT | 9 | RED | 12 | No |
| ELICEUSDT | 9 | RED | 8 | No |
| ELSAUSDT | 12 | GREEN | 27 | No |
| ENAUSDT | 12 | GREEN | 34 | No |
| ENSOUSDT | 12 | GREEN | 15 | No |
| ENSUSDT | 10 | GREEN | 14 | No |
| ERAUSDT | 12 | RED | 27 | No |
| ETCUSDT | 12 | GREEN | 25 | No |
| ETHFIUSDT | 12 | GREEN | 26 | No |
| ETHUSDT | 12 | GREEN | 34 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 12 | GREEN | 31 | No |
| FARTCOINUSDT | 12 | GREEN | 22 | No |
| FCXUSDT | 10 | GREEN | 5 | No |
| FETUSDT | 12 | GREEN | 22 | No |
| FFUSDT | 6 | RED | 7 | No |
| FILUSDT | 12 | RED | 25 | No |
| FLOCKUSDT | 8 | GREEN | 9 | No |
| FLOKIUSDT | 12 | GREEN | 9 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 12 | GREEN | 11 | No |
| GPSUSDT | 9 | GREEN | 5 | No |
| GRAMUSDT | 12 | RED | 20 | No |
| GRASSUSDT | 12 | RED | 18 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 12 | GREEN | 6 | No |
| GWEIUSDT | 12 | RED | 5 | No |
| HBARUSDT | 12 | GREEN | 26 | No |
| HPQUSDT | 5 | RED | 2 | No |
| HUMAUSDT | 12 | GREEN | 20 | No |
| HUSDT | 10 | RED | 21 | No |
| HYPEUSDT | 12 | GREEN | 30 | No |
| ICNTUSDT | 12 | RED | 24 | No |
| ICPUSDT | 12 | GREEN | 17 | No |
| IDOLUSDT | 12 | RED | 32 | No |
| INFYUSDT | 3 | RED | 2 | No |
| INITUSDT | 12 | RED | 31 | No |
| INJUSDT | 12 | GREEN | 35 | No |
| INXUSDT | 12 | GREEN | 15 | No |
| IOSTUSDT | 10 | RED | 16 | No |
| IRYSUSDT | 12 | GREEN | 22 | No |
| JCTUSDT | 12 | RED | 28 | No |
| JNJUSDT | 9 | RED | 4 | No |
| JTOUSDT | 11 | GREEN | 13 | No |
| JUPUSDT | 12 | GREEN | 26 | No |
| KAIAUSDT | 1 | GREEN | 13 | No |
| KAITOUSDT | 12 | GREEN | 10 | No |
| KASUSDT | 12 | GREEN | 18 | No |
| KAVAUSDT | 9 | RED | 12 | No |
| KERNELUSDT | 12 | GREEN | 13 | No |
| KGENUSDT | 9 | GREEN | 18 | No |
| KITEUSDT | 12 | RED | 15 | No |
| KUAISHOUUSDT | 12 | GREEN | 17 | No |
| LABUSDT | 12 | RED | 23 | No |
| LAUSDT | 8 | GREEN | 17 | No |
| LAYERUSDT | 2 | GREEN | 28 | No |
| LDOUSDT | 12 | GREEN | 10 | No |
| LINKUSDT | 12 | GREEN | 35 | No |
| LISTAUSDT | 12 | GREEN | 35 | No |
| LITUSDT | 12 | GREEN | 16 | No |
| LSKUSDT | 12 | RED | 11 | No |
| LTCUSDT | 12 | GREEN | 33 | No |
| LUNCUSDT | 12 | RED | 19 | No |
| MAGICUSDT | 11 | GREEN | 14 | No |
| MAGMAUSDT | 10 | RED | 20 | No |
| MANTAUSDT | 4 | RED | 4 | No |
| MANTRAUSDT | 6 | RED | 36 | No |
| MARSCOINUSDT | 12 | GREEN | 15 | No |
| MDTUSDT | 2 | GREEN | 3 | No |
| MEGAUSDT | 12 | RED | 9 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 7 | RED | 4 | No |
| MEUSDT | 10 | GREEN | 34 | No |
| MMTUSDT | 12 | GREEN | 33 | No |
| MONUSDT | 12 | GREEN | 19 | No |
| MOODENGUSDT | 4 | RED | 25 | No |
| MORPHOUSDT | 8 | GREEN | 19 | No |
| MOVEUSDT | 4 | RED | 31 | No |
| MOVRUSDT | 3 | GREEN | 19 | No |
| MSUSDT | 7 | RED | 6 | No |
| MUBARAKUSDT | 12 | GREEN | 17 | No |
| MUSDT | 2 | RED | 12 | No |
| MYXUSDT | 11 | GREEN | 9 | No |
| NAORISUSDT | 12 | RED | 17 | No |
| NEARUSDT | 12 | GREEN | 31 | No |
| NEMUSDT | 8 | GREEN | 3 | No |
| NIGHTUSDT | 12 | RED | 21 | No |
| NILUSDT | 10 | GREEN | 12 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 12 | GREEN | 30 | No |
| ONEUSDT | 8 | GREEN | 20 | No |
| ONGUSDT | 11 | GREEN | 16 | No |
| OPGUSDT | 10 | RED | 19 | No |
| OPUSDT | 12 | GREEN | 9 | No |
| ORCAUSDT | 11 | GREEN | 14 | No |
| ORDERUSDT | 7 | GREEN | 4 | No |
| ORDIUSDT | 12 | GREEN | 11 | No |
| OUSDT | 3 | GREEN | 8 | No |
| PBRUSDT | 8 | RED | 5 | No |
| PENDLEUSDT | 12 | GREEN | 28 | No |
| PENGUUSDT | 12 | GREEN | 17 | No |
| PEOPLEUSDT | 11 | GREEN | 10 | No |
| PEPEUSDT | 12 | GREEN | 35 | No |
| PHAUSDT | 8 | GREEN | 21 | No |
| PIEVERSEUSDT | 12 | RED | 34 | No |
| PIPPINUSDT | 12 | RED | 32 | No |
| PIUSDT | 12 | GREEN | 19 | No |
| PLUMEUSDT | 12 | GREEN | 4 | No |
| PNUTUSDT | 4 | GREEN | 6 | No |
| POLUSDT | 12 | GREEN | 12 | No |
| PONSUSDT | 12 | GREEN | 34 | No |
| POPCATUSDT | 2 | GREEN | 10 | No |
| POWERUSDT | 10 | GREEN | 12 | No |
| PROMUSDT | 12 | RED | 28 | No |
| PROSUSDT | 8 | GREEN | 10 | No |
| PUMPUSDT | 12 | GREEN | 30 | No |
| PYTHUSDT | 12 | GREEN | 12 | No |
| QNTUSDT | 12 | GREEN | 28 | No |
| QUSDT | 9 | RED | 19 | No |
| RAREUSDT | 12 | GREEN | 15 | No |
| RAVEUSDT | 10 | RED | 13 | No |
| RAYUSDT | 12 | GREEN | 14 | No |
| RENDERUSDT | 12 | RED | 25 | No |
| REUSDT | 12 | GREEN | 6 | No |
| RIVERUSDT | 12 | GREEN | 8 | No |
| RPLUSDT | 10 | RED | 5 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 12 | GREEN | 15 | No |
| SANDUSDT | 12 | GREEN | 32 | No |
| SAPIENUSDT | 9 | RED | 12 | No |
| SEIUSDT | 12 | GREEN | 34 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHELLUSDT | 4 | RED | 12 | No |
| SHIBUSDT | 12 | GREEN | 28 | No |
| SIRENUSDT | 4 | GREEN | 11 | No |
| SKYAIUSDT | 12 | RED | 26 | No |
| SKYUSDT | 12 | GREEN | 25 | No |
| SLXUSDT | 5 | GREEN | 28 | No |
| SOLUSDT | 12 | GREEN | 33 | No |
| SOONUSDT | 10 | RED | 13 | No |
| SOPHUSDT | 2 | GREEN | 9 | No |
| SPACEUSDT | 9 | GREEN | 6 | No |
| SPKUSDT | 9 | GREEN | 8 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 9 | RED | 14 | No |
| SSVUSDT | 2 | GREEN | 29 | No |
| STONKUSDT | 3 | RED | 20 | No |
| STRKUSDT | 12 | GREEN | 20 | No |
| STXUSDT | 12 | GREEN | 13 | No |
| SUIUSDT | 12 | GREEN | 28 | No |
| SYNUSDT | 2 | GREEN | 16 | No |
| TAOUSDT | 12 | GREEN | 29 | No |
| TIAUSDT | 12 | GREEN | 29 | No |
| TRBUSDT | 6 | GREEN | 9 | No |
| TRUMPUSDT | 12 | RED | 30 | No |
| TRXUSDT | 12 | GREEN | 16 | No |
| TUSDT | 2 | GREEN | 10 | No |
| TUTUSDT | 11 | GREEN | 2 | No |
| UAIUSDT | 12 | RED | 21 | No |
| UBUSDT | 5 | RED | 13 | No |
| UNITASUSDT | 12 | RED | 18 | No |
| UNIUSDT | 12 | GREEN | 29 | No |
| USDBRLUSDT | 12 | RED | 4 | No |
| USDJPYUSDT | 11 | GREEN | 5 | No |
| USELESSUSDT | 12 | RED | 26 | No |
| USUALUSDT | 12 | GREEN | 8 | No |
| USUSDT | 2 | RED | 12 | No |
| VELVETUSDT | 12 | RED | 16 | No |
| VIRTUALUSDT | 12 | GREEN | 21 | No |
| VVVUSDT | 12 | GREEN | 31 | No |
| WAXPUSDT | 4 | RED | 20 | No |
| WIFUSDT | 12 | GREEN | 25 | No |
| WLDUSDT | 12 | GREEN | 28 | No |
| WLFIUSDT | 12 | GREEN | 14 | No |
| XLMUSDT | 12 | RED | 28 | No |
| XMRUSDT | 12 | GREEN | 25 | No |
| XPLUSDT | 12 | GREEN | 26 | No |
| XRPUSDT | 12 | GREEN | 36 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZBTUSDT | 2 | RED | 17 | No |
| ZECUSDT | 12 | GREEN | 35 | No |
| ZENUSDT | 8 | GREEN | 6 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZKUSDT | 5 | GREEN | 9 | No |
| ZROUSDT | 12 | RED | 30 | No |
| 牛来USDT | 12 | GREEN | 33 | No |
| 龙虾USDT | 12 | GREEN | 7 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 50 | 438 |
| $1m–$10m 24h futures turnover | 50 | 457 |
| $10m–$100m 24h futures turnover | 17 | 232 |
| $100m+ 24h futures turnover | 5 | 80 |

## Profit-versus-loss summary (hypothetical book-walk outcomes)

- Positive outcomes: 2843; negative outcomes: 4612; flat: 0
- Win rate among scored outcomes: 38.1%
- Gross positive outcomes: 21928.935167 USDT
- Gross negative outcomes: 38437.848415 USDT
- Total estimated net after trading fees: -16508.913248 USDT
- Profit factor (gross gains / gross losses): 0.571
- Average winning outcome: 7.713308 USDT
- Average losing outcome: -8.334312 USDT
- Mean estimated net result: -39.85 bps

These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.

- Ticker-only reference outcomes (separate, not executable): 0

## Strategy breakdown

| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |
|---|---:|---:|---:|---:|
| breakdown | 1206 | 567 | 639 | -12.70 |
| breakout | 681 | 130 | 551 | -61.53 |
| ema_volume | 5568 | 2146 | 3422 | -43.08 |

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
