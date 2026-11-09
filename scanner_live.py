# scanner_live.py
# Live scanner entrypoint. Refuses to run live without 8 consecutive wins.

import asyncio
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("scanner_live")

VALIDATION_PATH = Path(os.environ.get("VALIDATION_STAMP", "/tmp/scanner_validation.json"))


def _check_validation() -> tuple[bool, str]:
    if not VALIDATION_PATH.exists():
        return False, f"no validation stamp at {VALIDATION_PATH}"
    try:
        stamp = json.loads(VALIDATION_PATH.read_text())
    except Exception as e:
        return False, f"stamp parse error: {e}"
    if stamp.get("streak", 0) < 8:
        return False, f"streak={stamp.get('streak')} < 8"
    return True, f"validated: streak={stamp['streak']} at {stamp.get('validated_at_iso')}"


async def main():
    logging.basicConfig(level=logging.INFO)
    validated, reason = _check_validation()
    if not validated:
        log.warning("=" * 60)
        log.warning("SCANNER LIVE TRADING BLOCKED: %s", reason)
        log.warning("Scanner will remain in PAPER mode until 8 consecutive wins.")
        log.warning("=" * 60)
        os.environ["PAPER_MODE"] = "true"
    else:
        log.info("=" * 60)
        log.info("SCANNER LIVE TRADING APPROVED: %s", reason)
        log.info("=" * 60)

    from scanner import ScannerRunner
    from body import run as body_run
    symbols = os.environ.get("SYMBOLS", "BTC/USDT:USDT,ETH/USDT:USDT").split(",")
    scanner = ScannerRunner()
    await asyncio.gather(scanner.run(), body_run(symbols))


if __name__ == "__main__":
    asyncio.run(main())
