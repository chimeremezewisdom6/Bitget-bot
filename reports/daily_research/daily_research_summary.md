# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-24T12:53:32.795728+00:00
- Session ended UTC: not recorded
- Collector cycles: 6
- Distinct symbols observed: 252
- Current Bitget turnover-watchlist contracts: 128
- Market observation rows: 5200
- Candidate signals eligible for entry evaluation: 883
- Watch-only RSI conditions (no entry): 1445
- Two-snapshot order-book shadow outcomes: 7140
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 2121
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 454
- Breakout-based trend starts found: 7224 (LONG: 3136; SHORT: 4088)
- Average direction-matching candle share in first hour: 31.4%
- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 453
- Complete trend events with early-window measurements: 7148

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 7148 | 45.2% | 3902/7148 (54.6%) | 0.1222% |
| 10 | 7148 | 37.7% | 3903/7148 (54.6%) | 0.1364% |
| 15 | 7148 | 35.0% | 3879/7148 (54.3%) | 0.1384% |
| 20 | 7148 | 34.1% | 3744/7148 (52.4%) | 0.0876% |
| 30 | 7148 | 33.0% | 3615/7148 (50.6%) | 0.0358% |
| 60 | 7148 | 31.6% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 241
- LONG/SHORT ignition candidates (score at least 4/7): 25
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| MMTUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 1.0697% | 1.243% | 1.4179% | 2.234x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ELSAUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.5702% | -1.2567% | -0.7492% | 1.803x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| ACEUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.9915% | -2.3743% | 1.7255% | 2.432x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| SKYUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.496% | -1.5218% | -1.4262% | 1.921x | 0/4 | NO_CLEAR_OI_CONFIRMATION |
| ATOMUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.3444% | -0.6943% | -0.2383% | 3.305x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| MEGAUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.126% | -0.5772% | 0.3285% | 1.876x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| REUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.2366% | -0.4083% | -0.1646% | 2.304x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| EVAAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.7363% | 2.5763% | 3.2467% | 0.644x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ARBUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.0741% | -0.4429% | -0.3922% | 1.76x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| JUPUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1399% | -0.1865% | -0.2139% | 4.273x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| SHIBUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.0865% | -0.2591% | -0.3168% | 3.219x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| MUBARAKUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.4002% | -0.7092% | -0.4181% | 0.057x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| PONSUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.4944% | -1.8203% | -2.3472% | 0.885x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| CLSUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.591% | -0.5857% | 16.9657% | 5.122x | 0/2 | NEW_POSITION_BUILDING_AGGREGATE |
| SKYAIUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3537% | -0.8795% | -0.7137% | 0.438x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| ORDIUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1171% | -0.1949% | -0.1301% | 1.478x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| PIPPINUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 1.0304% | 2.2953% | 1.2075% | 0.421x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| STXUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.196% | -0.5857% | -0.2929% | 0.384x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| KUAISHOUUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2768% | -0.1584% | 0.2119% | 0.187x | 0/4 | NEW_POSITION_BUILDING_AGGREGATE |
| ALLOUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.4305% | -0.4809% | -0.4097% | 0.782x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| RIVERUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3697% | -0.3697% | 0.3248% | 1.931x | 0/1 | NEW_POSITION_BUILDING_AGGREGATE |
| PROSUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.2824% | 1.3411% | -0.3907% | 0.276x | 4/1 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| 2ZUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -1.365% | -0.8353% | -0.111% | 1.339x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| MOVEUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.5461% | -1.3336% | -2.0588% | 0.26x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| KAIAUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3564% | -0.8862% | -1.8579% | 0.126x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| ENAUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1372% | -0.232% | 0.091% | 0.783x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| SUIUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.0787% | -0.2357% | -0.4167% | 2.71x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| PIEVERSEUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2412% | 0.0442% | 0.3698% | 0.281x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PROMUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.3092% | 0.6709% | 0.653% | 1.455x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| ARIAUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -2.186% | -3.1078% | -2.0419% | 2.251x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| WLDUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.0% | -0.2186% | -0.0297% | 2.122x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| TRUMPUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.0968% | -0.8405% | -0.7542% | 2.472x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| AAVEUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1961% | -0.3698% | -0.2263% | 2.134x | 2/2 | NO_CLEAR_OI_CONFIRMATION |
| BCHUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.0051% | -0.0256% | 0.7588% | 2.135x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| XMRUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.2431% | 0.1194% | 0.3959% | 7.168x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| ZROUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.4023% | -0.5224% | -0.5787% | 24.628x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| ICNTUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2053% | -0.3076% | -0.2345% | 1.653x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| LSKUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.2031% | 0.2031% | 0.3152% | 10.618x | 2/0 | NEW_POSITION_BUILDING_AGGREGATE |
| HBARUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1202% | -0.4394% | -0.4696% | 6.242x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| DGAIUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1885% | 0.5476% | 0.5852% | 8.487x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |

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
| MANTAUSDT | LONG | 2026-11-25 07:53 | 36 | 13 | 11 | 36 / 60 | 60.0% | 9.0723%
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

