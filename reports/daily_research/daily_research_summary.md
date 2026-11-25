# 24-Hour Bitget USDT Perpetual Research Report

- Session started UTC: 2026-11-24T12:53:32.795728+00:00
- Session ended UTC: not recorded
- Collector cycles: 4
- Distinct symbols observed: 240
- Current Bitget turnover-watchlist contracts: 128
- Market observation rows: 4800
- Candidate signals eligible for entry evaluation: 813
- Watch-only RSI conditions (no entry): 1377
- Two-snapshot order-book shadow outcomes: 6741
- Legacy ticker-reference outcomes: 0
- Outcomes unavailable: 0
- Collection error records: 0
- 60-minute same-colour candle checks: 1887
- Checks meeting 40+ same-colour candles: 0

## Previous 24-hour trend-start candle-colour backtest

- Symbols with completed historical backtests: 441
- Breakout-based trend starts found: 7024 (LONG: 3054; SHORT: 3970)
- Average direction-matching candle share in first hour: 31.7%
- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.

A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.

## Early-trend candle windows (separate experiment)

- Symbols with early-window backtests: 440
- Complete trend events with early-window measurements: 6948

For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.

| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |
|---:|---:|---:|---:|---:|
| 5 | 6948 | 45.5% | 3808/6948 (54.8%) | 0.1240% |
| 10 | 6948 | 38.0% | 3806/6948 (54.8%) | 0.1387% |
| 15 | 6948 | 35.4% | 3789/6948 (54.5%) | 0.1400% |
| 20 | 6948 | 34.4% | 3655/6948 (52.6%) | 0.0882% |
| 30 | 6948 | 33.4% | 3526/6948 (50.7%) | 0.0356% |
| 60 | 6948 | 31.9% | — | — |

## Current trend-ignition radar (latest Bitget scan per coin)

- Coins with usable candle/OI analysis: 229
- LONG/SHORT ignition candidates (score at least 4/7): 14
- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.

| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| ZROUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.6624% | -0.5% | -0.0405% | 3.882x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| MARSCOINUSDT | SHORT | 5 / 7 | IGNITION_CANDIDATE | -0.698% | -0.4786% | -1.4397% | 66.214x | 0/1 | NO_CLEAR_OI_CONFIRMATION |
| PEPEUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.3315% | 0.539% | 0.2166% | 0.801x | 4/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CYSUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.9941% | -2.0096% | -3.1976% | 0.937x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| TAOUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.0556% | -0.0056% | 0.2634% | 5.344x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| DOSUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -1.6818% | -0.4032% | -0.6445% | 0.282x | 0/5 | NO_CLEAR_OI_CONFIRMATION |
| GRAMUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.2811% | 0.2594% | 0.6177% | 1.732x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| IDOLUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.4015% | -0.5808% | 0.0533% | 0.489x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| LITUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.6316% | -0.3799% | 0.1366% | 0.434x | 0/2 | NEW_POSITION_BUILDING_AGGREGATE |
| CROSSUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.1687% | -0.6158% | -0.5667% | 14.099x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| HUMAUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 0.1245% | 0.7519% | 2.1006% | 12.478x | 2/1 | NEW_POSITION_BUILDING_AGGREGATE |
| CPUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.4211% | -0.4909% | 0.2705% | 1.368x | 0/4 | NEW_POSITION_BUILDING_AGGREGATE |
| ONGUSDT | SHORT | 4 / 7 | IGNITION_CANDIDATE | -0.2333% | -1.1558% | -2.2645% | 0.103x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| HPQUSDT | LONG | 4 / 7 | IGNITION_CANDIDATE | 1.3488% | 2.8959% | -12.5872% | 0.179x | 2/0 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| ZECUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1104% | -0.466% | -0.1126% | 1.086x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| MMTUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1369% | -0.8605% | 0.3355% | 0.669x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| ARIAUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.6354% | -0.2105% | -0.0836% | 0.913x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| ARBUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.154% | -0.2082% | 0.1034% | 1.573x | 0/4 | NEW_POSITION_BUILDING_AGGREGATE |
| LINKUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.0341% | -0.1361% | 0.3941% | 12.385x | 2/3 | NEW_POSITION_BUILDING_AGGREGATE |
| SKYUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.4058% | -0.7139% | -0.8541% | 0.114x | 1/2 | NO_CLEAR_OI_CONFIRMATION |
| XLMUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2105% | -0.2347% | 0.0278% | 2.286x | 1/3 | NEW_POSITION_BUILDING_AGGREGATE |
| JUPUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1357% | -0.1809% | -0.1374% | 0.352x | 0/1 | NO_CLEAR_OI_CONFIRMATION |
| XMRUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | 0.0139% | -0.1916% | 0.0629% | 0.695x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| MUBARAKUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5348% | -0.2235% | 0.2406% | 2.814x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| LSKUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5972% | -0.729% | -1.562% | 1.48x | 1/4 | NO_CLEAR_OI_CONFIRMATION |
| HUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.4959% | -0.3311% | 0.2254% | 30.647x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| SAHARAUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1718% | 0.7487% | 2.2155% | 0.381x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| IRYSUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.0593% | 2.6764% | 2.9053% | 1.671x | 3/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PONSUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5289% | -0.5172% | -0.2695% | 0.538x | 2/3 | NO_CLEAR_OI_CONFIRMATION |
| CTUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.5116% | -0.339% | 0.5292% | 0.587x | 1/4 | NEW_POSITION_BUILDING_AGGREGATE |
| ONEUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.0321% | 1.0169% | 0.5755% | 0.859x | 2/2 | NEW_POSITION_BUILDING_AGGREGATE |
| PIPPINUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.5365% | 0.4826% | -0.1618% | 0.039x | 3/1 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| MYXUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.3589% | -0.1797% | 0.1316% | 4.435x | 0/1 | NEW_POSITION_BUILDING_AGGREGATE |
| KUAISHOUUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1196% | 0.0399% | 1.7929% | 2.649x | 1/2 | NEW_POSITION_BUILDING_AGGREGATE |
| SPKUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2629% | -0.2629% | 0.0894% | 7.806x | 0/2 | NEW_POSITION_BUILDING_AGGREGATE |
| KITEUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.4981% | -0.6811% | -0.1977% | 1.72x | 0/2 | NO_CLEAR_OI_CONFIRMATION |
| MAGICUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.1521% | 0.3046% | 0.9179% | 0.084x | 1/1 | NEW_POSITION_BUILDING_AGGREGATE |
| EGLDUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.1863% | -0.3719% | -0.2659% | 2.37x | 0/1 | NO_CLEAR_OI_CONFIRMATION |
| PROSUSDT | LONG | 3 / 7 | EARLY_PRESSURE | 0.3333% | 0.6543% | -1.3239% | 2.3x | 3/2 | POSSIBLE_POSITION_CLOSING_OR_SHORT_COVERING |
| ALTUSDT | SHORT | 3 / 7 | EARLY_PRESSURE | -0.2127% | -0.1655% | -0.0448% | 2.656x | 0/1 | NO_CLEAR_OI_CONFIRMATION |

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
| 0GUSDT | 9 | RED | 12 | No |
| 1000BONKUSDT | 9 | RED | 11 | No |
| 2ZUSDT | 2 | RED | 19 | No |
| AAVEUSDT | 9 | GREEN | 30 | No |
| ACEUSDT | 9 | RED | 23 | No |
| ACUUSDT | 9 | RED | 4 | No |
| ADAUSDT | 9 | RED | 19 | No |
| AEONUSDT | 9 | RED | 15 | No |
| AEROUSDT | 9 | RED | 14 | No |
| AIOUSDT | 5 | GREEN | 9 | No |
| AKEUSDT | 9 | RED | 30 | No |
| ALGOUSDT | 9 | RED | 24 | No |
| ALLOUSDT | 9 | RED | 21 | No |
| ALTUSDT | 2 | RED | 8 | No |
| AMDLUSDT | 9 | RED | 28 | No |
| APRUSDT | 9 | RED | 10 | No |
| APTUSDT | 9 | RED | 24 | No |
| ARBUSDT | 9 | RED | 27 | No |
| ARIAUSDT | 9 | RED | 30 | No |
| ARKMUSDT | 5 | RED | 4 | No |
| ARUSDT | 9 | GREEN | 11 | No |
| ARXUSDT | 9 | RED | 17 | No |
| ASTERUSDT | 9 | RED | 16 | No |
| ATOMUSDT | 9 | RED | 18 | No |
| ATUSDT | 9 | RED | 12 | No |
| AVAXUSDT | 9 | RED | 32 | No |
| AXISUSDT | 9 | RED | 21 | No |
| BABYUSDT | 9 | RED | 11 | No |
| BANKUSDT | 9 | RED | 10 | No |
| BARDUSDT | 9 | RED | 23 | No |
| BATUSDT | 5 | RED | 13 | No |
| BCHUSDT | 9 | RED | 30 | No |
| BEAMUSDT | 9 | RED | 16 | No |
| BEATUSDT | 9 | GREEN | 21 | No |
| BERAUSDT | 5 | GREEN | 9 | No |
| BGBUSDT | 9 | RED | 14 | No |
| BIGTIMEUSDT | 1 | GREEN | 29 | No |
| BLESSUSDT | 9 | GREEN | 30 | No |
| BLURUSDT | 8 | RED | 14 | No |
| BNBUSDT | 9 | RED | 29 | No |
| BOMEUSDT | 9 | RED | 10 | No |
| BREVUSDT | 9 | RED | 28 | No |
| BRUSDT | 5 | GREEN | 11 | No |
| BTCUSDT | 9 | RED | 36 | No |
| BTWUSDT | 9 | GREEN | 33 | No |
| BUSDT | 2 | RED | 5 | No |
| CAKEUSDT | 2 | GREEN | 12 | No |
| CAPUSDT | 9 | GREEN | 10 | No |
| CFGUSDT | 9 | RED | 24 | No |
| CHIPUSDT | 9 | RED | 12 | No |
| CLSUSDT | 9 | RED | 9 | No |
| COOKIEUSDT | 7 | RED | 4 | No |
| CPUSDT | 9 | RED | 23 | No |
| CROSSUSDT | 9 | GREEN | 16 | No |
| CRVUSDT | 9 | RED | 18 | No |
| CSTOCKUSDT | 5 | GREEN | 10 | No |
| CTUSDT | 9 | GREEN | 29 | No |
| CYBERUSDT | 9 | GREEN | 30 | No |
| CYSUSDT | 9 | RED | 35 | No |
| DASHUSDT | 7 | RED | 10 | No |
| DEXEUSDT | 9 | RED | 15 | No |
| DGAIUSDT | 9 | GREEN | 25 | No |
| DOGEUSDT | 9 | RED | 32 | No |
| DOODUSDT | 5 | RED | 8 | No |
| DOSUSDT | 9 | RED | 34 | No |
| DOTUSDT | 9 | RED | 12 | No |
| EDGEUSDT | 5 | GREEN | 9 | No |
| EGLDUSDT | 6 | RED | 9 | No |
| EIGENUSDT | 9 | RED | 12 | No |
| ELICEUSDT | 8 | GREEN | 5 | No |
| ELSAUSDT | 9 | GREEN | 30 | No |
| ENAUSDT | 9 | RED | 32 | No |
| ENSOUSDT | 9 | RED | 26 | No |
| ENSUSDT | 9 | RED | 11 | No |
| ERAUSDT | 9 | GREEN | 21 | No |
| ETCUSDT | 9 | RED | 29 | No |
| ETHFIUSDT | 9 | RED | 19 | No |
| ETHUSDT | 9 | RED | 32 | No |
| EURUSDUSDT | 1 | GREEN | 4 | No |
| EVAAUSDT | 9 | GREEN | 33 | No |
| FARTCOINUSDT | 9 | GREEN | 24 | No |
| FCXUSDT | 9 | RED | 10 | No |
| FETUSDT | 9 | RED | 20 | No |
| FFUSDT | 5 | RED | 3 | No |
| FILUSDT | 9 | RED | 28 | No |
| FLOCKUSDT | 8 | GREEN | 9 | No |
| FLOKIUSDT | 9 | RED | 13 | No |
| FLUIDUSDT | 3 | RED | 12 | No |
| FOLKSUSDT | 5 | GREEN | 6 | No |
| GALAUSDT | 9 | GREEN | 11 | No |
| GPSUSDT | 8 | GREEN | 6 | No |
| GRAMUSDT | 9 | RED | 28 | No |
| GRASSUSDT | 9 | GREEN | 18 | No |
| GRTUSDT | 5 | RED | 7 | No |
| GRVTUSDT | 9 | GREEN | 17 | No |
| GWEIUSDT | 9 | GREEN | 16 | No |
| HBARUSDT | 9 | RED | 24 | No |
| HPQUSDT | 1 | GREEN | 12 | No |
| HUMAUSDT | 9 | GREEN | 13 | No |
| HUSDT | 9 | GREEN | 12 | No |
| HYPEUSDT | 9 | RED | 37 | No |
| ICNTUSDT | 9 | RED | 30 | No |
| ICPUSDT | 9 | RED | 19 | No |
| IDOLUSDT | 9 | RED | 31 | No |
| INITUSDT | 9 | GREEN | 31 | No |
| INJUSDT | 9 | GREEN | 28 | No |
| INXUSDT | 9 | RED | 11 | No |
| IOSTUSDT | 9 | GREEN | 11 | No |
| IRYSUSDT | 9 | GREEN | 31 | No |
| JCTUSDT | 9 | RED | 18 | No |
| JNJUSDT | 6 | RED | 5 | No |
| JTOUSDT | 9 | RED | 17 | No |
| JUPUSDT | 9 | RED | 18 | No |
| KAITOUSDT | 9 | GREEN | 11 | No |
| KASUSDT | 9 | RED | 16 | No |
| KAVAUSDT | 6 | GREEN | 21 | No |
| KERNELUSDT | 9 | RED | 22 | No |
| KGENUSDT | 9 | GREEN | 18 | No |
| KITEUSDT | 9 | RED | 20 | No |
| KUAISHOUUSDT | 9 | RED | 9 | No |
| LABUSDT | 9 | RED | 17 | No |
| LAUSDT | 5 | RED | 15 | No |
| LDOUSDT | 9 | RED | 15 | No |
| LINKUSDT | 9 | RED | 30 | No |
| LISTAUSDT | 9 | RED | 33 | No |
| LITUSDT | 9 | RED | 16 | No |
| LSKUSDT | 9 | RED | 17 | No |
| LTCUSDT | 9 | RED | 27 | No |
| LUNCUSDT | 9 | RED | 25 | No |
| MAGICUSDT | 7 | RED | 13 | No |
| MAGMAUSDT | 9 | RED | 16 | No |
| MANTRAUSDT | 2 | RED | 13 | No |
| MARSCOINUSDT | 9 | GREEN | 5 | No |
| MDTUSDT | 2 | GREEN | 3 | No |
| MEGAUSDT | 9 | RED | 19 | No |
| MELANIAUSDT | 5 | GREEN | 3 | No |
| METUSDT | 7 | RED | 4 | No |
| MEUSDT | 6 | GREEN | 23 | No |
| MMTUSDT | 9 | GREEN | 29 | No |
| MONUSDT | 9 | RED | 21 | No |
| MORPHOUSDT | 8 | GREEN | 19 | No |
| MSUSDT | 7 | RED | 6 | No |
| MUBARAKUSDT | 9 | GREEN | 19 | No |
| MYXUSDT | 9 | GREEN | 8 | No |
| NAORISUSDT | 9 | GREEN | 21 | No |
| NEARUSDT | 9 | RED | 32 | No |
| NEMUSDT | 7 | RED | 8 | No |
| NIGHTUSDT | 9 | GREEN | 14 | No |
| NILUSDT | 9 | RED | 23 | No |
| NUUSDT | 5 | GREEN | 7 | No |
| ONDOUSDT | 9 | RED | 25 | No |
| ONEUSDT | 8 | GREEN | 20 | No |
| ONGUSDT | 9 | RED | 29 | No |
| OPGUSDT | 6 | GREEN | 28 | No |
| OPUSDT | 9 | RED | 12 | No |
| ORCAUSDT | 9 | RED | 13 | No |
| ORDERUSDT | 4 | RED | 12 | No |
| ORDIUSDT | 9 | GREEN | 16 | No |
| PBRUSDT | 8 | RED | 5 | No |
| PENDLEUSDT | 9 | RED | 20 | No |
| PENGUUSDT | 9 | RED | 17 | No |
| PEOPLEUSDT | 7 | RED | 15 | No |
| PEPEUSDT | 9 | GREEN | 31 | No |
| PHAUSDT | 8 | GREEN | 21 | No |
| PIEVERSEUSDT | 9 | RED | 39 | No |
| PIPPINUSDT | 9 | GREEN | 25 | No |
| PIUSDT | 9 | RED | 22 | No |
| PLUMEUSDT | 9 | RED | 15 | No |
| POLUSDT | 9 | RED | 15 | No |
| PONSUSDT | 9 | GREEN | 26 | No |
| POWERUSDT | 8 | GREEN | 26 | No |
| PROMUSDT | 9 | RED | 29 | No |
| PROSUSDT | 5 | GREEN | 35 | No |
| PUMPUSDT | 9 | RED | 27 | No |
| PYTHUSDT | 9 | RED | 19 | No |
| QNTUSDT | 9 | RED | 26 | No |
| QUSDT | 9 | RED | 19 | No |
| RAREUSDT | 8 | RED | 17 | No |
| RAVEUSDT | 9 | RED | 12 | No |
| RAYUSDT | 9 | GREEN | 12 | No |
| RENDERUSDT | 9 | RED | 27 | No |
| REUSDT | 9 | RED | 24 | No |
| RIVERUSDT | 9 | RED | 11 | No |
| RPLUSDT | 9 | GREEN | 7 | No |
| RUNEUSDT | 5 | RED | 18 | No |
| SAHARAUSDT | 9 | RED | 34 | No |
| SANDUSDT | 9 | RED | 26 | No |
| SAPIENUSDT | 9 | RED | 12 | No |
| SEIUSDT | 9 | RED | 23 | No |
| SENTUSDT | 5 | GREEN | 13 | No |
| SHELLUSDT | 1 | GREEN | 16 | No |
| SHIBUSDT | 9 | RED | 26 | No |
| SIRENUSDT | 1 | GREEN | 22 | No |
| SKYAIUSDT | 9 | GREEN | 24 | No |
| SKYUSDT | 9 | GREEN | 31 | No |
| SLXUSDT | 1 | RED | 18 | No |
| SOLUSDT | 9 | GREEN | 30 | No |
| SOONUSDT | 9 | RED | 15 | No |
| SOPHUSDT | 1 | RED | 16 | No |
| SPACEUSDT | 6 | GREEN | 11 | No |
| SPKUSDT | 9 | GREEN | 8 | No |
| SPXUSDT | 5 | GREEN | 7 | No |
| SQDUSDT | 9 | RED | 14 | No |
| STRKUSDT | 9 | RED | 21 | No |
| STXUSDT | 9 | GREEN | 16 | No |
| SUIUSDT | 9 | RED | 31 | No |
| SYNUSDT | 1 | RED | 15 | No |
| TAOUSDT | 9 | RED | 31 | No |
| TIAUSDT | 9 | RED | 22 | No |
| TRBUSDT | 2 | GREEN | 11 | No |
| TRUMPUSDT | 9 | RED | 26 | No |
| TRXUSDT | 9 | GREEN | 10 | No |
| TUTUSDT | 7 | GREEN | 10 | No |
| UAIUSDT | 9 | RED | 20 | No |
| UBUSDT | 5 | RED | 13 | No |
| UNITASUSDT | 9 | RED | 12 | No |
| UNIUSDT | 9 | RED | 30 | No |
| USDBRLUSDT | 9 | GREEN | 6 | No |
| USDJPYUSDT | 7 | RED | 5 | No |
| USELESSUSDT | 9 | GREEN | 22 | No |
| USUALUSDT | 9 | RED | 18 | No |
| VELVETUSDT | 9 | RED | 13 | No |
| VIRTUALUSDT | 9 | RED | 22 | No |
| VVVUSDT | 9 | GREEN | 27 | No |
| WIFUSDT | 9 | RED | 20 | No |
| WLDUSDT | 9 | RED | 30 | No |
| WLFIUSDT | 9 | GREEN | 14 | No |
| XLMUSDT | 9 | RED | 28 | No |
| XMRUSDT | 9 | RED | 30 | No |
| XPLUSDT | 9 | GREEN | 31 | No |
| XRPUSDT | 9 | RED | 31 | No |
| XVGUSDT | 5 | GREEN | 14 | No |
| ZBTUSDT | 2 | RED | 17 | No |
| ZECUSDT | 9 | RED | 35 | No |
| ZENUSDT | 5 | RED | 10 | No |
| ZESTUSDT | 5 | RED | 9 | No |
| ZKUSDT | 1 | RED | 12 | No |
| ZROUSDT | 9 | RED | 23 | No |
| 牛来USDT | 9 | RED | 12 | No |
| 龙虾USDT | 9 | RED | 6 | No |

## Bitget futures-turnover activity-group coverage

| Group | Watchlist candidates | Observation rows |
|---|---:|---:|
| Under $1m 24h futures turnover | 50 | 256 |
| $1m–$10m 24h futures turnover | 50 | 259 |
| $10m–$100m 24h futures turnover | 23 | 152 |
| $100m+ 24h futures turnover | 5 | 60 |

## Profit-versus-loss summary (hypothetical book-walk outcomes)

- Positive outcomes: 2489; negative outcomes: 4252; flat: 0
- Win rate among scored outcomes: 36.9%
- Gross positive outcomes: 17301.089482 USDT
- Gross negative outcomes: 34544.260564 USDT
- Total estimated net after trading fees: -17243.171083 USDT
- Profit factor (gross gains / gross losses): 0.501
- Average winning outcome: 6.951020 USDT
- Average losing outcome: -8.124238 USDT
- Mean estimated net result: -46.31 bps

These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.

- Ticker-only reference outcomes (separate, not executable): 0

## Strategy breakdown

| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |
|---|---:|---:|---:|---:|
| breakdown | 1152 | 549 | 603 | -14.10 |
| breakout | 603 | 103 | 500 | -72.89 |
| ema_volume | 4986 | 1837 | 3149 | -50.54 |

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
