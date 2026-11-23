# Bitget Demo Scanner

A Python scanner for Bitget USDT-margined futures. The repository is deliberately locked to **Bitget Demo trading**.

## Project knowledge and research history

Read [docs/PROJECT_KNOWLEDGE_BASE.md](docs/PROJECT_KNOWLEDGE_BASE.md) for the dated project history, verified engineering findings, strategy parameters, test coverage, known failures, shadow-trading research protocol, and experiment log. Update that file whenever a meaningful test, finding, strategy decision, or limitation changes.

**Current user instruction (2026-11-23): observation-only research.** Do not place Live or Demo orders. The scanner remains order-capable in Demo mode; keep automated trading paused and do not run it with `BOT_DRY_RUN=false`.

## Safety status

- `scanner.py` hard-locks `BITGET_DEMO_MODE = True`; an environment variable cannot switch it to live trading.
- Demo authenticated requests include Bitget's required `paptrading: 1` header.
- `BOT_DRY_RUN=true` performs a read-only scan and must not change leverage or submit orders.
- The automated scanner workflow is intentionally paused. Do not remove its safety condition until a supervised Demo test has verified account access, order placement, fill confirmation, position monitoring, and reduce-only closing—and only after explicit authorization. The current instruction is no Demo or Live trading.
- Passing unit tests is not proof that the exchange connection or a real Demo order lifecycle works.

## Repository layout

| Path | Purpose |
| --- | --- |
| `scanner.py` | Market scanning, account checks, Demo order handling, position supervision and exits |
| `requirements.txt` | Python dependencies |
| `tests/test_scanner_safety.py` | Strategy, sizing, price-rounding and dry-run safety tests |
| `.github/workflows/validate.yml` | Compile and run unit tests on pushes and manual dispatch |
| `.github/workflows/demo-smoke-test.yml` | Manual, read-only Bitget Demo account/market smoke test |
| `.github/workflows/scanner.yml` | Deliberately paused automated scanner workflow |
| `live_active_trade.json` | Persistent local state for the currently supervised Demo position |
| `live_streak.json` | Persistent Demo win-streak state |
| `archive/legacy_trade_history.json` | Historical records retained for reference; not read by the current scanner |

Runtime-generated files such as decision logs and live trade history are not source code. Do not commit API credentials or private keys.

## GitHub Actions secrets

For the historical manual Demo smoke test, the workflow reads these repository Actions secrets using a **Bitget Demo API key**, never a live-trading key:

- `BITGET_API_KEY`
- `BITGET_SECRET_KEY`
- `BITGET_PASSPHRASE`

The smoke-test workflow sets `BOT_DRY_RUN=true` and `CONTINUOUS_247_LOOP=false`. It checks the account and market data without placing orders. Configure one API key set for the intended Demo account. If extra key sets are present, the scanner deliberately uses only the first so balance, positions, entries and exits cannot accidentally target different accounts.

## Local validation

Use Python 3.11 or newer:

```bash
python -m pip install -r requirements.txt
python -m py_compile scanner.py
python -m unittest discover -s tests -v
```

## Before enabling automated Demo trading

Trading is currently prohibited by the user's observation-only instruction. Do not enable it. The following historical checklist is retained for engineering context only:

1. Confirm credentials are a Bitget Demo API key with the required permissions.
2. Run the manual read-only smoke test and inspect its logs.
3. Verify account mode, available Demo balance, instrument rules and open positions.
4. Test a supervised Demo entry, confirmed fill, stop-loss, and reduce-only close.
5. Confirm position state survives workflow restarts. GitHub-hosted runners are ephemeral; state persistence must be deliberately implemented and tested before relying on scheduled or continuous runs.

Never use this project with live-account credentials.


## Read-only shadow market research

A separate collector now exists at `shadow_research.py`. It reads only Bitget public **USDT perpetual futures** instruments, tickers and order books. It does not use account credentials or call trading endpoints.

Run locally:

```bash
python shadow_research.py --min-turnover 500000 --top-depth 50
```

Or open **Actions → Shadow Market Snapshot (Read Only) → Run workflow**. The run uploads timestamped JSON and CSV artifacts. The default screen is $500,000 24-hour USDT turnover, with order-book depth collected for the 50 highest-turnover eligible contracts.

The collector estimates visible-book market buy/sell fills at $100, $500 and $1,000, plus spread and depth inside 0.1%, 0.5% and 1%. These are hypothetical estimates, not fills. Bitget futures endpoints do not supply circulating market cap; market caps must be joined separately and timestamped before any coin is assigned to a cap band.

No Pollinations key is needed for numeric market collection. Pollinations may later be used for separate text analysis of public trader research, but never as the source of market prices, volume, order-book depth or P&L. Keep any future Pollinations credential in a budget-limited Actions Secret, never in source code or repository Variables.
