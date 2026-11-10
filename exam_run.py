"""
exam_run.py — entry point with keep-alive server for Render.
Runs the trading loop in a background thread, serves /health on $PORT.
"""

import os
import json
import time
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import exam_core as core

log = logging.getLogger("exam")

r_map_raw = os.environ.get("R_BASE_MAP", "")
if r_map_raw:
    try:
        core.R_BASE_MAP.update(json.loads(r_map_raw))
        log.info(f"R_BASE_MAP loaded: {len(core.R_BASE_MAP)} entries")
    except Exception as e:
        log.warning(f"R_BASE_MAP parse failed: {e}")


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass


def start_keepalive():
    port = int(os.environ.get("PORT", "10000"))
    srv = HTTPServer(("0.0.0.0", port), Health)
    log.info(f"keep-alive listening on :{port}")
    srv.serve_forever()


def trading_loop():
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
    threading.Thread(target=start_keepalive, daemon=True).start()
    trading_loop()
