# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-23T11:29:36.710531+00:00
- Session ended UTC: not recorded
- Collector cycles: 15
- Distinct symbols observed: 217
- Current Bitget turnover-watchlist contracts: 11
- Market observation rows: 3000
- Candidate signals eligible for entry evaluation: 565
- Watch-only RSI conditions (no entry): 957
- Two-snapshot order-book shadow outcomes: 3978
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 1070
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 216
- Breakout-based trend starts found: 3370 (LONG: 1520; SHORT: 1850)
- Average direction-matching candle share in first hour: 31.1%

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 215
- Complete trend events with early-window measurements: 3294

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 3294 | 44.1% | 1660/3294 (50.4%) | 0.0407% |
| 10 | 3294 | 36.9% | 1676/3294 (50.9%) | 0.0692% |
| 15 | 3294 | 34.5% | 1676/3294 (50.9%) | 0.0773% |
| 20 | 3294 | 33.6% | 1646/3294 (50.0%) | 0.0547% |
| 30 | 3294 | 32.5% | 1632/3294 (49.5%) | 0.0495% |
| 60 | 3294 | 31.5% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 200
- LONG/SHORT ignition candidates (score at least 4/7): 12
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| VVVUSDT | LONG | 7 / 7 | IGNITION_CANDIDATE | 1.1893% | 0.8574% | unavailable | 10.312x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| DGAIUSDT | LONG | 7 / 7 | IGNITION_CANDIDATE | 0.9454% | 1.5793% | unavailable | 5.951x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| RPLUSDT | SHORT | 6 / 7 | IGNITION_CANDIDATE | -0.7341% | -3.5658% | unavailable | 1.602x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| ELSAUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 0.4953% | 1.1816% | unavailable | 4.565x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| DOSUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 1.4936% | 2.1036% | unavailable | 2.227x | 5/0 | NEW_POSITION_BUILDING_AGGREGATE |
| MUBARAKUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 1.1508% | 1.5264% | unavailable | 1.299x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| NAORISUSDT | LONG | 5 / 7 | IGNITION_CANDIDATE | 1.0579% | 0.7913% | unavailable | 19.406x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| ARBUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.3768% | -1.0294% | unavailable | 0.664x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| AVAXUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.103% | -0.8763% | unavailable | 2.451x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| MONUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.8989% | 0.1487% | unavailable | 0.232x | 5/0 | NEW_POSITION_BUILDING_AGGREGATE |
| BREVUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.6206% | -1.7068% | unavailable | 69.737x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| PBRUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.518% | 0.6452% | unavailable | 12.051x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| PIEVERSEUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1195% | 0.4394% | unavailable | 1.589x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| MMTUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -2.2364% | -1.9624% | unavailable | 0.417x | 0/5 | NO_CLEAR_OI_CONFIRMATION |
| JUPUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1656% | -0.8635% | unavailable | 1.851x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| INXUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.126% | -3.413% | unavailable | 0.683x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| SAHARAUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -2.1129% | -3.5316% | unavailable | 3.63x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| APRUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.3414% | -0.5574% | unavailable | 1.017x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| TRXUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.0162% | -0.0324% | unavailable | 0.924x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| VELVETUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.7971% | -0.8095% | unavailable | 22.72x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| CHIPUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.4446% | -0.034% | unavailable | 1.657x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| MORPHOUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1536% | -0.575% | unavailable | 17.139x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| AXISUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.4083% | -1.7717% | unavailable | 0.188x | 0/3 | NO_CLEAR_OI_CONFIRMATION |
| ALLOUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1043% | -0.5561% | unavailable | 1.457x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| KERNELUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.8595% | 0.9533% | unavailable | 0.805x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| HYPEUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.0732% | -0.4144% | unavailable | 0.371x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| ENAUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.0977% | -0.6028% | unavailable | 1.53x | 2/2 | NO_CLEAR_OI_CONFIRMATION |
| SUIUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.0% | -0.7063% | unavailable | 0.619x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| AKEUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.6095% | -1.0805% | unavailable | 0.655x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| ACEUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.8043% | -1.4647% | unavailable | 1.142x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| INJUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.0953% | -0.5052% | unavailable | 0.695x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| LTCUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.0239% | -0.4288% | unavailable | 0.065x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| FARTCOINUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.0957% | -0.9119% | unavailable | 1.812x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| PENGUUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.067% | -0.7307% | unavailable | 4.415x | 3/1 | NO_CLEAR_OI_CONFIRMATION |
| HUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.1524% | -0.6823% | unavailable | 0.996x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| SEIUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.1159% | -0.7198% | unavailable | 0.285x | 2/2 | NO_CLEAR_OI_CONFIRMATION |
| TIAUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.2341% | -0.6669% | unavailable | 2.247x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| IRYSUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.4899% | -1.0353% | unavailable | 0.849x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| IDOLUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | 1.0441% | 0.1005% | unavailable | 0.834x | 5/0 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| BTWUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | 0.8982% | 0.6218% | unavailable | 0.125x | 3/0 | NEW_POSITION_BUILDING_AGGREGATE |

