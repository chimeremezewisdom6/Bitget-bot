# Bitget authenticated 24-hour genuine-trend backtest

- Generated UTC: 2026-11-24T06:48:57.251221+00:00
- Window UTC: 2026-11-23T06:48:00+00:00 to 2026-11-24T06:48:00+00:00
- Bitget API key authentication: SUCCESS
- Key permission type: readonly
- Account fee schedule: AVAILABLE
- Access scope: Signed account-info and fee-rate reads only; no balances, positions, orders, or withdrawals.
- Universe: top 200 online crypto USDT perpetuals by 24h turnover.
- Coverage: 200/200 symbols; 288,000 closed 1m candles; 0 fetch errors.
- 2h breakout-and-hold candidates before the 4%/speed filters: 686
- Candidates reaching 4% over 2h: 86
- Rejected below 4%: 600
- Rejected by the 4x speed rule: 53
- Qualifying gradual trends: 33 (LONG 18, SHORT 15).

## Exact trend rules
1. A closed 1m candle closes above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT).
2. Every subsequent closed 1m candle remains outside that breakout level for 120 complete minutes.
3. Direction-adjusted net movement from breakout close to the 120th-minute close is at least 4%.
4. The 120m directional move is at least 4 times the absolute directional move in the FIRST 10 minutes. The largest rolling 10m move later in the trend is measured separately as a diagnostic, not used to reject the trend.
5. LONG and SHORT are evaluated separately; gaps and incomplete candles invalidate a sample.

## Aggregate findings
- Mean qualifying 2h directional return: 7.1335%
- Median qualifying 2h directional return: 5.7607%
- Mean 2h-to-first-10m ratio: 7.895x

## What the data says fuels the move

### Findings from the 33 qualifying events
- The sample contains 18 LONG and 15 SHORT trends.
- Mean two-hour directional return was 7.13%; median was 5.76%.
- The mean two-hour / first-10-minute movement ratio was 7.90x; median was 6.31x. The minimum qualifying ratio was 4.06x.
- The first 10-minute move averaged 1.10% (median 0.96%).
- First-10-minute quote turnover was available for 32 events: median 2.10x the 20-minute pre-breakout baseline. 18/32 were at least 1.5x and 17/32 were at least 2x. The mean was 5.77x, inflated by a few very large turnover bursts, so the median is more representative.
- Direction-matching candle share averaged 49.1% in the first 15 minutes and 47.7% across the full two hours. This supports measuring net progress and defended structure rather than requiring nearly every candle to be the same colour.
- Historical OI could be aligned to both event boundaries for only 1 of 33 events. ELSAUSDT LONG had +19.88% aggregate OI change over the event window. This is one observation and aggregate OI cannot identify whether longs or shorts opened.
- Funding snapshots were retrieved for qualifying symbols, but they are current readings, not the funding at the historical event time. The order-book endpoint did not yield usable bid/ask depth for this sample. No historical taker-buy/sell split was available.

### Interpretation
- The most repeatable evidence in this 24h sample is persistent price structure plus participation: a 120-minute hold, approximately half of the candles closing in the trend direction, and often higher quote turnover near the start.
- Turnover acceleration is a useful supporting feature, not a sufficient cause or standalone signal. Several qualifying trends had turnover below 1x, so a strict volume-surge requirement would miss some.
- The test can describe which market conditions accompanied the moves, but it cannot yet prove what caused them. A causal fuel study needs historical OI snapshots across the full 2h event, historical funding and order-book/trade-side data aligned to the same timestamps.

- Persistence: 120m breakout-level hold, direction-matching candle counts, and maximum adverse/favorable excursion.
- Participation: first-10m and first-30m quote-turnover acceleration versus the 20m before the breakout.
- Historical open interest: reported only when Bitget's returned 5m observations cover both event boundaries; otherwise left blank.
- Funding and order book: current snapshots for qualifying symbols only. They are not falsely described as historical causes.
- Aggressive buyer/seller dominance: not inferred from OHLCV candles; no unsupported taker-side conclusion.

