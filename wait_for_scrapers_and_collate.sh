#!/usr/bin/env bash
set -euo pipefail

# Wait for scrapers to finish (scrapers_last_done.txt) then run collate_all()
# Usage: scheduled once daily after the scraper window (e.g. 04:30)

cd "$(dirname "$0")"
PYTHON="$(pwd)/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

MAX_WAIT=$((3 * 3600))   # maximum wait (seconds) before proceeding anyway
POLL_SEC=30
START=$(date +%s)

echo "$(date -u +'%Y-%m-%d %H:%M:%S') - wait_for_scrapers_and_collate.sh - waiting for scrapers to finish" >> cal_collate.log

while true; do
  if [ -f scrapers_last_done.txt ]; then
    echo "$(date -u +'%Y-%m-%d %H:%M:%S') - scrapers_done marker found" >> cal_collate.log
    break
  fi

  NOW=$(date +%s)
  ELAPSED=$((NOW - START))
  if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    echo "$(date -u +'%Y-%m-%d %H:%M:%S') - timeout waiting for scrapers (proceeding to collate)" >> cal_collate.log
    break
  fi

  sleep "$POLL_SEC"
done

# Run collation (this also calls rotate_and_zip_logs via cal_collate)
$PYTHON -c "from cal_collate import collate_all; collate_all()" >> cal_collate.log 2>&1 || echo "$(date -u) - collate failed" >> cal_collate.log

# Remove sentinel to reset for next day
rm -f scrapers_last_done.txt || true

exit 0
