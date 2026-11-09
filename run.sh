#!/usr/bin/env bash
# run.sh — start the paper bot
set -e
pip install -r requirements.txt
mkdir -p /tmp/paper_exhaustion
nohup python paper_exhaustion.py > /tmp/paper_exhaustion/console.log 2>&1 &
echo "paper bot running (PID $!)"
echo "logs: tail -f /tmp/paper_exhaustion/console.log"
echo "csv:  tail -f /tmp/paper_exhaustion/trades.csv"
