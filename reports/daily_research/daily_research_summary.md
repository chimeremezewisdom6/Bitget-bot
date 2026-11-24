# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-24T12:53:32.795728+00:00
- Session ended UTC: not recorded
- Collector cycles: 2
- Distinct symbols observed: 224
- Current Bitget turnover-watchlist contracts: 128
- Market observation rows: 4400
- Candidate signals eligible for entry evaluation: 760
- Watch-only RSI conditions (no entry): 1310
- Two-snapshot order-book shadow outcomes: 6300
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 1487
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
- LONG/SHORT ignition candidates (score at least 4/7): 20
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| QNTUSDT | LONG | 7 / 7 | IGNITION_CANDIDATE | 0.3356% | 0.6395% | 0.4624% | 2.565x | 4/0 | NEW_POSITION_BUILDING_AGGREGATE |
| MAGMAUSDT | LONG | 7 / 7 | IGNITION_CANDIDATE | 0.4834% | 0.6998% | 0.5058% | 2.638x | 4/0 | NEW_POSITION_BUILDING_AGGREGATE |
| BLESSUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 4.3059% | 10.7407% | 8.1057% | 0.771x | 5/0 | NEW_POSITION_BUILDING_AGGREGATE |
| BEATUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 0.5293% | 0.5884% | 0.2575% | 1.658x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| INXUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 1.1183% | 3.048% | -1.2297% | 4.917x | 3/2 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| LUNCUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.9154% | 1.4363% | -3.9664% | 1.477x | 4/0 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| PBRUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.5% | 0.1917% | -5.7489% | 1.97x | 1/1 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| ENAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1912% | 1.0044% | 1.2359% | 1.856x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| EVAAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 3.3772% | 2.9326% | 1.5235% | 0.648x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| LISTAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 1.5457% | 0.8678% | 6.1905% | 2.325x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| BCHUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | 0.1005% | 0.297% | 0.3244% | 2.196x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ICNTUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3289% | -0.5075% | 0.3545% | 0.905x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ASTERUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1206% | 0.2012% | 0.1261% | 5.624x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.2727% | 0.7121% | 0.4982% | 0.093x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| RPLUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.3284% | 0.4934% | 2.7303% | 4.551x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PIPPINUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.3941% | 0.4507% | 0.4668% | 0.245x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| QUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.8119% | 1.6218% | 0.4689% | 1.323x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| GWEIUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.478% | 0.478% | 0.4141% | 0.097x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| NAORISUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.0943% | 0.4422% | 1.0767% | 0.108x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| PROSUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.7348% | 0.5869% | 0.4461% | 0.282x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PEPEUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1219% | 0.2412% | 0.4687% | 0.33x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| ARIAUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.6176% | 2.5552% | 0.7045% | 0.341x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PUMPUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2848% | 0.9005% | 1.033% | 0.297x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| TAOUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1465% | 0.1899% | 0.3515% | 0.674x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| TRUMPUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1671% | 0.3589% | 0.6014% | 0.546x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |
| XLMUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1746% | 0.0396% | -0.0085% | 0.784x | 4/1 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| ZROUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.0583% | -0.0194% | 1.2285% | 1.918x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| FETUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2812% | 0.4695% | 0.4106% | 0.299x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| SEIUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.0598% | 0.1499% | 0.4151% | 4.896x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| 牛来USDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.24% | 1.0209% | 2.6584% | 2.208x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| IDOLUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5814% | -0.25% | 0.0677% | 0.497x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| BTWUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.4589% | 0.6402% | 0.0092% | 1.129x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| CYBERUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.4358% | 0.3387% | 0.1548% | 7.042x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| SAPIENUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1539% | -0.4602% | -0.0357% | 16.368x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| LITUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1673% | 0.7573% | 0.5491% | 0.538x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| CAPUSDT | LONG | 3 / 7 | EARLY_PRESSURE | -0.2789% | 0.4056% | 1.2356% | 3.84x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| KERNELUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.3539% | -0.6585% | -0.3678% | 3.474x | 1/1 | NO_CLEAR_OI_CONFIRMATION |
| KITEUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2714% | 0.3412% | -0.5773% | 0.052x | 3/0 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| MAGICUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1521% | 0.3046% | 0.9179% | 0.084x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| 0GUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.3043% | -0.7071% | 0.4382% | 0.426x | 0/1 | NEW_POSITION_BUILDING_AGGREGATE |

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
| 0GUSDT | 7 | RED | 21 | No |
| 1000BONKUSDT | 7 | GREEN | 10 | No |
| AAVEUSDT | 7 | RED | 32 | No |
| ACEUSDT | 7 | RED | 23 | No |
| ACUUSDT | 7 | GREEN | 8 | No |
| ADAUSDT | 7 | RED | 22 | No |
| AEONUSDT | 7 | RED | 10 | No |
| AEROUSDT | 7 | RED | 16 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AKEUSDT | 7 | GREEN | 32 | No |
| ALGOUSDT | 7 | RED | 17 | No |
| ALLOUSDT | 7 | GREEN | 21 | No |
| AMDLUSDT | 7 | RED | 16 | No |
| APRUSDT | 7 | RED | 25 | No |
| APTUSDT | 7 | RED | 27 | No |
| ARBUSDT | 7 | RED | 33 | No |
| ARIAUSDT | 7 | GREEN | 31 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARUSDT | 7 | RED | 12 | No |
| ARXUSDT | 7 | RED | 25 | No |
| ASTERUSDT | 7 | GREEN | 18 | No |
| ATOMUSDT | 7 | RED | 20 | No |
| ATUSDT | 7 | RED | 20 | No |
| AVAXUSDT | 7 | RED | 29 | No |
| AXISUSDT | 7 | RED | 13 | No |
| BABYUSDT | 7 | GREEN | 24 | No |
| BANKUSDT | 7 | RED | 14 | No |
| BARDUSDT | 7 | RED | 16 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 7 | RED | 30 | No |
| BEAMUSDT | 7 | RED | 9 | No |
| BEATUSDT | 7 | GREEN | 29 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 7 | GREEN | 9 | No |
| BLESSUSDT | 7 | RED | 31 | No |
| BLURUSDT | 7 | RED | 11 | No |
| BNBUSDT | 7 | GREEN | 29 | No |
| BOMEUSDT | 7 | RED | 11 | No |
| BREVUSDT | 7 | GREEN | 16 | No |
| BRUSDT | 5 | GREEN | 11 | No |
| BTCUSDT | 7 | GREEN | 30 | No |
| BTWUSDT | 7 | RED | 25 | No |
| CAPUSDT | 7 | GREEN | 23 | No |
| CFGUSDT | 7 | RED | 9 | No |
| CHIPUSDT | 7 | RED | 15 | No |
| CLSUSDT | 7 | GREEN | 6 | No |
| COOKIEUSDT | 7 | RED | 4 | No |
| CPUSDT | 7 | RED | 14 | No |
| CROSSUSDT | 7 | GREEN | 25 | No |
| CRVUSDT | 7 | RED | 13 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 7 | GREEN | 24 | No |
| CYBERUSDT | 7 | GREEN | 21 | No |
| CYSUSDT | 7 | GREEN | 33 | No |
| DASHUSDT | 7 | RED | 10 | No |
| DEXEUSDT | 7 | GREEN | 7 | No |
| DGAIUSDT | 7 | GREEN | 28 | No |
| DOGEUSDT | 7 | RED | 32 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 7 | RED | 28 | No |
| DOTUSDT | 7 | GREEN | 13 | No |
| EDGEUSDT | 5 | GREEN | 9 | No |
| EGLDUSDT | 4 | RED | 9 | No |
| EIGENUSDT | 7 | RED | 12 | No |
| ELICEUSDT | 7 | RED | 3 | No |
| ELSAUSDT | 7 | RED | 32 | No |
| ENAUSDT | 7 | GREEN | 31 | No |
| ENSOUSDT | 7 | RED | 29 | No |
| ENSUSDT | 7 | RED | 17 | No |
| ERAUSDT | 7 | RED | 20 | No |
| ETCUSDT | 7 | GREEN | 24 | No |
| ETHFIUSDT | 7 | RED | 17 | No |
| ETHUSDT | 7 | RED | 31 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 7 | GREEN | 32 | No |
| FARTCOINUSDT | 7 | RED | 24 | No |
| FCXUSDT | 7 | RED | 11 | No |
| FETUSDT | 7 | GREEN | 18 | No |
| FFUSDT | 3 | RED | 10 | No |
| FILUSDT | 7 | GREEN | 28 | No |
| FLOCKUSDT | 7 | GREEN | 4 | No |
| FLOKIUSDT | 7 | GREEN | 6 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 7 | GREEN | 12 | No |
| GPSUSDT | 7 | RED | 4 | No |
| GRAMUSDT | 7 | GREEN | 20 | No |
| GRASSUSDT | 7 | GREEN | 22 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 7 | RED | 11 | No |
| GWEIUSDT | 7 | GREEN | 14 | No |
| HBARUSDT | 7 | RED | 19 | No |
| HUMAUSDT | 7 | RED | 18 | No |
| HUSDT | 7 | RED | 28 | No |
| HYPEUSDT | 7 | RED | 37 | No |
| ICNTUSDT | 7 | GREEN | 33 | No |
| ICPUSDT | 7 | RED | 20 | No |
| IDOLUSDT | 7 | RED | 30 | No |
| INITUSDT | 7 | RED | 29 | No |
| INJUSDT | 7 | RED | 27 | No |
| INXUSDT | 7 | RED | 28 | No |
| IOSTUSDT | 7 | RED | 8 | No |
| IRYSUSDT | 7 | RED | 23 | No |
| JCTUSDT | 7 | GREEN | 21 | No |
| JNJUSDT | 4 | GREEN | 10 | No |
| JTOUSDT | 7 | RED | 17 | No |
| JUPUSDT | 7 | GREEN | 25 | No |
| KAITOUSDT | 7 | RED | 10 | No |
| KASUSDT | 7 | RED | 12 | No |
| KAVAUSDT | 5 | RED | 15 | No |
| KERNELUSDT | 7 | GREEN | 17 | No |
| KGENUSDT | 7 | RED | 26 | No |
| KITEUSDT | 7 | GREEN | 30 | No |
| KUAISHOUUSDT | 7 | RED | 7 | No |
| LABUSDT | 7 | GREEN | 20 | No |
| LAUSDT | 5 | RED | 15 | No |
| LDOUSDT | 7 | RED | 17 | No |
| LINKUSDT | 7 | RED | 30 | No |
| LISTAUSDT | 7 | GREEN | 31 | No |
| LITUSDT | 7 | GREEN | 15 | No |
| LSKUSDT | 7 | RED | 8 | No |
| LTCUSDT | 7 | RED | 32 | No |
| LUNCUSDT | 7 | RED | 31 | No |
| MAGICUSDT | 7 | RED | 13 | No |
| MAGMAUSDT | 7 | GREEN | 24 | No |
| MARSCOINUSDT | 7 | GREEN | 8 | No |
| MEGAUSDT | 7 | RED | 18 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 7 | RED | 4 | No |
| MEUSDT | 5 | GREEN | 10 | No |
| MMTUSDT | 7 | GREEN | 28 | No |
| MONUSDT | 7 | RED | 20 | No |
| MORPHOUSDT | 7 | GREEN | 9 | No |
| MSUSDT | 7 | RED | 6 | No |
| MUBARAKUSDT | 7 | RED | 29 | No |
| MYXUSDT | 7 | RED | 14 | No |
| NAORISUSDT | 7 | GREEN | 29 | No |
| NEARUSDT | 7 | GREEN | 30 | No |
| NEMUSDT | 7 | RED | 8 | No |
| NIGHTUSDT | 7 | GREEN | 28 | No |
| NILUSDT | 7 | RED | 27 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 7 | GREEN | 24 | No |
| ONEUSDT | 7 | GREEN | 19 | No |
| ONGUSDT | 7 | RED | 15 | No |
| OPGUSDT | 5 | RED | 6 | No |
| OPUSDT | 7 | RED | 13 | No |
| ORCAUSDT | 7 | RED | 9 | No |
| ORDERUSDT | 2 | GREEN | 7 | No |
| ORDIUSDT | 7 | GREEN | 18 | No |
| PBRUSDT | 7 | GREEN | 9 | No |
| PENDLEUSDT | 7 | RED | 21 | No |
| PENGUUSDT | 7 | RED | 25 | No |
| PEOPLEUSDT | 5 | RED | 14 | No |
| PEPEUSDT | 7 | RED | 32 | No |
| PHAUSDT | 7 | GREEN | 6 | No |
| PIEVERSEUSDT | 7 | RED | 31 | No |
| PIPPINUSDT | 7 | RED | 26 | No |
| PIUSDT | 7 | RED | 16 | No |
| PLUMEUSDT | 7 | GREEN | 6 | No |
| POLUSDT | 7 | RED | 13 | No |
| PONSUSDT | 7 | GREEN | 29 | No |
| POWERUSDT | 7 | RED | 14 | No |
| PROMUSDT | 7 | RED | 24 | No |
| PROSUSDT | 3 | GREEN | 32 | No |
| PUMPUSDT | 7 | GREEN | 27 | No |
| PYTHUSDT | 7 | GREEN | 14 | No |
| QNTUSDT | 7 | GREEN | 28 | No |
| QUSDT | 7 | GREEN | 23 | No |
| RAREUSDT | 7 | GREEN | 12 | No |
| RAVEUSDT | 7 | GREEN | 9 | No |
| RAYUSDT | 7 | RED | 14 | No |
| RENDERUSDT | 7 | GREEN | 24 | No |
| REUSDT | 7 | GREEN | 19 | No |
| RIVERUSDT | 7 | RED | 16 | No |
| RPLUSDT | 7 | GREEN | 13 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 7 | GREEN | 29 | No |
| SANDUSDT | 7 | GREEN | 32 | No |
| SAPIENUSDT | 7 | RED | 12 | No |
| SEIUSDT | 7 | RED | 21 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHIBUSDT | 7 | RED | 24 | No |
| SKYAIUSDT | 7 | RED | 19 | No |
| SKYUSDT | 7 | GREEN | 24 | No |
| SOLUSDT | 7 | RED | 33 | No |
| SOONUSDT | 7 | RED | 12 | No |
| SPACEUSDT | 4 | GREEN | 20 | No |
| SPKUSDT | 7 | RED | 6 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 7 | RED | 8 | No |
| STRKUSDT | 7 | RED | 19 | No |
| STXUSDT | 7 | RED | 14 | No |
| SUIUSDT | 7 | GREEN | 29 | No |
| TAOUSDT | 7 | GREEN | 29 | No |
| TIAUSDT | 7 | GREEN | 23 | No |
| TRUMPUSDT | 7 | RED | 30 | No |
| TRXUSDT | 7 | RED | 16 | No |
| TUTUSDT | 7 | GREEN | 10 | No |
| UAIUSDT | 7 | GREEN | 29 | No |
| UBUSDT | 5 | RED | 13 | No |
| UNITASUSDT | 7 | GREEN | 19 | No |
| UNIUSDT | 7 | RED | 25 | No |
| USDBRLUSDT | 7 | RED | 18 | No |
| USDJPYUSDT | 7 | RED | 5 | No |
| USELESSUSDT | 7 | GREEN | 21 | No |
| USUALUSDT | 7 | RED | 6 | No |
| VELVETUSDT | 7 | GREEN | 24 | No |
| VIRTUALUSDT | 7 | GREEN | 25 | No |
| VVVUSDT | 7 | RED | 36 | No |
| WIFUSDT | 7 | RED | 18 | No |
| WLDUSDT | 7 | RED | 28 | No |
| WLFIUSDT | 7 | GREEN | 19 | No |
| XLMUSDT | 7 | RED | 29 | No |
| XMRUSDT | 7 | GREEN | 29 | No |
| XPLUSDT | 7 | RED | 23 | No |
| XRPUSDT | 7 | RED | 35 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZECUSDT | 7 | RED | 32 | No |
| ZENUSDT | 4 | RED | 7 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZROUSDT | 7 | RED | 28 | No |
| 牛来USDT | 7 | GREEN | 10 | No |
| 龙虾USDT | 7 | GREEN | 21 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 50 | 160 |
| $1m–$10m 24h futures turnover | 50 | 160 |
| $10m–$100m 24h futures turnover | 23 | 106 |
| $100m+ 24h futures turnover | 5 | 50 |

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
