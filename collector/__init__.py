"""Read-only Bitget collection package.

Phase A: this package is not imported by ``main.py`` or ``daily_research.py``.
It performs only public market-data GETs plus the two approved read-only fee
endpoints. It never places, amends or cancels orders.
"""

BUNDLE_VERSION = 1
