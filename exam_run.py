"""
exam_run.py — entry point. Loads R_BASE_MAP, starts loop, paper/live auto.
"""

import os
import json
import time
import logging

import exam_core as core

log = logging.getLogger("exam")

# Inject per-coin R base if provided (JSON string in env)
r_map_raw = os.environ.get("R_BASE_MAP", "")
if r_map_raw:
    try:
        core.R_BASE_MAP.update(json.loads(r_map_raw))
        log.info(f"R_BASE_MAP loaded: {len(core.R_BASE_MAP)} entries")
    except Exception as e:
        log.warning(f"R_BASE_MAP parse failed: {e}")


def main():
    log.info(
        f"starting | paper={core.PAPER} | leverage={core.LEVERAGE}x "
        f"| streak={core.REQUIRED_STREAK} | win={core.WIN_THRESHOLD:.4f} "
        f"| interval={core.INTERVAL_S}s"
    )
    trader = core.ExamTrader()
    while True:
        try:
            trader.step()
        except Exception as e:
            log.error(f"step error: {e}", exc_info=True)
            trader.healer.check_exception(e)
        time.sleep(core.INTERVAL_S)


if __name__ == "__main__":
    main()
