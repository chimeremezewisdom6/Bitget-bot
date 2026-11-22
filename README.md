# Bitget Demo Scanner

A Python scanner for Bitget USDT-margined futures. The repository is deliberately locked to **Bitget Demo trading**.

## Safety status

- `scanner.py` hard-locks `BITGET_DEMO_MODE = True`; an environment variable cannot switch it to live trading.
- Demo authenticated requests include Bitget's required `paptrading: 1` header.
- `BOT_DRY_RUN=true` performs a read-only scan and must not change leverage or submit orders.
- The automated scanner workflow is intentionally paused. Do not remove its safety condition until a supervised Demo test has verified account access, order placement, fill confirmation, position monitoring, and reduce-only closing.
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

For the manual Demo smoke test, configure these repository Actions secrets using a **Bitget Demo API key**, never a live-trading key:

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

1. Confirm the credentials are a Bitget Demo API key with the required read/trade permissions.
2. Run the manual read-only smoke test and inspect its logs.
3. Verify the account mode, available Demo balance, instrument rules and open positions.
4. Test a supervised Demo entry, confirmed fill, stop-loss, and reduce-only close.
5. Confirm position state survives workflow restarts. GitHub-hosted runners are ephemeral; state persistence must be deliberately implemented and tested before relying on scheduled or continuous runs.

Never use this project with live-account credentials.
