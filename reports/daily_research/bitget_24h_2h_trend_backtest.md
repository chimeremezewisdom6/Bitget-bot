# Bitget authenticated 24-hour genuine-trend backtest

- Generated UTC: 2026-11-24T06:48:09.501864+00:00
- Window UTC: 2026-11-23T06:47:00+00:00 to 2026-11-24T06:47:00+00:00
- Bitget API key authentication: SUCCESS
- Key permission type: readonly
- Account fee schedule: AVAILABLE
- Access scope: Signed account-info and fee-rate reads only; no balances, positions, orders, or withdrawals.
- Universe: top 200 online crypto USDT perpetuals by 24h turnover.
- Coverage: 200/200 symbols; 288,000 closed 1m candles; 0 fetch errors.
- 2h breakout-and-hold candidates before the 4%/speed filters: 1894
- Candidates reaching 4% over 2h: 130
- Rejected below 4%: 1764
- Rejected by the 4x speed rule: 84
- Qualifying gradual trends: 46 (LONG 25, SHORT 21).

## Exact trend rules
1. A closed 1m candle closes above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT).
2. Every subsequent closed 1m candle remains outside that breakout level for 120 complete minutes.
3. Direction-adjusted net movement from breakout close to the 120th-minute close is at least 4%.
4. The 120m directional move is at least 4 times the absolute directional move in the FIRST 10 minutes. The largest rolling 10m move later in the trend is measured separately as a diagnostic, not used to reject the trend.
5. LONG and SHORT are evaluated separately; gaps and incomplete candles invalidate a sample.

## Aggregate findings
- Mean qualifying 2h directional return: 7.1914%
- Median qualifying 2h directional return: 5.6068%
- Mean 2h-to-fastest-10m ratio: 7.091x

## What the data says fuels the move
- Persistence: 120m breakout-level hold, direction-matching candle counts, and maximum adverse/favorable excursion.
- Participation: first-10m and first-30m quote-turnover acceleration versus the 20m before the breakout.
- Historical open interest: reported only when Bitget's returned 5m observations cover both event boundaries; otherwise left blank.
- Funding and order book: current snapshots for qualifying symbols only. They are not falsely described as historical causes.
- Aggressive buyer/seller dominance: not inferred from OHLCV candles; no unsupported taker-side conclusion.