Scoring checks: aligned 5m/15m price acceleration, rising 15m OI, 5m turnover surge versus the prior 20m, directional candle pressure with real candle bodies, 20m breakout, 60m breakout, and higher-high/lower-low structure. Scores are evidence counts, not probabilities. A high score is a research watch candidate, not a buy/sell instruction. Rising aggregate OI means total outstanding positions increased; it does not reveal whether longs or shorts initiated them.

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
| RPLUSDT | LONG | 2026-11-24 02:39 | 34 | 24 | 2 | 34 / 60 | 56.67% | 5.3913%
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

## Mandatory 60-minute same-colour candle experiment

Each eligible symbol is checked up to five separate times. Every check uses the latest 60 fully closed one-minute candles; green and red candles are counted separately, doji candles count toward neither colour, and a result qualifies when either colour reaches at least 40. This is a research filter, not a trade instruction.

| Symbol | Checks recorded | Latest colour | Same-colour count | Qualified |
|---|---:|---|---:|---|
| 0GUSDT | 1 | GREEN | 10 | No |
| 1000BONKUSDT | 5 | RED | 10 | No |
| AAVEUSDT | 5 | GREEN | 29 | No |
| ACEUSDT | 5 | GREEN | 24 | No |
| ACUUSDT | 5 | GREEN | 9 | No |
| ADAUSDT | 5 | GREEN | 25 | No |
| AEONUSDT | 5 | RED | 9 | No |
| AEROUSDT | 5 | GREEN | 18 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AKEUSDT | 5 | RED | 33 | No |
| ALGOUSDT | 5 | RED | 28 | No |
| ALLOUSDT | 5 | RED | 18 | No |
| AMDLUSDT | 5 | GREEN | 21 | No |
| APRUSDT | 5 | GREEN | 31 | No |
| APTUSDT | 5 | RED | 27 | No |
| ARBUSDT | 5 | RED | 30 | No |
| ARIAUSDT | 5 | GREEN | 32 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARUSDT | 5 | GREEN | 16 | No |
| ARXUSDT | 5 | GREEN | 28 | No |
| ASTERUSDT | 5 | GREEN | 24 | No |
| ATOMUSDT | 5 | RED | 24 | No |
| ATUSDT | 5 | RED | 8 | No |
| AVAXUSDT | 5 | RED | 28 | No |
| AXISUSDT | 5 | GREEN | 21 | No |
| BABYUSDT | 5 | RED | 20 | No |
| BANKUSDT | 5 | GREEN | 11 | No |
| BARDUSDT | 5 | GREEN | 11 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 5 | GREEN | 30 | No |
| BEAMUSDT | 5 | RED | 7 | No |
| BEATUSDT | 5 | GREEN | 32 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 5 | GREEN | 6 | No |
| BLESSUSDT | 5 | RED | 32 | No |
| BLURUSDT | 5 | GREEN | 9 | No |
| BNBUSDT | 5 | GREEN | 31 | No |
| BOMEUSDT | 5 | RED | 12 | No |
| BREVUSDT | 5 | RED | 19 | No |
| BRUSDT | 5 | GREEN | 11 | No |
| BTCUSDT | 5 | GREEN | 34 | No |
| BTWUSDT | 5 | GREEN | 28 | No |
| CAPUSDT | 5 | RED | 30 | No |
| CFGUSDT | 5 | GREEN | 21 | No |
| CHIPUSDT | 5 | GREEN | 17 | No |
| CLSUSDT | 5 | RED | 15 | No |
| COOKIEUSDT | 5 | GREEN | 10 | No |
| CPUSDT | 5 | RED | 14 | No |
| CROSSUSDT | 5 | GREEN | 23 | No |
| CRVUSDT | 5 | GREEN | 18 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 5 | GREEN | 25 | No |
| CYBERUSDT | 5 | GREEN | 22 | No |
| CYSUSDT | 5 | RED | 31 | No |
| DASHUSDT | 5 | GREEN | 12 | No |
| DEXEUSDT | 5 | RED | 11 | No |
| DGAIUSDT | 5 | RED | 35 | No |
| DOGEUSDT | 5 | RED | 29 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 5 | RED | 17 | No |
| DOTUSDT | 5 | GREEN | 12 | No |
| EDGEUSDT | 5 | GREEN | 9 | No |
| EIGENUSDT | 5 | GREEN | 12 | No |
| ELICEUSDT | 5 | GREEN | 5 | No |
| ELSAUSDT | 5 | GREEN | 30 | No |
| ENAUSDT | 5 | RED | 30 | No |
| ENSOUSDT | 5 | RED | 28 | No |
| ENSUSDT | 5 | GREEN | 16 | No |
| ERAUSDT | 5 | RED | 14 | No |
| ETCUSDT | 5 | RED | 22 | No |
| ETHFIUSDT | 5 | GREEN | 21 | No |
| ETHUSDT | 5 | RED | 33 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 5 | RED | 32 | No |
| FARTCOINUSDT | 5 | RED | 29 | No |
| FCXUSDT | 5 | GREEN | 3 | No |
| FETUSDT | 5 | GREEN | 20 | No |
| FILUSDT | 5 | RED | 30 | No |
| FLOCKUSDT | 5 | RED | 19 | No |
| FLOKIUSDT | 5 | RED | 11 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 5 | RED | 11 | No |
| GPSUSDT | 5 | GREEN | 6 | No |
| GRAMUSDT | 5 | GREEN | 27 | No |
| GRASSUSDT | 5 | GREEN | 20 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 5 | RED | 24 | No |
| GWEIUSDT | 5 | RED | 8 | No |
| HBARUSDT | 5 | RED | 24 | No |
| HUMAUSDT | 5 | GREEN | 13 | No |
| HUSDT | 5 | GREEN | 21 | No |
| HYPEUSDT | 5 | GREEN | 33 | No |
| ICNTUSDT | 5 | GREEN | 25 | No |
| ICPUSDT | 5 | RED | 24 | No |
| IDOLUSDT | 5 | RED | 29 | No |
| INITUSDT | 5 | GREEN | 31 | No |
| INJUSDT | 5 | RED | 32 | No |
| INXUSDT | 5 | GREEN | 33 | No |
| IOSTUSDT | 5 | GREEN | 10 | No |
| IRYSUSDT | 5 | RED | 21 | No |
| JCTUSDT | 5 | RED | 22 | No |
| JTOUSDT | 5 | RED | 13 | No |
| JUPUSDT | 5 | RED | 26 | No |
| KAITOUSDT | 5 | RED | 15 | No |
| KASUSDT | 5 | RED | 15 | No |
| KAVAUSDT | 5 | RED | 15 | No |
| KERNELUSDT | 5 | RED | 22 | No |
| KGENUSDT | 5 | RED | 22 | No |
| KITEUSDT | 5 | GREEN | 11 | No |
| KUAISHOUUSDT | 5 | RED | 5 | No |
| LABUSDT | 5 | RED | 17 | No |
| LAUSDT | 5 | RED | 15 | No |
| LDOUSDT | 5 | RED | 14 | No |
| LINKUSDT | 5 | GREEN | 30 | No |
| LISTAUSDT | 5 | GREEN | 24 | No |
| LITUSDT | 5 | RED | 28 | No |
| LSKUSDT | 5 | GREEN | 23 | No |
| LTCUSDT | 5 | RED | 30 | No |
| LUNCUSDT | 5 | GREEN | 16 | No |
| MAGICUSDT | 5 | GREEN | 13 | No |
| MAGMAUSDT | 5 | GREEN | 22 | No |
| MARSCOINUSDT | 5 | GREEN | 14 | No |
| MEGAUSDT | 5 | RED | 17 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 5 | GREEN | 13 | No |
| MEUSDT | 1 | GREEN | 11 | No |
| MMTUSDT | 5 | GREEN | 30 | No |
| MONUSDT | 5 | RED | 17 | No |
| MORPHOUSDT | 5 | GREEN | 15 | No |
| MSUSDT | 5 | RED | 10 | No |
| MUBARAKUSDT | 5 | RED | 28 | No |
| MYXUSDT | 5 | GREEN | 11 | No |
| NAORISUSDT | 5 | RED | 21 | No |
| NEARUSDT | 5 | RED | 31 | No |
| NEMUSDT | 5 | GREEN | 5 | No |
| NIGHTUSDT | 5 | RED | 21 | No |
| NILUSDT | 5 | GREEN | 9 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 5 | RED | 27 | No |
| ONEUSDT | 5 | GREEN | 26 | No |
| ONGUSDT | 5 | GREEN | 30 | No |
| OPGUSDT | 5 | RED | 6 | No |
| OPUSDT | 5 | RED | 12 | No |
| ORCAUSDT | 5 | GREEN | 10 | No |
| ORDIUSDT | 5 | RED | 18 | No |
| PBRUSDT | 5 | GREEN | 3 | No |
| PENDLEUSDT | 5 | RED | 19 | No |
| PENGUUSDT | 5 | GREEN | 24 | No |
| PEOPLEUSDT | 5 | RED | 14 | No |
| PEPEUSDT | 5 | RED | 30 | No |
| PHAUSDT | 5 | GREEN | 17 | No |
| PIEVERSEUSDT | 5 | GREEN | 30 | No |
| PIPPINUSDT | 5 | RED | 21 | No |
| PIUSDT | 5 | GREEN | 24 | No |
| PLUMEUSDT | 5 | RED | 11 | No |
| POLUSDT | 5 | RED | 18 | No |
| PONSUSDT | 5 | RED | 30 | No |
| POWERUSDT | 5 | GREEN | 18 | No |
| PROMUSDT | 5 | GREEN | 35 | No |
| PUMPUSDT | 5 | RED | 31 | No |
| PYTHUSDT | 5 | GREEN | 22 | No |
| QNTUSDT | 5 | RED | 32 | No |
| QUSDT | 5 | RED | 20 | No |
| RAREUSDT | 5 | GREEN | 18 | No |
| RAVEUSDT | 5 | RED | 14 | No |
| RAYUSDT | 5 | GREEN | 16 | No |
| RENDERUSDT | 5 | GREEN | 27 | No |
| REUSDT | 5 | RED | 15 | No |
| RIVERUSDT | 5 | GREEN | 15 | No |
| RPLUSDT | 5 | GREEN | 29 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 5 | GREEN | 29 | No |
| SANDUSDT | 5 | GREEN | 28 | No |
| SAPIENUSDT | 5 | RED | 9 | No |
| SEIUSDT | 5 | RED | 27 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHIBUSDT | 5 | RED | 26 | No |
| SKYAIUSDT | 5 | GREEN | 19 | No |
| SKYUSDT | 5 | RED | 22 | No |
| SOLUSDT | 5 | RED | 33 | No |
| SOONUSDT | 5 | GREEN | 3 | No |
| SPKUSDT | 5 | GREEN | 8 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 5 | GREEN | 24 | No |
| STRKUSDT | 5 | GREEN | 29 | No |
| STXUSDT | 5 | RED | 15 | No |
| SUIUSDT | 5 | RED | 29 | No |
| TAOUSDT | 5 | GREEN | 30 | No |
| TIAUSDT | 5 | RED | 30 | No |
| TRUMPUSDT | 5 | RED | 29 | No |
| TRXUSDT | 5 | GREEN | 18 | No |
| TUTUSDT | 5 | GREEN | 5 | No |
| UAIUSDT | 5 | GREEN | 21 | No |
| UBUSDT | 4 | RED | 8 | No |
| UNITASUSDT | 5 | GREEN | 17 | No |
| UNIUSDT | 5 | RED | 31 | No |
| USDBRLUSDT | 5 | GREEN | 17 | No |
| USDJPYUSDT | 5 | GREEN | 4 | No |
| USELESSUSDT | 5 | RED | 25 | No |
| USUALUSDT | 5 | RED | 11 | No |
| VELVETUSDT | 5 | RED | 22 | No |
| VIRTUALUSDT | 5 | GREEN | 23 | No |
| VVVUSDT | 5 | RED | 30 | No |
| WIFUSDT | 5 | RED | 17 | No |
| WLDUSDT | 5 | RED | 26 | No |
| WLFIUSDT | 5 | RED | 15 | No |
| XLMUSDT | 5 | GREEN | 29 | No |
| XMRUSDT | 5 | GREEN | 31 | No |
| XPLUSDT | 5 | RED | 25 | No |
| XRPUSDT | 5 | RED | 31 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZECUSDT | 5 | RED | 31 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZROUSDT | 5 | RED | 27 | No |
| 牛来USDT | 5 | GREEN | 9 | No |
| 龙虾USDT | 5 | GREEN | 14 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 3 | 45 |
| $1m–$10m 24h futures turnover | 3 | 45 |
| $10m–$100m 24h futures turnover | 3 | 45 |
| $100m+ 24h futures turnover | 2 | 30 |

## Profit-versus-loss summary (hypothetical book-walk outcomes)

- Positive outcomes: 1182; negative outcomes: 2796; flat: 0
- Win rate among scored outcomes: 29.7%
- Gross positive outcomes: 5355.368205 USDT
- Gross negative outcomes: 20579.991267 USDT
- Total estimated net after trading fees: -15224.623062 USDT
- Profit factor (gross gains / gross losses): 0.260
- Average winning outcome: 4.530768 USDT
- Average losing outcome: -7.360512 USDT
- Mean estimated net result: -70.18 bps

These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.

- Ticker-only reference outcomes (separate, not executable): 0

## Strategy breakdown

| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |
|---|---:|---:|---:|---:|
| breakdown | 714 | 237 | 477 | -77.79 |
| breakout | 339 | 28 | 311 | -58.44 |
| ema_volume | 2925 | 917 | 2008 | -69.68 |

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
