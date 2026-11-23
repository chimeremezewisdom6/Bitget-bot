# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-23T11:29:36.710531+00:00
- Session ended UTC: not recorded
- Collector cycles: 4
- Distinct symbols observed: 204
- Current Bitget turnover-watchlist contracts: 11
- Market observation rows: 800
- Candidate signals eligible for entry evaluation: 166
- Watch-only RSI conditions (no entry): 318
- Two-snapshot order-book shadow outcomes: 999
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 3
- 60-minute same-colour candle checks: 800
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 203
- Breakout-based trend starts found: 3171 (LONG: 1428; SHORT: 1743)
- Average direction-matching candle share in first hour: 31.9%

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 200
- Complete trend events with early-window measurements: 3065

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 3065 | 44.9% | 1540/3065 (50.2%) | 0.0336% |
| 10 | 3065 | 37.8% | 1554/3065 (50.7%) | 0.0624% |
| 15 | 3065 | 35.4% | 1562/3065 (51.0%) | 0.0728% |
| 20 | 3065 | 34.5% | 1529/3065 (49.9%) | 0.0499% |
| 30 | 3065 | 33.5% | 1523/3065 (49.7%) | 0.0509% |
| 60 | 3065 | 32.4% | — | — |

| Symbol | Direction | Trend start (UTC) | Green | Red | Doji | Matching candles | Matching % | First-hour follow-through % |
|---|---|---|---:|---:|---:|---:|---:|---:|
| SKYUSDT | SHORT | 2026-11-23 07:49 | 17 | 40 | 3 | 40 / 60 | 66.67% | 6.3317%
| PROMUSDT | LONG | 2026-11-23 14:10 | 39 | 21 | 0 | 39 / 60 | 65.0% | 12.4267%
| CYSUSDT | LONG | 2026-11-23 16:29 | 38 | 22 | 0 | 38 / 60 | 63.33% | 10.4336%
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
| SOLUSDT | SHORT | 2026-11-23 15:41 | 26 | 34 | 0 | 34 / 60 | 56.67% | 1.8339%
| SOLUSDT | SHORT | 2026-11-23 16:41 | 25 | 34 | 1 | 34 / 60 | 56.67% | 0.5407%
| ZECUSDT | SHORT | 2026-11-23 15:55 | 26 | 34 | 0 | 34 / 60 | 56.67% | 1.7428%
| EVAAUSDT | SHORT | 2026-11-23 14:08 | 26 | 34 | 0 | 34 / 60 | 56.67% | -3.1755%
| ENAUSDT | LONG | 2026-11-23 03:11 | 34 | 26 | 0 | 34 / 60 | 56.67% | 1.1554%
| PIEVERSEUSDT | SHORT | 2026-11-23 07:51 | 26 | 34 | 0 | 34 / 60 | 56.67% | 1.216%
| PIEVERSEUSDT | SHORT | 2026-11-23 11:21 | 26 | 34 | 0 | 34 / 60 | 56.67% | 3.1707%
| PEPEUSDT | LONG | 2026-11-23 05:01 | 34 | 26 | 0 | 34 / 60 | 56.67% | 1.6849%
| SUIUSDT | LONG | 2026-11-23 10:54 | 34 | 24 | 2 | 34 / 60 | 56.67% | 0.2682%
| ELSAUSDT | LONG | 2026-11-23 01:02 | 34 | 24 | 2 | 34 / 60 | 56.67% | 4.061%
| ELSAUSDT | LONG | 2026-11-23 02:14 | 34 | 26 | 0 | 34 / 60 | 56.67% | 3.3116%
| BLESSUSDT | SHORT | 2026-11-23 16:36 | 26 | 34 | 0 | 34 / 60 | 56.67% | 7.8629%
| PROMUSDT | SHORT | 2026-11-23 19:22 | 23 | 34 | 3 | 34 / 60 | 56.67% | -1.935%
| ARIAUSDT | LONG | 2026-11-23 04:09 | 34 | 26 | 0 | 34 / 60 | 56.67% | 3.7698%
| ARIAUSDT | SHORT | 2026-11-23 15:50 | 26 | 34 | 0 | 34 / 60 | 56.67% | 8.5868%
| ACEUSDT | LONG | 2026-11-22 23:15 | 34 | 26 | 0 | 34 / 60 | 56.67% | 7.5581%
| ACEUSDT | LONG | 2026-11-23 00:29 | 34 | 24 | 2 | 34 / 60 | 56.67% | -2.7778%
| AKEUSDT | SHORT | 2026-11-23 00:05 | 26 | 34 | 0 | 34 / 60 | 56.67% | 1.2806%
| AKEUSDT | SHORT | 2026-11-23 08:04 | 26 | 34 | 0 | 34 / 60 | 56.67% | 1.274%
| BCHUSDT | SHORT | 2026-11-23 16:46 | 25 | 34 | 1 | 34 / 60 | 56.67% | 1.7136%
| CYSUSDT | LONG | 2026-11-23 07:15 | 34 | 23 | 3 | 34 / 60 | 56.67% | 9.9582%
| QNTUSDT | LONG | 2026-11-23 04:43 | 34 | 21 | 5 | 34 / 60 | 56.67% | 2.6826%
| QNTUSDT | LONG | 2026-11-23 09:09 | 34 | 24 | 2 | 34 / 60 | 56.67% | 0.9413%
| ALGOUSDT | LONG | 2026-11-23 08:26 | 34 | 19 | 7 | 34 / 60 | 56.67% | 2.1956%
| DOSUSDT | LONG | 2026-11-23 14:58 | 34 | 23 | 3 | 34 / 60 | 56.67% | 1.5723%
| DGAIUSDT | LONG | 2026-11-23 16:07 | 34 | 24 | 2 | 34 / 60 | 56.67% | 0.575%
| ZROUSDT | SHORT | 2026-11-23 19:20 | 25 | 34 | 1 | 34 / 60 | 56.67% | 2.6453%
| ENSOUSDT | SHORT | 2026-11-23 10:27 | 20 | 34 | 6 | 34 / 60 | 56.67% | 1.6338%
| FLOCKUSDT | LONG | 2026-11-23 13:55 | 34 | 26 | 0 | 34 / 60 | 56.67% | 8.259%
| BTWUSDT | LONG | 2026-11-23 11:25 | 34 | 26 | 0 | 34 / 60 | 56.67% | 9.3925%
| BTWUSDT | SHORT | 2026-11-23 19:15 | 24 | 34 | 2 | 34 / 60 | 56.67% | 0.8194%
| CYBERUSDT | LONG | 2026-11-23 12:30 | 34 | 22 | 4 | 34 / 60 | 56.67% | 2.1196%
| MUBARAKUSDT | LONG | 2026-11-23 10:22 | 34 | 19 | 7 | 34 / 60 | 56.67% | 7.2092%
| UNITASUSDT | LONG | 2026-11-23 06:00 | 34 | 24 | 2 | 34 / 60 | 56.67% | 0.0751%
| ETHFIUSDT | SHORT | 2026-11-23 16:21 | 23 | 34 | 3 | 34 / 60 | 56.67% | 1.3607%
| ONEUSDT | LONG | 2026-11-23 17:33 | 34 | 25 | 1 | 34 / 60 | 56.67% | 3.7236%
| PIPPINUSDT | LONG | 2026-11-23 13:46 | 34 | 24 | 2 | 34 / 60 | 56.67% | -1.0343%
| QUSDT | LONG | 2026-11-23 10:37 | 34 | 19 | 7 | 34 / 60 | 56.67% | 1.5107%
| MYXUSDT | LONG | 2026-11-23 14:10 | 34 | 25 | 1 | 34 / 60 | 56.67% | 0.727%
| BTCUSDT | SHORT | 2026-11-23 01:47 | 27 | 33 | 0 | 33 / 60 | 55.0% | 0.5239%
| BTCUSDT | SHORT | 2026-11-23 16:03 | 27 | 33 | 0 | 33 / 60 | 55.0% | 0.7979%
| SOLUSDT | LONG | 2026-11-23 05:21 | 33 | 27 | 0 | 33 / 60 | 55.0% | 0.38%
| SOLUSDT | SHORT | 2026-11-23 09:43 | 26 | 33 | 1 | 33 / 60 | 55.0% | 0.0845%
| SOLUSDT | SHORT | 2026-11-23 18:52 | 26 | 33 | 1 | 33 / 60 | 55.0% | 0.42%
| XRPUSDT | SHORT | 2026-11-23 16:02 | 27 | 33 | 0 | 33 / 60 | 55.0% | 1.5225%
| ZECUSDT | LONG | 2026-11-23 08:07 | 33 | 27 | 0 | 33 / 60 | 55.0% | 0.5216%
| HYPEUSDT | SHORT | 2026-11-23 01:37 | 26 | 33 | 1 | 33 / 60 | 55.0% | 0.8329%
| HYPEUSDT | SHORT | 2026-11-23 19:21 | 27 | 33 | 0 | 33 / 60 | 55.0% | 0.421%
| EVAAUSDT | SHORT | 2026-11-22 22:15 | 27 | 33 | 0 | 33 / 60 | 55.0% | 0.2424%
| EVAAUSDT | LONG | 2026-11-23 06:49 | 33 | 26 | 1 | 33 / 60 | 55.0% | -2.4956%
| PEPEUSDT | SHORT | 2026-11-23 01:44 | 24 | 33 | 3 | 33 / 60 | 55.0% | 1.1464%