## Qualifying events
| Symbol | Side | Start UTC | 2h move % | First 10m % | Fastest 10m % | Ratio | 15m aligned | 120m aligned | First 10m turnover x | Historical OI % |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| UNITASUSDT | SHORT | 2026-11-23T16:54:00+00:00 | 16.6988 | 2.7925 | 10.0824 | 5.98x | 9/15 | 54/120 | 2.3353 | None |
| ELSAUSDT | LONG | 2026-11-24T04:43:00+00:00 | 15.3395 | 2.3108 | 13.5045 | 6.64x | 10/15 | 64/120 | 1.6171 | 19.88434 |
| LISTAUSDT | LONG | 2026-11-23T14:02:00+00:00 | 14.9091 | 2.0121 | 4.8883 | 7.41x | 8/15 | 72/120 | 0.7689 | None |
| ACEUSDT | LONG | 2026-11-23T13:15:00+00:00 | 13.6778 | 2.3148 | 7.1130 | 5.91x | 9/15 | 64/120 | 0.9987 | None |
| EVAAUSDT | SHORT | 2026-11-24T02:37:00+00:00 | 10.9932 | 1.5724 | 7.7845 | 6.99x | 11/15 | 77/120 | 7.6897 | None |
| MMTUSDT | SHORT | 2026-11-23T11:13:00+00:00 | 9.5652 | 1.5371 | 3.4998 | 6.22x | 9/15 | 66/120 | 1.449 | None |
| UNITASUSDT | SHORT | 2026-11-23T14:03:00+00:00 | 8.7735 | 1.6681 | 4.5932 | 5.26x | 7/15 | 54/120 | 4.7995 | None |
| UNITASUSDT | LONG | 2026-11-24T03:14:00+00:00 | 8.4865 | 1.1983 | 3.9017 | 7.08x | 5/15 | 41/120 | 7.0943 | None |
| SAHARAUSDT | LONG | 2026-11-23T23:13:00+00:00 | 7.3802 | 1.5873 | 3.0878 | 4.65x | 6/15 | 33/120 | None | None |
| VELVETUSDT | LONG | 2026-11-23T10:25:00+00:00 | 6.9121 | 1.6232 | 2.5914 | 4.26x | 8/15 | 65/120 | 1.2919 | None |
| ZESTUSDT | SHORT | 2026-11-23T11:30:00+00:00 | 6.8736 | 1.2409 | 2.5125 | 5.54x | 7/15 | 45/120 | 8.7535 | None |
| ATOMUSDT | LONG | 2026-11-23T13:26:00+00:00 | 6.7951 | 0.4112 | 4.0789 | 16.52x | 6/15 | 59/120 | 0.4165 | None |
| SKYUSDT | SHORT | 2026-11-23T07:49:00+00:00 | 6.6297 | 0.5058 | 2.7020 | 13.11x | 10/15 | 66/120 | 7.3129 | None |
| ALLOUSDT | LONG | 2026-11-23T13:14:00+00:00 | 6.5071 | 0.5322 | 3.9357 | 12.23x | 6/15 | 61/120 | 0.8167 | None |
| BLESSUSDT | SHORT | 2026-11-23T19:05:00+00:00 | 6.2825 | 1.5467 | 2.9525 | 4.06x | 7/15 | 67/120 | 1.0061 | None |
| NAORISUSDT | SHORT | 2026-11-23T14:05:00+00:00 | 5.8398 | 0.4329 | 2.7490 | 13.49x | 7/15 | 58/120 | 0.635 | None |
| UAIUSDT | LONG | 2026-11-23T12:18:00+00:00 | 5.7607 | 0.9554 | 3.3947 | 6.03x | 8/15 | 57/120 | 0.956 | None |
| APRUSDT | LONG | 2026-11-23T13:33:00+00:00 | 5.6367 | 0.3765 | 5.1186 | 14.97x | 4/15 | 58/120 | 25.8722 | None |
| CYSUSDT | LONG | 2026-11-23T13:33:00+00:00 | 5.5769 | 1.3084 | 3.5877 | 4.26x | 10/15 | 65/120 | 1.0359 | None |
| LUNCUSDT | LONG | 2026-11-23T09:45:00+00:00 | 5.5128 | 0.4472 | 2.1081 | 12.33x | 3/15 | 54/120 | 31.6989 | None |
| ICNTUSDT | SHORT | 2026-11-23T11:38:00+00:00 | 5.4993 | 0.7219 | 2.9141 | 7.62x | 10/15 | 67/120 | 3.6033 | None |
| IOSTUSDT | LONG | 2026-11-23T12:10:00+00:00 | 5.2866 | 0.8109 | 4.5122 | 6.52x | 4/15 | 39/120 | 2.874 | None |
| CROSSUSDT | SHORT | 2026-11-23T14:55:00+00:00 | 5.1707 | 1.2684 | 2.2706 | 4.08x | 7/15 | 49/120 | 23.0999 | None |
| VELVETUSDT | LONG | 2026-11-23T08:04:00+00:00 | 5.1314 | 0.8235 | 2.0558 | 6.23x | 7/15 | 55/120 | 1.4213 | None |
| LITUSDT | SHORT | 2026-11-23T16:41:00+00:00 | 5.1158 | 0.4458 | 2.0221 | 11.48x | 8/15 | 65/120 | 1.104 | None |
| BTWUSDT | SHORT | 2026-11-23T08:53:00+00:00 | 4.9069 | 0.9512 | 2.0752 | 5.16x | 11/15 | 71/120 | 3.5167 | None |
| MONUSDT | SHORT | 2026-11-23T08:18:00+00:00 | 4.8321 | 0.9764 | 2.5381 | 4.95x | 4/15 | 48/120 | 1.2378 | None |
| REUSDT | LONG | 2026-11-24T04:09:00+00:00 | 4.6964 | 1.0710 | 1.6938 | 4.39x | 6/15 | 50/120 | 0.4638 | None |
| ONGUSDT | LONG | 2026-11-24T03:57:00+00:00 | 4.2511 | 0.1970 | 1.1783 | 21.57x | 8/15 | 65/120 | 2.3547 | None |
| ZROUSDT | SHORT | 2026-11-23T18:10:00+00:00 | 4.2212 | 0.6692 | 1.4729 | 6.31x | 7/15 | 63/120 | 16.8145 | None |
| NAORISUSDT | SHORT | 2026-11-23T20:23:00+00:00 | 4.1191 | 0.9154 | 1.9455 | 4.50x | 6/15 | 41/120 | 2.0643 | None |
| MMTUSDT | LONG | 2026-11-23T23:08:00+00:00 | 4.0252 | 0.5914 | 3.0201 | 6.81x | 9/15 | 65/120 | 17.3946 | None |
| SPKUSDT | LONG | 2026-11-24T04:01:00+00:00 | 4.0000 | 0.5004 | 1.9592 | 7.99x | 6/15 | 32/120 | 2.1029 | None |