## Mandatory 60-minute same-colour candle experiment

Each eligible symbol is checked up to five separate times. Every check uses the latest 60 fully closed one-minute candles; green and red candles are counted separately, doji candles count toward neither colour, and a result qualifies when either colour reaches at least 40. This is a research filter, not a trade instruction.

| Symbol | Checks recorded | Latest colour | Same-colour count | Qualified |
|---|---:|---|---:|---|
| 0GUSDT | 9 | RED | 12 | No |
| 1000BONKUSDT | 10 | RED | 12 | No |
| 2ZUSDT | 4 | GREEN | 24 | No |
| AAVEUSDT | 10 | GREEN | 31 | No |
| ACEUSDT | 10 | RED | 23 | No |
| ACUUSDT | 9 | RED | 4 | No |
| ADAUSDT | 10 | RED | 26 | No |
| AEONUSDT | 10 | RED | 17 | No |
| AEROUSDT | 10 | GREEN | 26 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AIXBTUSDT | 2 | RED | 7 | No |
| AKEUSDT | 10 | GREEN | 31 | No |
| ALGOUSDT | 10 | RED | 24 | No |
| ALICEUSDT | 2 | GREEN | 24 | No |
| ALLOUSDT | 10 | RED | 25 | No |
| ALTUSDT | 4 | RED | 11 | No |
| AMDLUSDT | 10 | RED | 18 | No |
| APRUSDT | 10 | RED | 15 | No |
| APTUSDT | 10 | GREEN | 28 | No |
| ARBUSDT | 10 | RED | 30 | No |
| ARIAUSDT | 10 | RED | 31 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARUSDT | 10 | RED | 14 | No |
| ARXUSDT | 10 | RED | 14 | No |
| ASTERUSDT | 10 | GREEN | 22 | No |
| ATOMUSDT | 10 | RED | 22 | No |
| ATUSDT | 10 | GREEN | 12 | No |
| AVAXUSDT | 10 | GREEN | 24 | No |
| AXISUSDT | 10 | GREEN | 21 | No |
| BABYUSDT | 10 | GREEN | 24 | No |
| BANKUSDT | 10 | RED | 18 | No |
| BARDUSDT | 10 | RED | 12 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 10 | RED | 31 | No |
| BEAMUSDT | 10 | RED | 13 | No |
| BEATUSDT | 10 | RED | 28 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 10 | GREEN | 16 | No |
| BIGTIMEUSDT | 3 | GREEN | 33 | No |
| BLESSUSDT | 10 | GREEN | 32 | No |
| BLURUSDT | 10 | GREEN | 18 | No |
| BNBUSDT | 10 | RED | 31 | No |
| BOMEUSDT | 10 | RED | 11 | No |
| BREVUSDT | 10 | RED | 16 | No |
| BRUSDT | 5 | GREEN | 11 | No |
| BTCUSDT | 10 | RED | 34 | No |
| BTWUSDT | 10 | GREEN | 30 | No |
| BUSDT | 4 | RED | 10 | No |
| CAKEUSDT | 4 | GREEN | 9 | No |
| CAPUSDT | 9 | GREEN | 10 | No |
| CFGUSDT | 10 | GREEN | 17 | No |
| CHIPUSDT | 10 | RED | 15 | No |
| CLSUSDT | 10 | RED | 8 | No |
| COOKIEUSDT | 7 | RED | 4 | No |
| CPUSDT | 10 | RED | 20 | No |
| CROSSUSDT | 10 | RED | 12 | No |
| CRVUSDT | 10 | RED | 20 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 10 | RED | 29 | No |
| CYBERUSDT | 10 | RED | 18 | No |
| CYSUSDT | 10 | GREEN | 33 | No |
| DASHUSDT | 7 | RED | 10 | No |
| DEXEUSDT | 10 | RED | 11 | No |
| DGAIUSDT | 10 | GREEN | 26 | No |
| DOGEUSDT | 10 | RED | 27 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 10 | GREEN | 35 | No |
| DOTUSDT | 10 | RED | 15 | No |
| EDGEUSDT | 5 | GREEN | 9 | No |
| EGLDUSDT | 6 | RED | 9 | No |
| EIGENUSDT | 9 | RED | 12 | No |
| ELICEUSDT | 8 | GREEN | 5 | No |
| ELSAUSDT | 10 | RED | 32 | No |
| ENAUSDT | 10 | GREEN | 30 | No |
| ENSOUSDT | 10 | GREEN | 26 | No |
| ENSUSDT | 9 | RED | 11 | No |
| ERAUSDT | 10 | RED | 24 | No |
| ETCUSDT | 10 | RED | 27 | No |
| ETHFIUSDT | 10 | GREEN | 19 | No |
| ETHUSDT | 10 | RED | 31 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 10 | GREEN | 35 | No |
| FARTCOINUSDT | 10 | GREEN | 29 | No |
| FCXUSDT | 10 | GREEN | 5 | No |
| FETUSDT | 10 | RED | 18 | No |
| FFUSDT | 6 | RED | 7 | No |
| FILUSDT | 10 | RED | 27 | No |
| FLOCKUSDT | 8 | GREEN | 9 | No |
| FLOKIUSDT | 10 | RED | 8 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 10 | RED | 14 | No |
| GPSUSDT | 8 | GREEN | 6 | No |
| GRAMUSDT | 10 | RED | 25 | No |
| GRASSUSDT | 10 | GREEN | 17 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 10 | RED | 13 | No |
| GWEIUSDT | 10 | RED | 24 | No |
| HBARUSDT | 10 | RED | 20 | No |
| HPQUSDT | 3 | RED | 10 | No |
| HUMAUSDT | 10 | RED | 11 | No |
| HUSDT | 10 | RED | 21 | No |
| HYPEUSDT | 10 | RED | 32 | No |
| ICNTUSDT | 10 | GREEN | 27 | No |
| ICPUSDT | 10 | GREEN | 24 | No |
| IDOLUSDT | 10 | GREEN | 27 | No |
| INFYUSDT | 1 | GREEN | 8 | No |
| INITUSDT | 10 | GREEN | 32 | No |
| INJUSDT | 10 | GREEN | 25 | No |
| INXUSDT | 10 | GREEN | 18 | No |
| IOSTUSDT | 10 | RED | 16 | No |
| IRYSUSDT | 10 | RED | 28 | No |
| JCTUSDT | 10 | RED | 24 | No |
| JNJUSDT | 7 | RED | 10 | No |
| JTOUSDT | 10 | RED | 11 | No |
| JUPUSDT | 10 | GREEN | 19 | No |
| KAIAUSDT | 1 | GREEN | 13 | No |
| KAITOUSDT | 10 | RED | 18 | No |
| KASUSDT | 10 | RED | 26 | No |
| KAVAUSDT | 8 | GREEN | 12 | No |
| KERNELUSDT | 10 | RED | 16 | No |
| KGENUSDT | 9 | GREEN | 18 | No |
| KITEUSDT | 10 | GREEN | 24 | No |
| KUAISHOUUSDT | 10 | RED | 13 | No |
| LABUSDT | 10 | RED | 20 | No |
| LAUSDT | 7 | RED | 13 | No |
| LDOUSDT | 10 | GREEN | 9 | No |
| LINKUSDT | 10 | RED | 31 | No |
| LISTAUSDT | 10 | RED | 37 | No |
| LITUSDT | 10 | GREEN | 11 | No |
| LSKUSDT | 10 | RED | 12 | No |
| LTCUSDT | 10 | GREEN | 26 | No |
| LUNCUSDT | 10 | RED | 24 | No |
| MAGICUSDT | 9 | RED | 14 | No |
| MAGMAUSDT | 9 | RED | 16 | No |
| MANTAUSDT | 2 | GREEN | 28 | No |
| MANTRAUSDT | 4 | GREEN | 29 | No |
| MARSCOINUSDT | 10 | GREEN | 12 | No |
| MDTUSDT | 2 | GREEN | 3 | No |
| MEGAUSDT | 10 | RED | 19 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 7 | RED | 4 | No |
| MEUSDT | 8 | RED | 21 | No |
| MMTUSDT | 10 | GREEN | 36 | No |
| MONUSDT | 10 | GREEN | 29 | No |
| MOODENGUSDT | 2 | GREEN | 31 | No |
| MORPHOUSDT | 8 | GREEN | 19 | No |
| MOVEUSDT | 2 | RED | 25 | No |
| MOVRUSDT | 2 | RED | 8 | No |
| MSUSDT | 7 | RED | 6 | No |
| MUBARAKUSDT | 10 | GREEN | 25 | No |
| MYXUSDT | 9 | GREEN | 8 | No |
| NAORISUSDT | 10 | RED | 32 | No |
| NEARUSDT | 10 | GREEN | 31 | No |
| NEMUSDT | 7 | RED | 8 | No |
| NIGHTUSDT | 10 | RED | 23 | No |
| NILUSDT | 10 | GREEN | 12 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 10 | GREEN | 26 | No |
| ONEUSDT | 8 | GREEN | 20 | No |
| ONGUSDT | 10 | GREEN | 13 | No |
| OPGUSDT | 8 | RED | 32 | No |
| OPUSDT | 10 | RED | 15 | No |
| ORCAUSDT | 10 | RED | 16 | No |
| ORDERUSDT | 5 | RED | 9 | No |
| ORDIUSDT | 10 | RED | 17 | No |
| OUSDT | 1 | RED | 15 | No |
| PBRUSDT | 8 | RED | 5 | No |
| PENDLEUSDT | 10 | RED | 26 | No |
| PENGUUSDT | 10 | RED | 25 | No |
| PEOPLEUSDT | 9 | RED | 17 | No |
| PEPEUSDT | 10 | RED | 32 | No |
| PHAUSDT | 8 | GREEN | 21 | No |
| PIEVERSEUSDT | 10 | RED | 30 | No |
| PIPPINUSDT | 10 | GREEN | 27 | No |
| PIUSDT | 10 | GREEN | 18 | No |
| PLUMEUSDT | 10 | RED | 19 | No |
| PNUTUSDT | 2 | RED | 12 | No |
| POLUSDT | 10 | RED | 22 | No |
| PONSUSDT | 10 | RED | 34 | No |
| POWERUSDT | 8 | GREEN | 26 | No |
| PROMUSDT | 10 | GREEN | 25 | No |
| PROSUSDT | 6 | RED | 31 | No |
| PUMPUSDT | 10 | RED | 28 | No |
| PYTHUSDT | 10 | RED | 27 | No |
| QNTUSDT | 10 | RED | 31 | No |
| QUSDT | 9 | RED | 19 | No |
| RAREUSDT | 10 | RED | 19 | No |
| RAVEUSDT | 10 | RED | 13 | No |
| RAYUSDT | 10 | GREEN | 18 | No |
| RENDERUSDT | 10 | RED | 31 | No |
| REUSDT | 10 | RED | 24 | No |
| RIVERUSDT | 10 | GREEN | 10 | No |
| RPLUSDT | 10 | RED | 5 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 10 | GREEN | 22 | No |
| SANDUSDT | 10 | RED | 32 | No |
| SAPIENUSDT | 9 | RED | 12 | No |
| SEIUSDT | 10 | RED | 23 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHELLUSDT | 3 | RED | 10 | No |
| SHIBUSDT | 10 | GREEN | 31 | No |
| SIRENUSDT | 3 | RED | 13 | No |
| SKYAIUSDT | 10 | RED | 32 | No |
| SKYUSDT | 10 | RED | 21 | No |
| SLXUSDT | 3 | GREEN | 32 | No |
| SOLUSDT | 10 | RED | 31 | No |
| SOONUSDT | 10 | RED | 13 | No |
| SOPHUSDT | 1 | RED | 16 | No |
| SPACEUSDT | 7 | GREEN | 13 | No |
| SPKUSDT | 9 | GREEN | 8 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 9 | RED | 14 | No |
| STONKUSDT | 2 | GREEN | 20 | No |
| STRKUSDT | 10 | GREEN | 19 | No |
| STXUSDT | 10 | RED | 18 | No |
| SUIUSDT | 10 | GREEN | 26 | No |
| SYNUSDT | 1 | RED | 15 | No |
| TAOUSDT | 10 | RED | 32 | No |
| TIAUSDT | 10 | RED | 23 | No |
| TRBUSDT | 4 | GREEN | 11 | No |
| TRUMPUSDT | 10 | RED | 26 | No |
| TRXUSDT | 10 | RED | 15 | No |
| TUTUSDT | 9 | RED | 11 | No |
| UAIUSDT | 10 | RED | 26 | No |
| UBUSDT | 5 | RED | 13 | No |
| UNITASUSDT | 10 | GREEN | 21 | No |
| UNIUSDT | 10 | GREEN | 27 | No |
| USDBRLUSDT | 10 | RED | 5 | No |
| USDJPYUSDT | 9 | GREEN | 5 | No |
| USELESSUSDT | 10 | GREEN | 23 | No |
| USUALUSDT | 10 | GREEN | 14 | No |
| VELVETUSDT | 10 | RED | 16 | No |
| VIRTUALUSDT | 10 | RED | 23 | No |
| VVVUSDT | 10 | GREEN | 29 | No |
| WAXPUSDT | 2 | RED | 25 | No |
| WIFUSDT | 10 | RED | 20 | No |
| WLDUSDT | 10 | RED | 28 | No |
| WLFIUSDT | 10 | RED | 17 | No |
| XLMUSDT | 10 | RED | 26 | No |
| XMRUSDT | 10 | RED | 29 | No |
| XPLUSDT | 10 | GREEN | 20 | No |
| XRPUSDT | 10 | RED | 32 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZBTUSDT | 2 | RED | 17 | No |
| ZECUSDT | 10 | RED | 33 | No |
| ZENUSDT | 7 | RED | 9 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZKUSDT | 3 | RED | 15 | No |
| ZROUSDT | 10 | RED | 25 | No |
| 牛来USDT | 10 | RED | 16 | No |
| 龙虾USDT | 10 | RED | 9 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 50 | 338 |
| $1m–$10m 24h futures turnover | 50 | 357 |
| $10m–$100m 24h futures turnover | 23 | 198 |
| $100m+ 24h futures turnover | 5 | 70 |

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
