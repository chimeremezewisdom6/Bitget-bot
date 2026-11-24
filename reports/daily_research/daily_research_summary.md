# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-24T12:53:32.795728+00:00
- Session ended UTC: not recorded
- Collector cycles: 3
- Distinct symbols observed: 233
- Current Bitget turnover-watchlist contracts: 128
- Market observation rows: 4600
- Candidate signals eligible for entry evaluation: 780
- Watch-only RSI conditions (no entry): 1340
- Two-snapshot order-book shadow outcomes: 6561
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 1687
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 432
- Breakout-based trend starts found: 6882 (LONG: 2988; SHORT: 3894)
- Average direction-matching candle share in first hour: 31.9%
- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 431
- Complete trend events with early-window measurements: 6806

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 6806 | 45.6% | 3743/6806 (55.0%) | 0.1284% |
| 10 | 6806 | 38.2% | 3743/6806 (55.0%) | 0.1426% |
| 15 | 6806 | 35.5% | 3724/6806 (54.7%) | 0.1425% |
| 20 | 6806 | 34.6% | 3585/6806 (52.7%) | 0.0889% |
| 30 | 6806 | 33.6% | 3461/6806 (50.9%) | 0.0368% |
| 60 | 6806 | 32.1% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 221
- LONG/SHORT ignition candidates (score at least 4/7): 11
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| MONUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 1.2897% | 1.6932% | 1.3107% | 1.547x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| XMRUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.1333% | 0.7418% | 1.0712% | 4.672x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| GRVTUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.7954% | -1.17% | -0.9884% | 4.116x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| EGLDUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.3273% | 0.3273% | 0.5268% | 1.985x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| PROSUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.1481% | 1.212% | 0.4077% | 3.446x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| XLMUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | -0.4921% | 0.0487% | 0.4189% | 2.439x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| SEIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | -0.0608% | 0.736% | 0.3353% | 0.55x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| TIAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | -0.1846% | 0.6826% | 0.729% | 1.729x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| USDBRLUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.0796% | 0.258% | 2.4918% | 0.637x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| KITEUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1185% | 0.4555% | 0.3752% | 2.462x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| RAVEUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | -0.448% | 0.2429% | 0.8311% | 3.903x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| MMTUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -0.0855% | 0.9935% | 1.0918% | 0.108x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ARBUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5026% | 0.3167% | 0.3275% | 0.114x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| LISTAUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1232% | 3.1831% | -0.6453% | 0.982x | 3/2 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| ALGOUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -0.3432% | 0.3584% | 0.3075% | 1.531x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| INXUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.6798% | 2.0153% | 1.534% | 0.938x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| HUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.7525% | -0.1682% | 1.7354% | 0.555x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| JCTUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1336% | 1.4208% | 0.8708% | 0.402x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| IRYSUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.0644% | 0.8442% | 0.6624% | 0.699x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PONSUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -0.23% | -0.1726% | 0.3551% | 0.555x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| VELVETUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.4737% | 1.6009% | 1.4574% | 3.009x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| USELESSUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5957% | 0.1% | 0.4506% | 0.171x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| LUNCUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2422% | 0.6857% | -0.1651% | 0.169x | 4/1 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| ETCUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -0.2094% | 0.4037% | 0.274% | 3.335x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| ONEUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.0321% | 1.0169% | 0.5755% | 0.859x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| INITUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -0.3256% | 1.3001% | 0.978% | 3.45x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| PIPPINUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -1.0199% | 0.6001% | 0.5269% | 3.29x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| MAGMAUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.3149% | 0.562% | 0.2979% | 0.988x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| STXUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1965% | 0.5545% | 0.6082% | 2.185x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| SOONUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.4878% | -0.0816% | -0.2514% | 47.816x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| ALLOUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -0.2826% | 0.5779% | 0.9937% | 1.173x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| KERNELUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.6008% | 1.2334% | 1.0429% | 0.428x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| MAGICUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1521% | 0.3046% | 0.9179% | 0.084x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| AEONUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.3109% | 1.2023% | 1.1937% | 1.927x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| FFUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.6936% | -0.6353% | -0.4903% | 1.879x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| BUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2195% | 0.5531% | 0.8667% | 5.003x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| BTCUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | -0.3807% | 0.1168% | 0.483% | 0.907x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| NEARUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | -0.4105% | 0.5395% | 1.6147% | 5.268x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| ENAUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | -0.5408% | 0.5467% | 0.3674% | 0.241x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| EVAAUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | 0.3129% | 1.1738% | 1.1762% | 0.778x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |

Scoring checks: aligned 5m/15m price acceleration, rising 15m OI, 5m turnover surge versus the prior 20m, directional candle pressure with real candle bodies, 20m breakout, 60m breakout, and higher-high/lower-low structure. Scores are evidence counts, not probabilities. A high score is a research watch candidate, not a buy/sell instruction. Rising aggregate OI means total outstanding positions increased; it does not reveal whether longs or shorts initiated them.

| Symbol | Direction | Trend start (UTC) | Green | Red | Doji | Matching candles | Matching % | First-hour follow-through % |
|---|---|---|---:|---:|---:|---:|---:|---:|
| EVAAUSDT | SHORT | 2026-11-24 03:44 | 19 | 41 | 0 | 41 / 60 | 68.33% | -1.3488%
| SKYUSDT | SHORT | 2026-11-23 07:49 | 17 | 40 | 3 | 40 / 60 | 66.67% | 6.3317%
| PROMUSDT | LONG | 2026-11-23 14:10 | 39 | 21 | 0 | 39 / 60 | 65.0% | 12.4267%
| PROMUSDT | LONG | 2026-11-23 14:10 | 39 | 21 | 0 | 39 / 60 | 65.0% | 12.4267%
| CYSUSDT | LONG | 2026-11-23 16:29 | 38 | 22 | 0 | 38 / 60 | 63.33% | 10.4336%
| CYSUSDT | LONG | 2026-11-23 16:29 | 38 | 22 | 0 | 38 / 60 | 63.33% | 10.4336%
| XMRUSDT | LONG | 2026-11-24 03:37 | 38 | 18 | 4 | 38 / 60 | 63.33% | 1.7838%
| LABUSDT | LONG | 2026-11-23 13:56 | 38 | 22 | 0 | 38 / 60 | 63.33% | 4.0981%
| UAIUSDT | LONG | 2026-11-23 13:57 | 38 | 22 | 0 | 38 / 60 | 63.33% | 3.1938%
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
| DOSUSDT | SHORT | 2026-11-23 16:09 | 21 | 35 | 4 | 35 / 60 | 58.33% | 2.2548%
| ATOMUSDT | LONG | 2026-11-23 13:55 | 35 | 23 | 2 | 35 / 60 | 58.33% | 3.856%
| PONSUSDT | LONG | 2026-11-23 13:18 | 35 | 21 | 4 | 35 / 60 | 58.33% | 9.6235%
| PONSUSDT | SHORT | 2026-11-23 15:42 | 25 | 35 | 0 | 35 / 60 | 58.33% | 2.8367%
| GRAMUSDT | LONG | 2026-11-23 06:52 | 35 | 17 | 8 | 35 / 60 | 58.33% | 1.6643%
| BTWUSDT | SHORT | 2026-11-22 23:16 | 23 | 35 | 2 | 35 / 60 | 58.33% | 2.4258%
| CYBERUSDT | LONG | 2026-11-23 14:30 | 35 | 23 | 2 | 35 / 60 | 58.33% | 1.9955%
| INITUSDT | LONG | 2026-11-23 13:56 | 35 | 24 | 1 | 35 / 60 | 58.33% | 4.5193%
| BEATUSDT | LONG | 2026-11-23 08:12 | 35 | 20 | 5 | 35 / 60 | 58.33% | -1.1587%
| PIPPINUSDT | LONG | 2026-11-23 07:10 | 35 | 16 | 9 | 35 / 60 | 58.33% | 3.0994%
| PIPPINUSDT | LONG | 2026-11-23 15:16 | 35 | 24 | 1 | 35 / 60 | 58.33% | 1.6146%
| BTCUSDT | SHORT | 2026-11-24 02:22 | 25 | 35 | 0 | 35 / 60 | 58.33% | 1.0741%
| NEARUSDT | SHORT | 2026-11-24 09:00 | 25 | 35 | 0 | 35 / 60 | 58.33% | 0.623%
| PEPEUSDT | LONG | 2026-11-23 13:55 | 35 | 25 | 0 | 35 / 60 | 58.33% | 7.2345%
| PEPEUSDT | SHORT | 2026-11-24 06:22 | 25 | 35 | 0 | 35 / 60 | 58.33% | 0.1158%
| EVAAUSDT | SHORT | 2026-11-23 17:05 | 25 | 35 | 0 | 35 / 60 | 58.33% | 2.8532%
| EVAAUSDT | SHORT | 2026-11-23 21:19 | 25 | 35 | 0 | 35 / 60 | 58.33% | 1.7645%
| EVAAUSDT | LONG | 2026-11-24 06:41 | 35 | 25 | 0 | 35 / 60 | 58.33% | 0.8891%
| EVAAUSDT | SHORT | 2026-11-24 11:10 | 25 | 35 | 0 | 35 / 60 | 58.33% | 13.4378%
| MMTUSDT | LONG | 2026-11-23 23:08 | 35 | 23 | 2 | 35 / 60 | 58.33% | 1.4549%
| BLESSUSDT | LONG | 2026-11-24 00:05 | 35 | 24 | 1 | 35 / 60 | 58.33% | 3.8698%
| LISTAUSDT | LONG | 2026-11-23 21:27 | 35 | 23 | 2 | 35 / 60 | 58.33% | 2.6466%
| CYSUSDT | SHORT | 2026-11-24 06:35 | 25 | 35 | 0 | 35 / 60 | 58.33% | 3.1661%
| PIEVERSEUSDT | LONG | 2026-11-23 16:11 | 35 | 25 | 0 | 35 / 60 | 58.33% | 5.1775%
| UNIUSDT | SHORT | 2026-11-24 06:22 | 19 | 35 | 6 | 35 / 60 | 58.33% | 1.0339%
| PUMPUSDT | SHORT | 2026-11-24 08:27 | 23 | 35 | 2 | 35 / 60 | 58.33% | 1.9121%
| BNBUSDT | SHORT | 2026-11-24 10:18 | 22 | 35 | 3 | 35 / 60 | 58.33% | 0.255%
| AVAXUSDT | SHORT | 2026-11-24 02:02 | 23 | 35 | 2 | 35 / 60 | 58.33% | 0.6085%
| INJUSDT | LONG | 2026-11-23 13:56 | 35 | 25 | 0 | 35 / 60 | 58.33% | 5.1172%
| BCHUSDT | LONG | 2026-11-23 13:55 | 35 | 25 | 0 | 35 / 60 | 58.33% | 4.1861%
| XLMUSDT | SHORT | 2026-11-23 16:46 | 25 | 35 | 0 | 35 / 60 | 58.33% | 0.923%
| QNTUSDT | SHORT | 2026-11-24 01:57 | 22 | 35 | 3 | 35 / 60 | 58.33% | 0.7895%

