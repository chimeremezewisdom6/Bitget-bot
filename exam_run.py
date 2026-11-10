"""
exam_run.py — entry point with keep-alive server for Render.
"""

import os
import time
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import exam_core as core

log = logging.getLogger("exam")


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
        f"starting {core.VERSION} | paper={core.PAPER} | leverage={core.LEVERAGE}x "
        f"| margin={core.MARGIN_MODE} | streak={core.REQUIRED_STREAK} "
        f"| win={core.WIN_THRESHOLD:.4f} | interval={core.INTERVAL_S}s "
        f"| candle_limit={core.CANDLE_PAGE_LIMIT}"
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
