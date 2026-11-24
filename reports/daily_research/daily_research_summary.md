# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-24T12:53:32.795728+00:00
- Session ended UTC: not recorded
- Collector cycles: 1
- Distinct symbols observed: 224
- Current Bitget turnover-watchlist contracts: 128
- Market observation rows: 4200
- Candidate signals eligible for entry evaluation: 744
- Watch-only RSI conditions (no entry): 1254
- Two-snapshot order-book shadow outcomes: 6300
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 1287
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 422
- Breakout-based trend starts found: 6715 (LONG: 2916; SHORT: 3799)
- Average direction-matching candle share in first hour: 32.3%
- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 421
- Complete trend events with early-window measurements: 6639

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 6639 | 45.9% | 3639/6639 (54.8%) | 0.1283% |
| 10 | 6639 | 38.4% | 3638/6639 (54.8%) | 0.1424% |
| 15 | 6639 | 35.9% | 3628/6639 (54.6%) | 0.1429% |
| 20 | 6639 | 35.0% | 3488/6639 (52.5%) | 0.0878% |
| 30 | 6639 | 33.9% | 3368/6639 (50.7%) | 0.0358% |
| 60 | 6639 | 32.5% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 212
- LONG/SHORT ignition candidates (score at least 4/7): 13
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| LISTAUSDT | LONG | 7 / 7 | IGNITION_CANDIDATE | 1.3582% | 1.6768% | 6.1905% | 1.809x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| BLESSUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 2.5634% | 10.3496% | 8.1057% | 0.537x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| QNTUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.2821% | 0.4778% | 0.4624% | 0.1x | 4/0 | NEW_POSITION_BUILDING_AGGREGATE |
| LUNCUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.7821% | 0.94% | -3.9664% | 1.375x | 4/0 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| MAGMAUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.399% | 0.6965% | 0.5058% | 2.619x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| KITEUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.4671% | 0.4041% | -0.5773% | 0.168x | 4/0 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| WLDUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1283% | -0.2563% | 0.7327% | 4.148x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| BCHUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.0402% | 0.0805% | 0.3244% | 2.268x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ZROUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1359% | -0.1941% | 1.2285% | 1.872x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| INXUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 1.4088% | 2.8307% | -1.3403% | 4.651x | 3/2 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| IDOLUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.6819% | -0.564% | 0.0677% | 0.31x | 0/4 | NEW_POSITION_BUILDING_AGGREGATE |
| RPLUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.4095% | 1.4061% | 2.7303% | 3.799x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| CAPUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1344% | 0.7072% | 1.2356% | 3.553x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| ENAUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2322% | 0.6284% | 1.2359% | 2.329x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| EVAAUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 2.0715% | 0.9419% | 1.5235% | 0.674x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PROMUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5551% | -0.1682% | 2.0196% | 0.135x | 0/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PUMPUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1629% | 0.6135% | 1.033% | 0.217x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| SKYUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.8236% | 0.3225% | 0.3881% | 1.595x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| FETUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2812% | 0.5639% | 0.4106% | 0.248x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| SEIUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.0898% | 0.4505% | 0.4151% | 1.563x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| 牛来USDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.24% | 1.0209% | 2.6584% | 2.086x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CYBERUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2906% | 0.1935% | 0.1548% | 5.101x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CTUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1636% | 0.4099% | 0.4188% | 0.453x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| SAPIENUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1539% | -0.4602% | -0.0357% | 16.368x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| BEATUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1322% | 0.2501% | 0.2575% | 1.474x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PIPPINUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.3948% | 0.3948% | 0.4668% | 0.289x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| NAORISUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.3134% | 0.5691% | 1.0767% | 0.236x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| KERNELUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5416% | -0.6585% | -0.3678% | 2.079x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| 0GUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1016% | -0.7071% | 0.4382% | 0.333x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| 龙虾USDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.3025% | -0.5118% | 0.2593% | 0.193x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ETHUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.0429% | 0.2126% | 0.2607% | 0.342x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| SOLUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.13% | 0.034% | 0.2558% | 0.624x | 0/5 | NEW_POSITION_BUILDING_AGGREGATE |
| ZECUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.1435% | 0.2282% | 0.7243% | 0.77x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| HYPEUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.278% | -0.3002% | 0.0094% | 0.669x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| NEARUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | -0.031% | 0.3937% | 0.6592% | 0.156x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PEPEUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | -0.1422% | -0.0987% | 0.4687% | 0.321x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| DOGEUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.0899% | -0.1438% | 0.0582% | 6.044x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PIEVERSEUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.2533% | -0.4774% | 0.1607% | 0.696x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| ELSAUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | 0.5277% | -0.2229% | -1.3873% | 0.387x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| ADAUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.1374% | -0.3427% | 0.0752% | 0.605x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |

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
| 0GUSDT | 6 | RED | 21 | No |
| 1000BONKUSDT | 6 | GREEN | 10 | No |
| AAVEUSDT | 6 | RED | 32 | No |
| ACEUSDT | 6 | RED | 23 | No |
| ACUUSDT | 6 | GREEN | 8 | No |
| ADAUSDT | 6 | RED | 21 | No |
| AEONUSDT | 6 | RED | 10 | No |
| AEROUSDT | 6 | RED | 17 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AKEUSDT | 6 | GREEN | 32 | No |
| ALGOUSDT | 6 | RED | 17 | No |
| ALLOUSDT | 6 | GREEN | 21 | No |
| AMDLUSDT | 6 | RED | 16 | No |
| APRUSDT | 6 | RED | 26 | No |
| APTUSDT | 6 | RED | 27 | No |
| ARBUSDT | 6 | RED | 34 | No |
| ARIAUSDT | 6 | GREEN | 31 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARUSDT | 6 | RED | 12 | No |
| ARXUSDT | 6 | RED | 25 | No |
| ASTERUSDT | 6 | GREEN | 17 | No |
| ATOMUSDT | 6 | RED | 20 | No |
| ATUSDT | 6 | RED | 20 | No |
| AVAXUSDT | 6 | RED | 29 | No |
| AXISUSDT | 6 | RED | 13 | No |
| BABYUSDT | 6 | GREEN | 24 | No |
| BANKUSDT | 6 | RED | 14 | No |
| BARDUSDT | 6 | RED | 16 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 6 | RED | 30 | No |
| BEAMUSDT | 6 | RED | 9 | No |
| BEATUSDT | 6 | GREEN | 29 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 6 | GREEN | 9 | No |
| BLESSUSDT | 6 | RED | 32 | No |
| BLURUSDT | 6 | RED | 12 | No |
| BNBUSDT | 6 | GREEN | 28 | No |
| BOMEUSDT | 6 | RED | 11 | No |
| BREVUSDT | 6 | GREEN | 16 | No |
| BRUSDT | 5 | GREEN | 11 | No |
| BTCUSDT | 6 | RED | 31 | No |
| BTWUSDT | 6 | RED | 26 | No |
| CAPUSDT | 6 | GREEN | 23 | No |
| CFGUSDT | 6 | RED | 8 | No |
| CHIPUSDT | 6 | RED | 15 | No |
| CLSUSDT | 6 | GREEN | 6 | No |
| COOKIEUSDT | 6 | RED | 4 | No |
| CPUSDT | 6 | RED | 14 | No |
| CROSSUSDT | 6 | GREEN | 25 | No |
| CRVUSDT | 6 | RED | 14 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 6 | GREEN | 23 | No |
| CYBERUSDT | 6 | RED | 22 | No |
| CYSUSDT | 6 | GREEN | 32 | No |
| DASHUSDT | 6 | RED | 11 | No |
| DEXEUSDT | 6 | GREEN | 7 | No |
| DGAIUSDT | 6 | GREEN | 29 | No |
| DOGEUSDT | 6 | RED | 33 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 6 | RED | 29 | No |
| DOTUSDT | 6 | RED | 13 | No |
| EDGEUSDT | 5 | GREEN | 9 | No |
| EGLDUSDT | 3 | RED | 9 | No |
| EIGENUSDT | 6 | RED | 12 | No |
| ELICEUSDT | 6 | RED | 3 | No |
| ELSAUSDT | 6 | RED | 32 | No |
| ENAUSDT | 6 | GREEN | 32 | No |
| ENSOUSDT | 6 | RED | 28 | No |
| ENSUSDT | 6 | RED | 18 | No |
| ERAUSDT | 6 | RED | 20 | No |
| ETCUSDT | 6 | GREEN | 24 | No |
| ETHFIUSDT | 6 | RED | 18 | No |
| ETHUSDT | 6 | RED | 31 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 6 | GREEN | 32 | No |
| FARTCOINUSDT | 6 | RED | 25 | No |
| FCXUSDT | 6 | RED | 10 | No |
| FETUSDT | 6 | GREEN | 18 | No |
| FFUSDT | 2 | RED | 10 | No |
| FILUSDT | 6 | GREEN | 27 | No |
| FLOCKUSDT | 6 | GREEN | 4 | No |
| FLOKIUSDT | 6 | RED | 7 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 6 | GREEN | 13 | No |
| GPSUSDT | 6 | RED | 4 | No |
| GRAMUSDT | 6 | GREEN | 21 | No |
| GRASSUSDT | 6 | GREEN | 22 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 6 | RED | 12 | No |
| GWEIUSDT | 6 | GREEN | 14 | No |
| HBARUSDT | 6 | RED | 20 | No |
| HUMAUSDT | 6 | RED | 19 | No |
| HUSDT | 6 | RED | 29 | No |
| HYPEUSDT | 6 | RED | 36 | No |
| ICNTUSDT | 6 | GREEN | 33 | No |
| ICPUSDT | 6 | RED | 20 | No |
| IDOLUSDT | 6 | RED | 30 | No |
| INITUSDT | 6 | RED | 30 | No |
| INJUSDT | 6 | RED | 28 | No |
| INXUSDT | 6 | RED | 28 | No |
| IOSTUSDT | 6 | RED | 9 | No |
| IRYSUSDT | 6 | RED | 24 | No |
| JCTUSDT | 6 | RED | 21 | No |
| JNJUSDT | 3 | GREEN | 11 | No |
| JTOUSDT | 6 | RED | 16 | No |
| JUPUSDT | 6 | GREEN | 25 | No |
| KAITOUSDT | 6 | RED | 10 | No |
| KASUSDT | 6 | RED | 12 | No |
| KAVAUSDT | 5 | RED | 15 | No |
| KERNELUSDT | 6 | GREEN | 17 | No |
| KGENUSDT | 6 | RED | 26 | No |
| KITEUSDT | 6 | GREEN | 30 | No |
| KUAISHOUUSDT | 6 | RED | 8 | No |
| LABUSDT | 6 | GREEN | 21 | No |
| LAUSDT | 5 | RED | 15 | No |
| LDOUSDT | 6 | RED | 17 | No |
| LINKUSDT | 6 | RED | 31 | No |
| LISTAUSDT | 6 | GREEN | 31 | No |
| LITUSDT | 6 | GREEN | 16 | No |
| LSKUSDT | 6 | RED | 8 | No |
| LTCUSDT | 6 | RED | 33 | No |
| LUNCUSDT | 6 | RED | 32 | No |
| MAGICUSDT | 6 | RED | 13 | No |
| MAGMAUSDT | 6 | GREEN | 23 | No |
| MARSCOINUSDT | 6 | GREEN | 8 | No |
| MEGAUSDT | 6 | RED | 18 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 6 | RED | 4 | No |
| MEUSDT | 4 | GREEN | 9 | No |
| MMTUSDT | 6 | GREEN | 28 | No |
| MONUSDT | 6 | RED | 21 | No |
| MORPHOUSDT | 6 | GREEN | 9 | No |
| MSUSDT | 6 | RED | 5 | No |
| MUBARAKUSDT | 6 | RED | 29 | No |
| MYXUSDT | 6 | RED | 14 | No |
| NAORISUSDT | 6 | GREEN | 30 | No |
| NEARUSDT | 6 | GREEN | 31 | No |
| NEMUSDT | 6 | RED | 8 | No |
| NIGHTUSDT | 6 | GREEN | 28 | No |
| NILUSDT | 6 | RED | 28 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 6 | GREEN | 24 | No |
| ONEUSDT | 6 | GREEN | 18 | No |
| ONGUSDT | 6 | RED | 16 | No |
| OPGUSDT | 5 | RED | 6 | No |
| OPUSDT | 6 | RED | 14 | No |
| ORCAUSDT | 6 | RED | 9 | No |
| ORDERUSDT | 1 | GREEN | 7 | No |
| ORDIUSDT | 6 | GREEN | 18 | No |
| PBRUSDT | 6 | GREEN | 9 | No |
| PENDLEUSDT | 6 | RED | 22 | No |
| PENGUUSDT | 6 | RED | 26 | No |
| PEOPLEUSDT | 5 | RED | 14 | No |
| PEPEUSDT | 6 | RED | 31 | No |
| PHAUSDT | 6 | GREEN | 6 | No |
| PIEVERSEUSDT | 6 | RED | 31 | No |
| PIPPINUSDT | 6 | RED | 27 | No |
| PIUSDT | 6 | RED | 16 | No |
| PLUMEUSDT | 6 | RED | 7 | No |
| POLUSDT | 6 | RED | 14 | No |
| PONSUSDT | 6 | GREEN | 28 | No |
| POWERUSDT | 6 | RED | 14 | No |
| PROMUSDT | 6 | RED | 25 | No |
| PROSUSDT | 2 | GREEN | 33 | No |
| PUMPUSDT | 6 | RED | 27 | No |
| PYTHUSDT | 6 | RED | 15 | No |
| QNTUSDT | 6 | GREEN | 28 | No |
| QUSDT | 6 | GREEN | 23 | No |
| RAREUSDT | 6 | GREEN | 12 | No |
| RAVEUSDT | 6 | GREEN | 9 | No |
| RAYUSDT | 6 | RED | 15 | No |
| RENDERUSDT | 6 | GREEN | 24 | No |
| REUSDT | 6 | GREEN | 18 | No |
| RIVERUSDT | 6 | RED | 16 | No |
| RPLUSDT | 6 | GREEN | 13 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 6 | GREEN | 28 | No |
| SANDUSDT | 6 | GREEN | 32 | No |
| SAPIENUSDT | 6 | RED | 12 | No |
| SEIUSDT | 6 | RED | 21 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHIBUSDT | 6 | RED | 25 | No |
| SKYAIUSDT | 6 | RED | 20 | No |
| SKYUSDT | 6 | GREEN | 24 | No |
| SOLUSDT | 6 | RED | 33 | No |
| SOONUSDT | 6 | RED | 12 | No |
| SPACEUSDT | 3 | GREEN | 20 | No |
| SPKUSDT | 6 | RED | 6 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 6 | RED | 8 | No |
| STRKUSDT | 6 | RED | 19 | No |
| STXUSDT | 6 | RED | 14 | No |
| SUIUSDT | 6 | GREEN | 29 | No |
| TAOUSDT | 6 | RED | 29 | No |
| TIAUSDT | 6 | GREEN | 22 | No |
| TRUMPUSDT | 6 | RED | 31 | No |
| TRXUSDT | 6 | RED | 16 | No |
| TUTUSDT | 6 | GREEN | 10 | No |
| UAIUSDT | 6 | GREEN | 29 | No |
| UBUSDT | 5 | RED | 13 | No |
| UNITASUSDT | 6 | GREEN | 19 | No |
| UNIUSDT | 6 | RED | 25 | No |
| USDBRLUSDT | 6 | RED | 18 | No |
| USDJPYUSDT | 6 | RED | 5 | No |
| USELESSUSDT | 6 | GREEN | 22 | No |
| USUALUSDT | 6 | RED | 6 | No |
| VELVETUSDT | 6 | GREEN | 24 | No |
| VIRTUALUSDT | 6 | GREEN | 25 | No |
| VVVUSDT | 6 | RED | 37 | No |
| WIFUSDT | 6 | RED | 18 | No |
| WLDUSDT | 6 | RED | 28 | No |
| WLFIUSDT | 6 | GREEN | 19 | No |
| XLMUSDT | 6 | RED | 30 | No |
| XMRUSDT | 6 | GREEN | 29 | No |
| XPLUSDT | 6 | GREEN | 23 | No |
| XRPUSDT | 6 | RED | 34 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZECUSDT | 6 | RED | 32 | No |
| ZENUSDT | 3 | RED | 7 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZROUSDT | 6 | RED | 29 | No |
| 牛来USDT | 6 | GREEN | 10 | No |
| 龙虾USDT | 6 | GREEN | 20 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 50 | 110 |
| $1m–$10m 24h futures turnover | 50 | 110 |
| $10m–$100m 24h futures turnover | 23 | 83 |
| $100m+ 24h futures turnover | 5 | 45 |

## Profit-versus-loss summary (hypothetical book-walk outcomes)

- Positive outcomes: 2336; negative outcomes: 3964; flat: 0
- Win rate among scored outcomes: 37.1%
- Gross positive outcomes: 14825.447572 USDT
- Gross negative outcomes: 28871.980444 USDT
- Total estimated net after trading fees: -14046.532873 USDT
- Profit factor (gross gains / gross losses): 0.513
- Average winning outcome: 6.346510 USDT
- Average losing outcome: -7.283547 USDT
- Mean estimated net result: -40.20 bps

These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.

- Ticker-only reference outcomes (separate, not executable): 0

## Strategy breakdown

| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |
|---|---:|---:|---:|---:|
| breakdown | 1134 | 540 | 594 | -17.89 |
| breakout | 531 | 76 | 455 | -55.67 |
| ema_volume | 4635 | 1720 | 2915 | -43.89 |

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