## Mandatory 60-minute same-colour candle experiment

Each eligible symbol is checked up to five separate times. Every check uses the latest 60 fully closed one-minute candles; green and red candles are counted separately, doji candles count toward neither colour, and a result qualifies when either colour reaches at least 40. This is a research filter, not a trade instruction.

| Symbol | Checks recorded | Latest colour | Same-colour count | Qualified |
|---|---:|---|---:|---|
| 0GUSDT | 8 | GREEN | 12 | No |
| 1000BONKUSDT | 8 | GREEN | 18 | No |
| 2ZUSDT | 1 | RED | 22 | No |
| AAVEUSDT | 8 | GREEN | 32 | No |
| ACEUSDT | 8 | GREEN | 25 | No |
| ACUUSDT | 8 | RED | 2 | No |
| ADAUSDT | 8 | RED | 26 | No |
| AEONUSDT | 8 | GREEN | 20 | No |
| AEROUSDT | 8 | RED | 19 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AKEUSDT | 8 | GREEN | 31 | No |
| ALGOUSDT | 8 | RED | 30 | No |
| ALLOUSDT | 8 | RED | 24 | No |
| ALTUSDT | 1 | RED | 9 | No |
| AMDLUSDT | 8 | GREEN | 27 | No |
| APRUSDT | 8 | RED | 22 | No |
| APTUSDT | 8 | RED | 31 | No |
| ARBUSDT | 8 | RED | 30 | No |
| ARIAUSDT | 8 | RED | 31 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARUSDT | 8 | GREEN | 18 | No |
| ARXUSDT | 8 | GREEN | 27 | No |
| ASTERUSDT | 8 | GREEN | 25 | No |
| ATOMUSDT | 8 | GREEN | 23 | No |
| ATUSDT | 8 | RED | 17 | No |
| AVAXUSDT | 8 | RED | 33 | No |
| AXISUSDT | 8 | RED | 22 | No |
| BABYUSDT | 8 | GREEN | 25 | No |
| BANKUSDT | 8 | GREEN | 19 | No |
| BARDUSDT | 8 | RED | 19 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 8 | GREEN | 29 | No |
| BEAMUSDT | 8 | RED | 15 | No |
| BEATUSDT | 8 | RED | 37 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 8 | RED | 20 | No |
| BLESSUSDT | 8 | GREEN | 32 | No |
| BLURUSDT | 7 | RED | 11 | No |
| BNBUSDT | 8 | RED | 34 | No |
| BOMEUSDT | 8 | GREEN | 24 | No |
| BREVUSDT | 8 | GREEN | 9 | No |
| BRUSDT | 5 | GREEN | 11 | No |
| BTCUSDT | 8 | RED | 34 | No |
| BTWUSDT | 8 | GREEN | 31 | No |
| BUSDT | 1 | RED | 19 | No |
| CAKEUSDT | 1 | GREEN | 21 | No |
| CAPUSDT | 8 | GREEN | 19 | No |
| CFGUSDT | 8 | RED | 25 | No |
| CHIPUSDT | 8 | RED | 19 | No |
| CLSUSDT | 8 | RED | 22 | No |
| COOKIEUSDT | 7 | RED | 4 | No |
| CPUSDT | 8 | RED | 15 | No |
| CROSSUSDT | 8 | GREEN | 18 | No |
| CRVUSDT | 8 | RED | 24 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 8 | RED | 28 | No |
| CYBERUSDT | 8 | GREEN | 24 | No |
| CYSUSDT | 8 | GREEN | 30 | No |
| DASHUSDT | 7 | RED | 10 | No |
| DEXEUSDT | 8 | GREEN | 18 | No |
| DGAIUSDT | 8 | GREEN | 27 | No |
| DOGEUSDT | 8 | RED | 31 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 8 | GREEN | 33 | No |
| DOTUSDT | 8 | RED | 21 | No |
| EDGEUSDT | 5 | GREEN | 9 | No |
| EGLDUSDT | 5 | GREEN | 14 | No |
| EIGENUSDT | 8 | GREEN | 17 | No |
| ELICEUSDT | 8 | GREEN | 5 | No |
| ELSAUSDT | 8 | GREEN | 31 | No |
| ENAUSDT | 8 | RED | 32 | No |
| ENSOUSDT | 8 | GREEN | 26 | No |
| ENSUSDT | 8 | RED | 22 | No |
| ERAUSDT | 8 | RED | 22 | No |
| ETCUSDT | 8 | RED | 29 | No |
| ETHFIUSDT | 8 | RED | 29 | No |
| ETHUSDT | 8 | RED | 34 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 8 | GREEN | 35 | No |
| FARTCOINUSDT | 8 | RED | 28 | No |
| FCXUSDT | 8 | GREEN | 15 | No |
| FETUSDT | 8 | RED | 19 | No |
| FFUSDT | 4 | GREEN | 25 | No |
| FILUSDT | 8 | GREEN | 30 | No |
| FLOCKUSDT | 8 | GREEN | 9 | No |
| FLOKIUSDT | 8 | GREEN | 16 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 8 | RED | 21 | No |
| GPSUSDT | 8 | GREEN | 6 | No |
| GRAMUSDT | 8 | RED | 28 | No |
| GRASSUSDT | 8 | RED | 27 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 8 | RED | 16 | No |
| GWEIUSDT | 8 | GREEN | 25 | No |
| HBARUSDT | 8 | RED | 25 | No |
| HUMAUSDT | 8 | RED | 17 | No |
| HUSDT | 8 | RED | 26 | No |
| HYPEUSDT | 8 | RED | 31 | No |
| ICNTUSDT | 8 | GREEN | 26 | No |
| ICPUSDT | 8 | RED | 28 | No |
| IDOLUSDT | 8 | GREEN | 29 | No |
| INITUSDT | 8 | GREEN | 32 | No |
| INJUSDT | 8 | RED | 33 | No |
| INXUSDT | 8 | RED | 23 | No |
| IOSTUSDT | 8 | GREEN | 14 | No |
| IRYSUSDT | 8 | GREEN | 27 | No |
| JCTUSDT | 8 | GREEN | 31 | No |
| JNJUSDT | 5 | GREEN | 17 | No |
| JTOUSDT | 8 | RED | 25 | No |
| JUPUSDT | 8 | RED | 28 | No |
| KAITOUSDT | 8 | GREEN | 20 | No |
| KASUSDT | 8 | RED | 25 | No |
| KAVAUSDT | 5 | RED | 15 | No |
| KERNELUSDT | 8 | GREEN | 18 | No |
| KGENUSDT | 8 | RED | 22 | No |
| KITEUSDT | 8 | GREEN | 27 | No |
| KUAISHOUUSDT | 8 | RED | 15 | No |
| LABUSDT | 8 | RED | 29 | No |
| LAUSDT | 5 | RED | 15 | No |
| LDOUSDT | 8 | GREEN | 24 | No |
| LINKUSDT | 8 | RED | 34 | No |
| LISTAUSDT | 8 | GREEN | 37 | No |
| LITUSDT | 8 | RED | 27 | No |
| LSKUSDT | 8 | RED | 18 | No |
| LTCUSDT | 8 | RED | 30 | No |
| LUNCUSDT | 8 | RED | 29 | No |
| MAGICUSDT | 7 | RED | 13 | No |
| MAGMAUSDT | 8 | GREEN | 23 | No |
| MANTRAUSDT | 1 | RED | 16 | No |
| MARSCOINUSDT | 8 | GREEN | 19 | No |
| MDTUSDT | 1 | GREEN | 11 | No |
| MEGAUSDT | 8 | GREEN | 27 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 7 | RED | 4 | No |
| MEUSDT | 6 | GREEN | 23 | No |
| MMTUSDT | 8 | GREEN | 35 | No |
| MONUSDT | 8 | RED | 34 | No |
| MORPHOUSDT | 8 | GREEN | 19 | No |
| MSUSDT | 7 | RED | 6 | No |
| MUBARAKUSDT | 8 | GREEN | 28 | No |
| MYXUSDT | 8 | RED | 20 | No |
| NAORISUSDT | 8 | RED | 24 | No |
| NEARUSDT | 8 | RED | 35 | No |
| NEMUSDT | 7 | RED | 8 | No |
| NIGHTUSDT | 8 | RED | 24 | No |
| NILUSDT | 8 | GREEN | 22 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 8 | RED | 30 | No |
| ONEUSDT | 8 | GREEN | 20 | No |
| ONGUSDT | 8 | RED | 26 | No |
| OPGUSDT | 5 | RED | 6 | No |
| OPUSDT | 8 | GREEN | 18 | No |
| ORCAUSDT | 8 | RED | 15 | No |
| ORDERUSDT | 3 | GREEN | 16 | No |
| ORDIUSDT | 8 | GREEN | 29 | No |
| PBRUSDT | 8 | RED | 5 | No |
| PENDLEUSDT | 8 | RED | 31 | No |
| PENGUUSDT | 8 | GREEN | 29 | No |
| PEOPLEUSDT | 6 | RED | 25 | No |
| PEPEUSDT | 8 | GREEN | 33 | No |
| PHAUSDT | 8 | GREEN | 21 | No |
| PIEVERSEUSDT | 8 | GREEN | 31 | No |
| PIPPINUSDT | 8 | GREEN | 29 | No |
| PIUSDT | 8 | GREEN | 27 | No |
| PLUMEUSDT | 8 | RED | 18 | No |
| POLUSDT | 8 | GREEN | 25 | No |
| PONSUSDT | 8 | RED | 30 | No |
| POWERUSDT | 8 | GREEN | 26 | No |
| PROMUSDT | 8 | RED | 31 | No |
| PROSUSDT | 4 | GREEN | 34 | No |
| PUMPUSDT | 8 | RED | 33 | No |
| PYTHUSDT | 8 | RED | 30 | No |
| QNTUSDT | 8 | RED | 32 | No |
| QUSDT | 8 | RED | 28 | No |
| RAREUSDT | 8 | RED | 17 | No |
| RAVEUSDT | 8 | GREEN | 30 | No |
| RAYUSDT | 8 | RED | 20 | No |
| RENDERUSDT | 8 | RED | 30 | No |
| REUSDT | 8 | RED | 26 | No |
| RIVERUSDT | 8 | GREEN | 17 | No |
| RPLUSDT | 8 | GREEN | 22 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 8 | GREEN | 29 | No |
| SANDUSDT | 8 | RED | 29 | No |
| SAPIENUSDT | 8 | GREEN | 24 | No |
| SEIUSDT | 8 | GREEN | 31 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHIBUSDT | 8 | RED | 29 | No |
| SKYAIUSDT | 8 | GREEN | 26 | No |
| SKYUSDT | 8 | GREEN | 23 | No |
| SOLUSDT | 8 | RED | 31 | No |
| SOONUSDT | 8 | RED | 19 | No |
| SPACEUSDT | 5 | RED | 18 | No |
| SPKUSDT | 8 | GREEN | 22 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 8 | GREEN | 15 | No |
| STRKUSDT | 8 | RED | 25 | No |
| STXUSDT | 8 | GREEN | 24 | No |
| SUIUSDT | 8 | RED | 30 | No |
| TAOUSDT | 8 | RED | 31 | No |
| TIAUSDT | 8 | GREEN | 30 | No |
| TRBUSDT | 1 | GREEN | 19 | No |
| TRUMPUSDT | 8 | RED | 32 | No |
| TRXUSDT | 8 | GREEN | 25 | No |
| TUTUSDT | 7 | GREEN | 10 | No |
| UAIUSDT | 8 | RED | 30 | No |
| UBUSDT | 5 | RED | 13 | No |
| UNITASUSDT | 8 | RED | 14 | No |
| UNIUSDT | 8 | GREEN | 29 | No |
| USDBRLUSDT | 8 | GREEN | 30 | No |
| USDJPYUSDT | 7 | RED | 5 | No |
| USELESSUSDT | 8 | RED | 30 | No |
| USUALUSDT | 8 | GREEN | 3 | No |
| VELVETUSDT | 8 | GREEN | 25 | No |
| VIRTUALUSDT | 8 | RED | 31 | No |
| VVVUSDT | 8 | RED | 31 | No |
| WIFUSDT | 8 | RED | 25 | No |
| WLDUSDT | 8 | GREEN | 27 | No |
| WLFIUSDT | 8 | RED | 25 | No |
| XLMUSDT | 8 | RED | 32 | No |
| XMRUSDT | 8 | RED | 31 | No |
| XPLUSDT | 8 | GREEN | 25 | No |
| XRPUSDT | 8 | RED | 32 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZBTUSDT | 1 | GREEN | 18 | No |
| ZECUSDT | 8 | GREEN | 30 | No |
| ZENUSDT | 4 | RED | 7 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZKUSDT | 1 | RED | 12 | No |
| ZROUSDT | 8 | GREEN | 32 | No |
| 牛来USDT | 8 | GREEN | 16 | No |
| 龙虾USDT | 8 | GREEN | 13 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 50 | 209 |
| $1m–$10m 24h futures turnover | 50 | 210 |
| $10m–$100m 24h futures turnover | 23 | 129 |
| $100m+ 24h futures turnover | 5 | 55 |

## Profit-versus-loss summary (hypothetical book-walk outcomes)

- Positive outcomes: 2453; negative outcomes: 4108; flat: 0
- Win rate among scored outcomes: 37.4%
- Gross positive outcomes: 16734.797578 USDT
- Gross negative outcomes: 31841.439417 USDT
- Total estimated net after trading fees: -15106.641839 USDT
- Profit factor (gross gains / gross losses): 0.526
- Average winning outcome: 6.822176 USDT
- Average losing outcome: -7.751081 USDT
- Mean estimated net result: -41.54 bps

These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.

- Ticker-only reference outcomes (separate, not executable): 0

## Strategy breakdown

| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |
|---|---:|---:|---:|---:|
| breakdown | 1134 | 540 | 594 | -17.89 |
| breakout | 585 | 103 | 482 | -60.59 |
| ema_volume | 4842 | 1810 | 3032 | -44.78 |

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