## Mandatory 60-minute same-colour candle experiment

Each eligible symbol is checked up to five separate times. Every check uses the latest 60 fully closed one-minute candles; green and red candles are counted separately, doji candles count toward neither colour, and a result qualifies when either colour reaches at least 40. This is a research filter, not a trade instruction.

| Symbol | Checks recorded | Latest colour | Same-colour count | Qualified |
|---|---:|---|---:|---|
| 1000BONKUSDT | 4 | RED | 10 | No |
| AAVEUSDT | 4 | GREEN | 28 | No |
| ACEUSDT | 4 | GREEN | 25 | No |
| ADAUSDT | 4 | GREEN | 25 | No |
| AEONUSDT | 4 | RED | 9 | No |
| AEROUSDT | 4 | GREEN | 19 | No |
| AIOUSDT | 4 | GREEN | 9 | No |
| AKEUSDT | 4 | RED | 34 | No |
| ALGOUSDT | 4 | RED | 29 | No |
| ALLOUSDT | 4 | GREEN | 18 | No |
| AMDLUSDT | 4 | GREEN | 21 | No |
| APRUSDT | 4 | GREEN | 31 | No |
| APTUSDT | 4 | GREEN | 25 | No |
| ARBUSDT | 4 | GREEN | 29 | No |
| ARIAUSDT | 4 | GREEN | 32 | No |
| ARKMUSDT | 4 | RED | 4 | No |
| ARUSDT | 4 | GREEN | 14 | No |
| ASTERUSDT | 4 | GREEN | 24 | No |
| ATOMUSDT | 4 | GREEN | 25 | No |
| AVAXUSDT | 4 | RED | 28 | No |
| AXISUSDT | 4 | GREEN | 22 | No |
| BANKUSDT | 4 | RED | 12 | No |
| BARDUSDT | 4 | RED | 11 | No |
| BATUSDT | 4 | RED | 14 | No |
| BCHUSDT | 4 | GREEN | 30 | No |
| BEAMUSDT | 4 | GREEN | 7 | No |
| BEATUSDT | 4 | GREEN | 30 | No |
| BERAUSDT | 4 | GREEN | 9 | No |
| BGBUSDT | 4 | GREEN | 6 | No |
| BLESSUSDT | 4 | RED | 33 | No |
| BLURUSDT | 4 | GREEN | 9 | No |
| BNBUSDT | 4 | GREEN | 32 | No |
| BOMEUSDT | 4 | RED | 11 | No |
| BREVUSDT | 4 | RED | 20 | No |
| BRUSDT | 4 | GREEN | 12 | No |
| BTCUSDT | 4 | GREEN | 35 | No |
| BTWUSDT | 4 | RED | 30 | No |
| CAPUSDT | 4 | RED | 30 | No |
| CFGUSDT | 4 | GREEN | 21 | No |
| CHIPUSDT | 4 | GREEN | 18 | No |
| CLSUSDT | 4 | RED | 17 | No |
| COOKIEUSDT | 3 | RED | 12 | No |
| CPUSDT | 4 | GREEN | 13 | No |
| CROSSUSDT | 4 | RED | 26 | No |
| CRVUSDT | 4 | GREEN | 19 | No |
| CSTOCKUSDT | 4 | GREEN | 12 | No |
| CTUSDT | 4 | GREEN | 26 | No |
| CYBERUSDT | 4 | GREEN | 20 | No |
| CYSUSDT | 4 | RED | 31 | No |
| DASHUSDT | 4 | RED | 12 | No |
| DEXEUSDT | 4 | RED | 11 | No |
| DGAIUSDT | 4 | RED | 34 | No |
| DOGEUSDT | 4 | RED | 29 | No |
| DOODUSDT | 3 | GREEN | 7 | No |
| DOSUSDT | 4 | RED | 17 | No |
| DOTUSDT | 4 | GREEN | 12 | No |
| EDGEUSDT | 4 | RED | 9 | No |
| EIGENUSDT | 1 | RED | 19 | No |
| ELICEUSDT | 4 | GREEN | 6 | No |
| ELSAUSDT | 4 | GREEN | 30 | No |
| ENAUSDT | 4 | RED | 30 | No |
| ENSOUSDT | 4 | RED | 26 | No |
| ENSUSDT | 4 | RED | 16 | No |
| ERAUSDT | 4 | RED | 15 | No |
| ETCUSDT | 4 | GREEN | 22 | No |
| ETHFIUSDT | 4 | GREEN | 21 | No |
| ETHUSDT | 4 | RED | 34 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 4 | RED | 31 | No |
| FARTCOINUSDT | 4 | RED | 29 | No |
| FCXUSDT | 4 | GREEN | 3 | No |
| FETUSDT | 4 | GREEN | 20 | No |
| FILUSDT | 4 | RED | 29 | No |
| FLOCKUSDT | 4 | RED | 21 | No |
| FLOKIUSDT | 4 | GREEN | 11 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 4 | GREEN | 5 | No |
| GALAUSDT | 4 | GREEN | 12 | No |
| GPSUSDT | 4 | GREEN | 6 | No |
| GRAMUSDT | 4 | GREEN | 26 | No |
| GRASSUSDT | 4 | GREEN | 18 | No |
| GRTUSDT | 4 | RED | 7 | No |
| GRVTUSDT | 4 | RED | 25 | No |
| GWEIUSDT | 4 | RED | 7 | No |
| HBARUSDT | 4 | RED | 26 | No |
| HUMAUSDT | 4 | GREEN | 12 | No |
| HUSDT | 4 | RED | 21 | No |
| HYPEUSDT | 4 | GREEN | 34 | No |
| ICNTUSDT | 4 | GREEN | 26 | No |
| ICPUSDT | 4 | RED | 25 | No |
| IDOLUSDT | 4 | RED | 31 | No |
| INITUSDT | 4 | GREEN | 33 | No |
| INJUSDT | 4 | RED | 32 | No |
| INXUSDT | 4 | GREEN | 30 | No |
| IOSTUSDT | 4 | GREEN | 9 | No |
| IRYSUSDT | 4 | RED | 20 | No |
| JCTUSDT | 4 | RED | 22 | No |
| JTOUSDT | 4 | GREEN | 12 | No |
| JUPUSDT | 4 | RED | 25 | No |
| KAITOUSDT | 4 | RED | 16 | No |
| KASUSDT | 4 | RED | 14 | No |
| KAVAUSDT | 4 | RED | 16 | No |
| KERNELUSDT | 4 | RED | 22 | No |
| KGENUSDT | 4 | RED | 22 | No |
| KITEUSDT | 4 | GREEN | 10 | No |
| KUAISHOUUSDT | 4 | RED | 5 | No |
| LABUSDT | 4 | RED | 17 | No |
| LAUSDT | 3 | RED | 13 | No |
| LDOUSDT | 4 | RED | 13 | No |
| LINKUSDT | 4 | GREEN | 30 | No |
| LISTAUSDT | 4 | GREEN | 23 | No |
| LITUSDT | 4 | RED | 27 | No |
| LSKUSDT | 4 | GREEN | 23 | No |
| LTCUSDT | 4 | RED | 30 | No |
| LUNCUSDT | 4 | GREEN | 16 | No |
| MAGMAUSDT | 4 | GREEN | 23 | No |
| MARSCOINUSDT | 4 | RED | 15 | No |
| MEGAUSDT | 4 | RED | 16 | No |
| MELANIAUSDT | 4 | GREEN | 3 | No |
| METUSDT | 4 | GREEN | 12 | No |
| MMTUSDT | 4 | GREEN | 30 | No |
| MONUSDT | 4 | RED | 18 | No |
| MORPHOUSDT | 4 | GREEN | 17 | No |
| MSUSDT | 4 | RED | 9 | No |
| MUBARAKUSDT | 4 | GREEN | 29 | No |
| MYXUSDT | 4 | GREEN | 10 | No |
| NAORISUSDT | 4 | RED | 19 | No |
| NEARUSDT | 4 | RED | 30 | No |
| NEMUSDT | 4 | GREEN | 5 | No |
| NIGHTUSDT | 4 | RED | 20 | No |
| NILUSDT | 4 | GREEN | 9 | No |
| NUUSDT | 4 | GREEN | 7 | No |
| ONDOUSDT | 4 | RED | 27 | No |
| ONEUSDT | 4 | GREEN | 29 | No |
| OPGUSDT | 3 | RED | 7 | No |
| OPUSDT | 4 | RED | 12 | No |
| ORCAUSDT | 4 | GREEN | 10 | No |
| ORDIUSDT | 4 | RED | 19 | No |
| PENDLEUSDT | 4 | RED | 20 | No |
| PENGUUSDT | 4 | GREEN | 23 | No |
| PEOPLEUSDT | 1 | RED | 18 | No |
| PEPEUSDT | 4 | GREEN | 30 | No |
| PHAUSDT | 4 | GREEN | 18 | No |
| PIEVERSEUSDT | 4 | GREEN | 30 | No |
| PIPPINUSDT | 4 | RED | 21 | No |
| PIUSDT | 4 | GREEN | 23 | No |
| PLUMEUSDT | 4 | RED | 12 | No |
| POLUSDT | 4 | GREEN | 17 | No |
| PONSUSDT | 4 | RED | 30 | No |
| POWERUSDT | 4 | GREEN | 20 | No |
| PROMUSDT | 4 | GREEN | 34 | No |
| PUMPUSDT | 4 | RED | 31 | No |
| PYTHUSDT | 4 | GREEN | 23 | No |
| QNTUSDT | 4 | RED | 31 | No |
| QUSDT | 4 | RED | 20 | No |
| RAREUSDT | 4 | GREEN | 20 | No |
| RAVEUSDT | 4 | RED | 14 | No |
| RAYUSDT | 4 | GREEN | 16 | No |
| RENDERUSDT | 4 | GREEN | 28 | No |
| REUSDT | 4 | RED | 15 | No |
| RUNEUSDT | 4 | RED | 17 | No |
| SANDUSDT | 4 | GREEN | 27 | No |
| SAPIENUSDT | 4 | RED | 9 | No |
| SEIUSDT | 4 | RED | 27 | No |
| SENTUSDT | 4 | GREEN | 13 | No |
| SHIBUSDT | 4 | GREEN | 24 | No |
| SKYAIUSDT | 4 | GREEN | 20 | No |
| SKYUSDT | 4 | RED | 22 | No |
| SOLUSDT | 4 | RED | 32 | No |
| SOONUSDT | 4 | RED | 4 | No |
| SPKUSDT | 4 | GREEN | 8 | No |
| SPXUSDT | 3 | GREEN | 7 | No |
| STRKUSDT | 4 | RED | 30 | No |
| STXUSDT | 4 | RED | 14 | No |
| SUIUSDT | 4 | RED | 28 | No |
| TAOUSDT | 4 | GREEN | 32 | No |
| TIAUSDT | 4 | RED | 30 | No |
| TRUMPUSDT | 4 | RED | 29 | No |
| TRXUSDT | 4 | GREEN | 16 | No |
| TUTUSDT | 4 | GREEN | 4 | No |
| UAIUSDT | 4 | GREEN | 23 | No |
| UBUSDT | 3 | GREEN | 15 | No |
| UNITASUSDT | 4 | GREEN | 17 | No |
| UNIUSDT | 4 | RED | 30 | No |
| USDBRLUSDT | 4 | GREEN | 17 | No |
| USDJPYUSDT | 4 | GREEN | 4 | No |
| USELESSUSDT | 4 | GREEN | 22 | No |
| USUALUSDT | 4 | RED | 12 | No |
| VELVETUSDT | 4 | RED | 24 | No |
| VIRTUALUSDT | 4 | GREEN | 24 | No |
| VVVUSDT | 4 | RED | 29 | No |
| WIFUSDT | 4 | GREEN | 17 | No |
| WLDUSDT | 4 | GREEN | 25 | No |
| WLFIUSDT | 4 | RED | 15 | No |
| XLMUSDT | 4 | GREEN | 30 | No |
| XMRUSDT | 4 | GREEN | 34 | No |
| XPLUSDT | 4 | RED | 26 | No |
| XRPUSDT | 4 | RED | 32 | No |
| XVGUSDT | 4 | GREEN | 15 | No |
| ZECUSDT | 4 | GREEN | 31 | No |
| ZESTUSDT | 4 | RED | 9 | No |
| ZROUSDT | 4 | RED | 29 | No |
| 牛来USDT | 4 | GREEN | 9 | No |
| 龙虾USDT | 4 | GREEN | 14 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 3 | 12 |
| $1m–$10m 24h futures turnover | 3 | 12 |
| $10m–$100m 24h futures turnover | 3 | 12 |
| $100m+ 24h futures turnover | 2 | 8 |

## Profit-versus-loss summary (hypothetical book-walk outcomes)

- Positive outcomes: 468; negative outcomes: 531; flat: 0
- Win rate among scored outcomes: 46.8%
- Gross positive outcomes: 2464.213630 USDT
- Gross negative outcomes: 2059.340224 USDT
- Total estimated net after trading fees: 404.873406 USDT
- Profit factor (gross gains / gross losses): 1.197
- Average winning outcome: 5.265414 USDT
- Average losing outcome: -3.878230 USDT
- Mean estimated net result: 9.15 bps

These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.

- Ticker-only reference outcomes (separate, not executable): 0

## Strategy breakdown

| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |
|---|---:|---:|---:|---:|
| breakdown | 216 | 99 | 117 | -14.02 |
| breakout | 18 | 9 | 9 | 291.81 |
| ema_volume | 765 | 360 | 405 | 9.04 |

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
- shadow_experiments.jsonl — signals, partial entry/exit records, book-walk outcomes and unavailable evaluations.
- collection_errors.jsonl — Bitget API and processing failures.
