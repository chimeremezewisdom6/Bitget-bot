# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-23T11:29:36.710531+00:00
- Session ended UTC: not recorded
- Collector cycles: 20
- Distinct symbols observed: 223
- Current Bitget turnover-watchlist contracts: 11
- Market observation rows: 4000
- Candidate signals eligible for entry evaluation: 731
- Watch-only RSI conditions (no entry): 1218
- Two-snapshot order-book shadow outcomes: 6300
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 1087
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 222
- Breakout-based trend starts found: 3465 (LONG: 1564; SHORT: 1901)
- Average direction-matching candle share in first hour: 30.7%
- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 221
- Complete trend events with early-window measurements: 3389

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 3389 | 43.8% | 1714/3389 (50.6%) | 0.0424% |
| 10 | 3389 | 36.5% | 1728/3389 (51.0%) | 0.0718% |
| 15 | 3389 | 34.1% | 1734/3389 (51.2%) | 0.0795% |
| 20 | 3389 | 33.2% | 1704/3389 (50.3%) | 0.0579% |
| 30 | 3389 | 32.1% | 1687/3389 (49.8%) | 0.0508% |
| 60 | 3389 | 31.1% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 210
- LONG/SHORT ignition candidates (score at least 4/7): 14
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| MMTUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 1.1593% | 1.5955% | 2.0952% | 2.88x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| QUSDT | LONG | 6 / 7 | IGNITION_CANDIDATE | 1.1494% | 0.6469% | 0.6793% | 46.114x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| LISTAUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -1.8663% | -3.198% | -7.1821% | 0.495x | 0/5 | NO_CLEAR_OI_CONFIRMATION |
| IOSTUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.6615% | -0.8419% | 0.5838% | 10.77x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| PBRUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.2668% | -0.6456% | 19.5438% | 0.043x | 0/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CYSUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.7862% | 2.1244% | 3.7558% | 2.413x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| INXUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.306% | 0.8462% | 3.774% | 0.099x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| KASUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1907% | -0.1907% | -0.4135% | 3.488x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| LITUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | 0.1699% | -0.2537% | -0.1891% | 2.267x | 1/3 | NO_CLEAR_OI_CONFIRMATION |
| MAGMAUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2849% | -0.5949% | -0.9351% | 2.926x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| ARXUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.742% | 0.9349% | -0.2474% | 1.415x | 4/0 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| SPKUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1691% | -0.3376% | -0.2532% | 2.025x | 0/1 | NO_CLEAR_OI_CONFIRMATION |
| ATUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | 0.6791% | 0.0% | 2.4798% | 2.068x | 2/2 | NO_CLEAR_OI_CONFIRMATION |
| EGLDUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2737% | -0.7266% | -0.3965% | 2.845x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| HYPEUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.5336% | -0.2726% | -0.2246% | 1.729x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| PEPEUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1729% | -0.2678% | -0.3718% | 1.338x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| XLMUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.0871% | -0.7633% | -0.7857% | 2.49x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| XMRUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.0101% | -0.0221% | -0.4328% | 0.161x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| VVVUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.3437% | 0.3437% | 0.5349% | 0.054x | 3/1 | NEW_POSITION_BUILDING_AGGREGATE |
| RENDERUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.0078% | -0.8126% | -1.5273% | 0.19x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| MUBARAKUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5843% | -1.3256% | -1.2489% | 1.27x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| DOTUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1499% | -0.597% | -0.6351% | 1.573x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| DGAIUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.207% | 0.614% | 0.3513% | 8.414x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| USELESSUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.1215% | -0.5629% | -1.2754% | 10.261x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| CLSUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2479% | 0.0% | 8.0433% | 529.436x | 1/1 | NO_CLEAR_OI_CONFIRMATION |
| SAPIENUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.4087% | 0.3318% | 0.8568% | 0.032x | 1/0 | NEW_POSITION_BUILDING_AGGREGATE |
| CHIPUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1822% | -0.7968% | -0.7955% | 0.05x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| BEATUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.5124% | -2.2427% | 1.5232% | 2.4x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PLUMEUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.3749% | -0.932% | -0.8691% | 2.115x | 0/1 | NO_CLEAR_OI_CONFIRMATION |
| USUALUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2669% | -0.3556% | -0.2693% | 18.201x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| UAIUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1681% | -0.835% | -1.315% | 0.566x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| AEONUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.4509% | -1.3896% | -0.8089% | 8.311x | 1/1 | NO_CLEAR_OI_CONFIRMATION |
| BTCUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.0072% | -0.2891% | 0.0504% | 1.692x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| NEARUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.0723% | -0.7358% | -0.8268% | 3.425x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| EVAAUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.7511% | -8.6944% | -9.6057% | 7.081x | 3/2 | NO_CLEAR_OI_CONFIRMATION |
| PIEVERSEUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | 0.494% | 0.8833% | 1.0349% | 0.975x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| ELSAUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -1.3882% | -0.2122% | -0.4019% | 1.212x | 2/2 | NO_CLEAR_OI_CONFIRMATION |
| ARBUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | 0.1326% | -0.1499% | -0.1677% | 1.585x | 2/2 | NO_CLEAR_OI_CONFIRMATION |
| ACEUSDT | SHORT | 2 / 7 | NO_STRONG_IGNITION | -0.1385% | -1.0974% | -0.7785% | 1.732x | 2/2 | NO_CLEAR_OI_CONFIRMATION |
| INJUSDT | LONG | 2 / 7 | NO_STRONG_IGNITION | 0.0996% | -0.4785% | -0.878% | 1.513x | 3/2 | NO_CLEAR_OI_CONFIRMATION |

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
| 0GUSDT | 5 | RED | 17 | No |
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
| EGLDUSDT | 2 | RED | 12 | No |
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
| FFUSDT | 1 | RED | 17 | No |
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
| JNJUSDT | 2 | GREEN | 7 | No |
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
| MEUSDT | 3 | RED | 12 | No |
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
| PROSUSDT | 1 | GREEN | 34 | No |
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
| SPACEUSDT | 2 | GREEN | 12 | No |
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
| UBUSDT | 5 | RED | 13 | No |
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
| ZENUSDT | 2 | RED | 17 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZROUSDT | 5 | RED | 27 | No |
| 牛来USDT | 5 | GREEN | 9 | No |
| 龙虾USDT | 5 | GREEN | 14 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 3 | 60 |
| $1m–$10m 24h futures turnover | 3 | 60 |
| $10m–$100m 24h futures turnover | 3 | 60 |
| $100m+ 24h futures turnover | 2 | 40 |

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