## Per-coin coverage
| Symbol | Candles | Trends | LONG | SHORT | Status |
|---|---:|---:|---:|---:|---|
| UNITASUSDT | 1440 | 3 | 1 | 2 | OK |
| MMTUSDT | 1440 | 2 | 1 | 1 | OK |
| VELVETUSDT | 1440 | 2 | 2 | 0 | OK |
| NAORISUSDT | 1440 | 2 | 0 | 2 | OK |
| EVAAUSDT | 1440 | 1 | 0 | 1 | OK |
| ELSAUSDT | 1440 | 1 | 1 | 0 | OK |
| BLESSUSDT | 1440 | 1 | 0 | 1 | OK |
| CYSUSDT | 1440 | 1 | 1 | 0 | OK |
| ACEUSDT | 1440 | 1 | 1 | 0 | OK |
| LISTAUSDT | 1440 | 1 | 1 | 0 | OK |
| SKYUSDT | 1440 | 1 | 0 | 1 | OK |
| ZROUSDT | 1440 | 1 | 0 | 1 | OK |
| ATOMUSDT | 1440 | 1 | 1 | 0 | OK |
| ICNTUSDT | 1440 | 1 | 0 | 1 | OK |
| SAHARAUSDT | 1440 | 1 | 1 | 0 | OK |
| APRUSDT | 1440 | 1 | 1 | 0 | OK |
| BTWUSDT | 1440 | 1 | 0 | 1 | OK |
| MONUSDT | 1440 | 1 | 0 | 1 | OK |
| LUNCUSDT | 1440 | 1 | 1 | 0 | OK |
| LITUSDT | 1440 | 1 | 0 | 1 | OK |
| CROSSUSDT | 1440 | 1 | 0 | 1 | OK |
| REUSDT | 1440 | 1 | 1 | 0 | OK |
| IOSTUSDT | 1440 | 1 | 1 | 0 | OK |
| ALLOUSDT | 1440 | 1 | 1 | 0 | OK |
| UAIUSDT | 1440 | 1 | 1 | 0 | OK |
| ONGUSDT | 1440 | 1 | 1 | 0 | OK |
| SPKUSDT | 1440 | 1 | 1 | 0 | OK |
| ZESTUSDT | 1440 | 1 | 0 | 1 | OK |
| BTCUSDT | 1440 | 0 | 0 | 0 | OK |
| ETHUSDT | 1440 | 0 | 0 | 0 | OK |
| SOLUSDT | 1440 | 0 | 0 | 0 | OK |
| XRPUSDT | 1440 | 0 | 0 | 0 | OK |
| ZECUSDT | 1440 | 0 | 0 | 0 | OK |
| HYPEUSDT | 1440 | 0 | 0 | 0 | OK |
| NEARUSDT | 1440 | 0 | 0 | 0 | OK |
| ENAUSDT | 1440 | 0 | 0 | 0 | OK |
| PEPEUSDT | 1440 | 0 | 0 | 0 | OK |
| DOGEUSDT | 1440 | 0 | 0 | 0 | OK |
| SUIUSDT | 1440 | 0 | 0 | 0 | OK |
| PIEVERSEUSDT | 1440 | 0 | 0 | 0 | OK |
| PROMUSDT | 1440 | 0 | 0 | 0 | OK |
| ADAUSDT | 1440 | 0 | 0 | 0 | OK |
| ARIAUSDT | 1440 | 0 | 0 | 0 | OK |
| WLDUSDT | 1440 | 0 | 0 | 0 | OK |
| PUMPUSDT | 1440 | 0 | 0 | 0 | OK |
| UNIUSDT | 1440 | 0 | 0 | 0 | OK |
| BNBUSDT | 1440 | 0 | 0 | 0 | OK |
| AKEUSDT | 1440 | 0 | 0 | 0 | OK |
| ARBUSDT | 1440 | 0 | 0 | 0 | OK |
| LINKUSDT | 1440 | 0 | 0 | 0 | OK |
| INJUSDT | 1440 | 0 | 0 | 0 | OK |
| TAOUSDT | 1440 | 0 | 0 | 0 | OK |
| AVAXUSDT | 1440 | 0 | 0 | 0 | OK |
| APTUSDT | 1440 | 0 | 0 | 0 | OK |
| ONDOUSDT | 1440 | 0 | 0 | 0 | OK |
| TRUMPUSDT | 1440 | 0 | 0 | 0 | OK |
| AAVEUSDT | 1440 | 0 | 0 | 0 | OK |
| LTCUSDT | 1440 | 0 | 0 | 0 | OK |
| QNTUSDT | 1440 | 0 | 0 | 0 | OK |
| BCHUSDT | 1440 | 0 | 0 | 0 | OK |
| XLMUSDT | 1440 | 0 | 0 | 0 | OK |
| XMRUSDT | 1440 | 0 | 0 | 0 | OK |
| JUPUSDT | 1440 | 0 | 0 | 0 | OK |
| FILUSDT | 1440 | 0 | 0 | 0 | OK |
| FARTCOINUSDT | 1440 | 0 | 0 | 0 | OK |
| ALGOUSDT | 1440 | 0 | 0 | 0 | OK |
| VVVUSDT | 1440 | 0 | 0 | 0 | OK |
| SHIBUSDT | 1440 | 0 | 0 | 0 | OK |
| RENDERUSDT | 1440 | 0 | 0 | 0 | OK |
| DOSUSDT | 1440 | 0 | 0 | 0 | OK |
| MUBARAKUSDT | 1440 | 0 | 0 | 0 | OK |
| FETUSDT | 1440 | 0 | 0 | 0 | OK |
| DOTUSDT | 1440 | 0 | 0 | 0 | OK |
| INXUSDT | 1440 | 0 | 0 | 0 | OK |
| PENGUUSDT | 1440 | 0 | 0 | 0 | OK |
| ASTERUSDT | 1440 | 0 | 0 | 0 | OK |
| HUSDT | 1440 | 0 | 0 | 0 | OK |
| LSKUSDT | 1440 | 0 | 0 | 0 | OK |
| SEIUSDT | 1440 | 0 | 0 | 0 | OK |
| TIAUSDT | 1440 | 0 | 0 | 0 | OK |
| DGAIUSDT | 1440 | 0 | 0 | 0 | OK |
| FLOCKUSDT | 1440 | 0 | 0 | 0 | OK |
| HBARUSDT | 1440 | 0 | 0 | 0 | OK |
| ICPUSDT | 1440 | 0 | 0 | 0 | OK |
| USDBRLUSDT | 1440 | 0 | 0 | 0 | OK |
| CRVUSDT | 1440 | 0 | 0 | 0 | OK |
| IRYSUSDT | 1440 | 0 | 0 | 0 | OK |
| GRAMUSDT | 1440 | 0 | 0 | 0 | OK |
| 牛来USDT | 1440 | 0 | 0 | 0 | OK |
| PONSUSDT | 1440 | 0 | 0 | 0 | OK |
| ENSOUSDT | 1440 | 0 | 0 | 0 | OK |
| JCTUSDT | 1440 | 0 | 0 | 0 | OK |
| IDOLUSDT | 1440 | 0 | 0 | 0 | OK |
| PIUSDT | 1440 | 0 | 0 | 0 | OK |
| WLFIUSDT | 1440 | 0 | 0 | 0 | OK |
| CYBERUSDT | 1440 | 0 | 0 | 0 | OK |
| NIGHTUSDT | 1440 | 0 | 0 | 0 | OK |
| LDOUSDT | 1440 | 0 | 0 | 0 | OK |
| TRXUSDT | 1440 | 0 | 0 | 0 | OK |
| USDJPYUSDT | 1440 | 0 | 0 | 0 | OK |
| WIFUSDT | 1440 | 0 | 0 | 0 | OK |
| KASUSDT | 1440 | 0 | 0 | 0 | OK |
| CTUSDT | 1440 | 0 | 0 | 0 | OK |
| USELESSUSDT | 1440 | 0 | 0 | 0 | OK |
| ELICEUSDT | 1440 | 0 | 0 | 0 | OK |
| CLSUSDT | 1440 | 0 | 0 | 0 | OK |
| VIRTUALUSDT | 1440 | 0 | 0 | 0 | OK |
| ETCUSDT | 1440 | 0 | 0 | 0 | OK |
| SANDUSDT | 1440 | 0 | 0 | 0 | OK |
| ONEUSDT | 1440 | 0 | 0 | 0 | OK |
| SAPIENUSDT | 1440 | 0 | 0 | 0 | OK |
| ETHFIUSDT | 1440 | 0 | 0 | 0 | OK |
| CHIPUSDT | 1440 | 0 | 0 | 0 | OK |
| PYTHUSDT | 1440 | 0 | 0 | 0 | OK |
| XPLUSDT | 1440 | 0 | 0 | 0 | OK |
| BGBUSDT | 1440 | 0 | 0 | 0 | OK |
| RPLUSDT | 1440 | 0 | 0 | 0 | OK |
| INITUSDT | 1440 | 0 | 0 | 0 | OK |
| SKYAIUSDT | 1440 | 0 | 0 | 0 | OK |
| OPUSDT | 1440 | 0 | 0 | 0 | OK |
| ERAUSDT | 1440 | 0 | 0 | 0 | OK |
| GALAUSDT | 1440 | 0 | 0 | 0 | OK |
| ORDIUSDT | 1440 | 0 | 0 | 0 | OK |
| BEATUSDT | 1440 | 0 | 0 | 0 | OK |
| HUMAUSDT | 1440 | 0 | 0 | 0 | OK |
| PIPPINUSDT | 1440 | 0 | 0 | 0 | OK |
| BREVUSDT | 1440 | 0 | 0 | 0 | OK |
| AEROUSDT | 1440 | 0 | 0 | 0 | OK |
| AMDLUSDT | 1440 | 0 | 0 | 0 | OK |
| CFGUSDT | 1440 | 0 | 0 | 0 | OK |
| STRKUSDT | 1440 | 0 | 0 | 0 | OK |
| QUSDT | 1440 | 0 | 0 | 0 | OK |
| MEGAUSDT | 1440 | 0 | 0 | 0 | OK |
| DEXEUSDT | 1440 | 0 | 0 | 0 | OK |
| 1000BONKUSDT | 1440 | 0 | 0 | 0 | OK |
| PLUMEUSDT | 1440 | 0 | 0 | 0 | OK |
| MORPHOUSDT | 1440 | 0 | 0 | 0 | OK |
| MAGMAUSDT | 1440 | 0 | 0 | 0 | OK |
| USUALUSDT | 1440 | 0 | 0 | 0 | OK |
| CAPUSDT | 1440 | 0 | 0 | 0 | OK |
| RAREUSDT | 1440 | 0 | 0 | 0 | OK |
| BANKUSDT | 1440 | 0 | 0 | 0 | OK |
| MARSCOINUSDT | 1440 | 0 | 0 | 0 | OK |
| RAYUSDT | 1440 | 0 | 0 | 0 | OK |
| STXUSDT | 1440 | 0 | 0 | 0 | OK |
| SQDUSDT | 1440 | 0 | 0 | 0 | OK |
| ARUSDT | 1440 | 0 | 0 | 0 | OK |
| MYXUSDT | 1440 | 0 | 0 | 0 | OK |
| GWEIUSDT | 1440 | 0 | 0 | 0 | OK |
| ENSUSDT | 1440 | 0 | 0 | 0 | OK |
| JTOUSDT | 1440 | 0 | 0 | 0 | OK |
| PENDLEUSDT | 1440 | 0 | 0 | 0 | OK |
| NILUSDT | 1440 | 0 | 0 | 0 | OK |
| KAITOUSDT | 1440 | 0 | 0 | 0 | OK |
| SOONUSDT | 1440 | 0 | 0 | 0 | OK |
| POWERUSDT | 1440 | 0 | 0 | 0 | OK |
| BLURUSDT | 1440 | 0 | 0 | 0 | OK |
| FCXUSDT | 1440 | 0 | 0 | 0 | OK |
| KGENUSDT | 1440 | 0 | 0 | 0 | OK |
| GRASSUSDT | 1440 | 0 | 0 | 0 | OK |
| MSUSDT | 1440 | 0 | 0 | 0 | OK |
| BARDUSDT | 1440 | 0 | 0 | 0 | OK |
| GRVTUSDT | 1440 | 0 | 0 | 0 | OK |
| BOMEUSDT | 1440 | 0 | 0 | 0 | OK |
| BABYUSDT | 1440 | 0 | 0 | 0 | OK |
| LABUSDT | 1440 | 0 | 0 | 0 | OK |
| AXISUSDT | 1440 | 0 | 0 | 0 | OK |
| NEMUSDT | 1440 | 0 | 0 | 0 | OK |
| ACUUSDT | 1440 | 0 | 0 | 0 | OK |
| FLOKIUSDT | 1440 | 0 | 0 | 0 | OK |
| BEAMUSDT | 1440 | 0 | 0 | 0 | OK |
| CPUSDT | 1440 | 0 | 0 | 0 | OK |
| 0GUSDT | 1440 | 0 | 0 | 0 | OK |
| ARXUSDT | 1440 | 0 | 0 | 0 | OK |
| BERAUSDT | 1440 | 0 | 0 | 0 | OK |
| GPSUSDT | 1440 | 0 | 0 | 0 | OK |
| KUAISHOUUSDT | 1440 | 0 | 0 | 0 | OK |
| PBRUSDT | 1440 | 0 | 0 | 0 | OK |
| METUSDT | 1440 | 0 | 0 | 0 | OK |
| ORCAUSDT | 1440 | 0 | 0 | 0 | OK |
| KITEUSDT | 1440 | 0 | 0 | 0 | OK |
| ARKMUSDT | 1440 | 0 | 0 | 0 | OK |
| KERNELUSDT | 1440 | 0 | 0 | 0 | OK |
| NUUSDT | 1440 | 0 | 0 | 0 | OK |
| DASHUSDT | 1440 | 0 | 0 | 0 | OK |
| PHAUSDT | 1440 | 0 | 0 | 0 | OK |
| POLUSDT | 1440 | 0 | 0 | 0 | OK |
| CSTOCKUSDT | 1440 | 0 | 0 | 0 | OK |
| EDGEUSDT | 1440 | 0 | 0 | 0 | OK |
| MAGICUSDT | 1440 | 0 | 0 | 0 | OK |
| COOKIEUSDT | 1440 | 0 | 0 | 0 | OK |
| LAUSDT | 1440 | 0 | 0 | 0 | OK |
| RIVERUSDT | 1440 | 0 | 0 | 0 | OK |
| GRTUSDT | 1440 | 0 | 0 | 0 | OK |
| EIGENUSDT | 1440 | 0 | 0 | 0 | OK |
| RAVEUSDT | 1440 | 0 | 0 | 0 | OK |
| ATUSDT | 1440 | 0 | 0 | 0 | OK |
| PEOPLEUSDT | 1440 | 0 | 0 | 0 | OK |
| OPGUSDT | 1440 | 0 | 0 | 0 | OK |
| UBUSDT | 1440 | 0 | 0 | 0 | OK |

## Limitations
- Historical research only; not current entry signals or a profitability claim.
- Breakout/hold is a defined proxy and can miss trends without a 60m range break or with a brief retest.
- The four-times filter compares the 2h movement with the first 10m movement. Later fast bursts are reported separately.
- Historical OI, funding, order-book depth and taker-side history may not cover past events. Missing evidence is not fabricated.
- Returns exclude fees, spread, slippage, funding payments and execution latency. No orders were placed.
- Top 200 means the highest 24h-turnover online crypto USDT perpetuals at test time.
