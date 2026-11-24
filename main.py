"""Canonical root entry point for the Bitget read-only research scanner.

GitHub Actions cron calls this file directly so the scanner is visible at the
repository root on the main branch. The implementation remains in
 daily_research.py to keep the research engine modular.
"""
from daily_research import main


if __name__ == "__main__":
    main()