## Qualifying events
| Symbol | Side | Start UTC | 2h move % | First 10m % | Fastest 10m % | Ratio | 15m aligned | 120m aligned | First 10m turnover x | Historical OI % |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PROMUSDT | LONG | 2026-11-23T09:59:00+00:00 | 30.7534 | 7.2291 | 8.2997 | 4.25x | 10/15 | 71/120 | 24.9143 | None |
| UNITASUSDT | SHORT | 2026-11-23T16:54:00+00:00 | 16.6988 | 2.7925 | 10.0824 | 5.98x | 9/15 | 54/120 | 2.3353 | None |
| ELSAUSDT | LONG | 2026-11-24T04:43:00+00:00 | 15.3395 | 2.3108 | 13.5045 | 6.64x | 10/15 | 64/120 | 1.6171 | 18.77904 |
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
| MUBARAKUSDT | LONG | 2026-11-23T10:23:00+00:00 | 6.4374 | 0.8403 | 5.7642 | 7.66x | 9/15 | 62/120 | 5.709 | None |
| BLESSUSDT | SHORT | 2026-11-23T19:05:00+00:00 | 6.2825 | 1.5467 | 2.9525 | 4.06x | 7/15 | 67/120 | 1.0061 | None |
| OPGUSDT | LONG | 2026-11-23T13:57:00+00:00 | 6.1317 | 0.6839 | 2.1626 | 8.97x | 3/15 | 21/120 | 1.044 | None |
| BTWUSDT | LONG | 2026-11-23T12:04:00+00:00 | 5.8755 | 1.3492 | 2.9239 | 4.35x | 10/15 | 63/120 | 1.6748 | None |
| NAORISUSDT | SHORT | 2026-11-23T14:05:00+00:00 | 5.8398 | 0.4329 | 2.7490 | 13.49x | 7/15 | 58/120 | 0.635 | None |
| MONUSDT | SHORT | 2026-11-23T15:47:00+00:00 | 5.8158 | 1.4504 | 2.1904 | 4.01x | 8/15 | 47/120 | 5.7476 | None |
| UAIUSDT | LONG | 2026-11-23T12:18:00+00:00 | 5.7607 | 0.9554 | 3.3947 | 6.03x | 8/15 | 57/120 | 0.956 | None |
| APRUSDT | LONG | 2026-11-23T13:33:00+00:00 | 5.6367 | 0.3765 | 5.1186 | 14.97x | 4/15 | 58/120 | 25.8722 | None |
| CYSUSDT | LONG | 2026-11-23T13:33:00+00:00 | 5.5769 | 1.3084 | 3.5877 | 4.26x | 10/15 | 65/120 | 1.0359 | None |
| BEATUSDT | LONG | 2026-11-23T13:57:00+00:00 | 5.5343 | 1.3500 | 2.5585 | 4.10x | 10/15 | 65/120 | 4.6445 | None |
| USUALUSDT | SHORT | 2026-11-23T19:26:00+00:00 | 5.5215 | 1.2227 | 2.3572 | 4.52x | 7/15 | 27/120 | 65.0486 | None |
| LUNCUSDT | LONG | 2026-11-23T09:45:00+00:00 | 5.5128 | 0.4472 | 2.1081 | 12.33x | 3/15 | 54/120 | 31.6989 | None |
| ICNTUSDT | SHORT | 2026-11-23T11:38:00+00:00 | 5.4993 | 0.7219 | 2.9141 | 7.62x | 10/15 | 67/120 | 3.6033 | None |
| BEATUSDT | SHORT | 2026-11-23T19:20:00+00:00 | 5.4991 | 1.3004 | 3.4362 | 4.23x | 11/15 | 59/120 | 2.3148 | None |
| MONUSDT | LONG | 2026-11-24T01:54:00+00:00 | 5.4654 | 1.1159 | 3.1483 | 4.90x | 8/15 | 42/120 | 9.6323 | None |
| MONUSDT | LONG | 2026-11-24T04:23:00+00:00 | 5.2877 | 1.2698 | 2.4883 | 4.16x | 5/15 | 52/120 | 1.5778 | 8.3509 |
| IOSTUSDT | LONG | 2026-11-23T12:10:00+00:00 | 5.2866 | 0.8109 | 4.5122 | 6.52x | 4/15 | 39/120 | 2.874 | None |
| CROSSUSDT | SHORT | 2026-11-23T14:55:00+00:00 | 5.1707 | 1.2684 | 2.2706 | 4.08x | 7/15 | 49/120 | 23.0999 | None |
| VELVETUSDT | LONG | 2026-11-23T08:04:00+00:00 | 5.1314 | 0.8235 | 2.0558 | 6.23x | 7/15 | 55/120 | 1.4213 | None |
| LITUSDT | SHORT | 2026-11-23T16:41:00+00:00 | 5.1158 | 0.4458 | 2.0221 | 11.48x | 8/15 | 65/120 | 1.104 | None |
| BTWUSDT | SHORT | 2026-11-23T08:53:00+00:00 | 4.9069 | 0.9512 | 2.0752 | 5.16x | 11/15 | 71/120 | 3.5167 | None |
| MONUSDT | SHORT | 2026-11-23T08:18:00+00:00 | 4.8321 | 0.9764 | 2.5381 | 4.95x | 4/15 | 48/120 | 1.2378 | None |
| REUSDT | LONG | 2026-11-24T04:09:00+00:00 | 4.6964 | 1.0710 | 1.6938 | 4.39x | 6/15 | 50/120 | 0.4638 | None |
| CPUSDT | SHORT | 2026-11-24T00:48:00+00:00 | 4.5585 | 0.9218 | 2.5040 | 4.95x | 6/15 | 45/120 | 0.5078 | None |
| CROSSUSDT | SHORT | 2026-11-23T19:53:00+00:00 | 4.3752 | 0.8041 | 1.8687 | 5.44x | 6/15 | 52/120 | 13.897 | None |
| ONGUSDT | LONG | 2026-11-24T03:57:00+00:00 | 4.2511 | 0.1970 | 1.1783 | 21.57x | 8/15 | 65/120 | 2.3547 | None |
| ZROUSDT | SHORT | 2026-11-23T18:10:00+00:00 | 4.2212 | 0.6692 | 1.4729 | 6.31x | 7/15 | 63/120 | 16.8145 | None |
| PONSUSDT | SHORT | 2026-11-23T15:42:00+00:00 | 4.1427 | 1.0076 | 1.9292 | 4.11x | 8/15 | 65/120 | 1.3666 | None |
| NAORISUSDT | SHORT | 2026-11-23T20:23:00+00:00 | 4.1191 | 0.9154 | 1.9455 | 4.50x | 6/15 | 41/120 | 2.0643 | None |
| MMTUSDT | LONG | 2026-11-23T23:08:00+00:00 | 4.0252 | 0.5914 | 3.0201 | 6.81x | 9/15 | 65/120 | 17.3946 | None |
| SPKUSDT | LONG | 2026-11-24T04:01:00+00:00 | 4.0000 | 0.5004 | 1.9592 | 7.99x | 6/15 | 32/120 | 2.1029 | None |

