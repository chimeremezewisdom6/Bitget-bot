"""
exam_run.py — Thin entry point. Imports exam_core and calls main().
"""

import logging
import exam_core

def main():
    logging.getLogger("exam").info(
        f"exam_run.py dispatching to exam_core {exam_core.VERSION}"
    )
    exam_core.main()

if __name__ == "__main__":
    main()
