# live_runner.py
# Live OFI-trading entrypoint. Refuses to trade without a validated stamp.

import asyncio
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("live_runner")

FALLBACK_PARAMS = {
    "ofi_1m_orders_min": 1.5, "ofi_1m_volume_min": 2.0,
    "ofi_3m_orders_min": 2.0, "ofi_3m_volume_min": 3.0,
    "ofi_10m_volume_min": 1.5, "continuation_required": 4,
    "lag_gap_min": 0.5,
}


def _load_and_validate() -> tuple[dict, bool, str]:
    path = Path(os.environ.get("BEST_PARAMS", "/tmp/best_params.json"))
    if not path.exists():
        return FALLBACK_PARAMS, False, f"no params file at {path}"
    try:
        params = json.loads(path.read_text())
    except Exception as e:
        return FALLBACK_PARAMS, False, f"parse error: {e}"

    clean = {k: v for k, v in params.items() if not k.startswith("_")}
    merged = {**FALLBACK_PARAMS, **clean}
    stamp = params.get("_validation")
    if not stamp:
        return merged, False, "no validation stamp — learner has not passed all gates"
    if stamp.get("phase") != "ACTIONABLE":
        return merged, False, f"stamp phase={stamp.get('phase')} — not ACTIONABLE"
    if stamp.get("confirmed_days", 0) < 2:
        return merged, False, f"combo confirmed on only {stamp.get('confirmed_days')} days (need 2)"
    return clean, True, f"validated: {stamp}"


async def main():
    logging.basicConfig(level=logging.INFO)
    params, validated, reason = _load_and_validate()
    if not validated:
        log.warning("=" * 60)
        log.warning("LIVE TRADING BLOCKED: %s", reason)
        log.warning("Falling back to PAPER MODE — no live orders will be sent.")
        log.warning("=" * 60)
        os.environ["PAPER_MODE"] = "true"
    else:
        log.info("live trading approved: %s", reason)
        log.info("params: %s", params)

    symbols = os.environ.get("SYMBOLS", "BTC/USDT:USDT,ETH/USDT:USDT").split(",")
    from body import run as body_run
    await body_run(symbols, params=params)


if __name__ == "__main__":
    asyncio.run(main())