## Per-coin coverage
| Symbol | Candles | Trends | LONG | SHORT | Status |
|---|---:|---:|---:|---:|---|
| MONUSDT | 1440 | 4 | 2 | 2 | OK |
| UNITASUSDT | 1440 | 3 | 1 | 2 | OK |
| MMTUSDT | 1440 | 2 | 1 | 1 | OK |
| BTWUSDT | 1440 | 2 | 1 | 1 | OK |
| VELVETUSDT | 1440 | 2 | 2 | 0 | OK |
| CROSSUSDT | 1440 | 2 | 0 | 2 | OK |
| BEATUSDT | 1440 | 2 | 1 | 1 | OK |
| NAORISUSDT | 1440 | 2 | 0 | 2 | OK |
| EVAAUSDT | 1440 | 1 | 0 | 1 | OK |
| ELSAUSDT | 1440 | 1 | 1 | 0 | OK |
| BLESSUSDT | 1440 | 1 | 0 | 1 | OK |
| PROMUSDT | 1440 | 1 | 1 | 0 | OK |
| CYSUSDT | 1440 | 1 | 1 | 0 | OK |
| ACEUSDT | 1440 | 1 | 1 | 0 | OK |
| LISTAUSDT | 1440 | 1 | 1 | 0 | OK |
| SKYUSDT | 1440 | 1 | 0 | 1 | OK |
| ZROUSDT | 1440 | 1 | 0 | 1 | OK |
| MUBARAKUSDT | 1440 | 1 | 1 | 0 | OK |
| ATOMUSDT | 1440 | 1 | 1 | 0 | OK |
| ICNTUSDT | 1440 | 1 | 0 | 1 | OK |
| SAHARAUSDT | 1440 | 1 | 1 | 0 | OK |
| PONSUSDT | 1440 | 1 | 0 | 1 | OK |
| APRUSDT | 1440 | 1 | 1 | 0 | OK |
| LUNCUSDT | 1440 | 1 | 1 | 0 | OK |
| LITUSDT | 1440 | 1 | 0 | 1 | OK |
| REUSDT | 1440 | 1 | 1 | 0 | OK |
| USUALUSDT | 1440 | 1 | 0 | 1 | OK |
| IOSTUSDT | 1440 | 1 | 1 | 0 | OK |
| ALLOUSDT | 1440 | 1 | 1 | 0 | OK |
| UAIUSDT | 1440 | 1 | 1 | 0 | OK |
| CPUSDT | 1440 | 1 | 0 | 1 | OK |
| ONGUSDT | 1440 | 1 | 1 | 0 | OK |
| SPKUSDT | 1440 | 1 | 1 | 0 | OK |
| ZESTUSDT | 1440 | 1 | 0 | 1 | OK |
| OPGUSDT | 1440 | 1 | 1 | 0 | OK |
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
| PIPPINUSDT | 1440 | 0 | 0 | 0 | OK |
| BREVUSDT | 1440 | 0 | 0 | 0 | OK |
| HUMAUSDT | 1440 | 0 | 0 | 0 | OK |
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
| UBUSDT | 1440 | 0 | 0 | 0 | OK |

## Limitations
- Historical research only; not current entry signals or a profitability claim.
- Breakout/hold is a defined proxy and can miss trends without a 60m range break or with a brief retest.
- The four-times filter compares the 2h movement with the first 10m movement. Later fast bursts are reported separately.
- Historical OI, funding, order-book depth and taker-side history may not cover past events. Missing evidence is not fabricated.
- Returns exclude fees, spread, slippage, funding payments and execution latency. No orders were placed.
- Top 200 means the highest 24h-turnover online crypto USDT perpetuals at test time.
