#!/usr/bin/env bash
set -euo pipefail

# Run all three scrapers at a random time between 00:00 and 04:00.
# Usage: invoked once daily by cron at 00:00; the script chooses a random delay.

cd "$(dirname "$0")"

# Prefer venv python if available
PYTHON="$(pwd)/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

# Random delay in seconds (0 .. 4*3600-1)
DELAY=$((RANDOM % 14400))
echo "$(date -u +'%Y-%m-%d %H:%M:%S') - run_scrapers_random.sh - sleeping for ${DELAY}s" >> run_scrapers_random.log
sleep "$DELAY"

echo "$(date -u +'%Y-%m-%d %H:%M:%S') - run_scrapers_random.sh - starting scrapers" >> run_scrapers_random.log

# Run scrapers sequentially; append their output to their respective logs
$PYTHON -c "from revue import scrape_all; scrape_all()" >> revue_scraper.log 2>&1 || echo "$(date -u) - revue failed" >> run_scrapers_random.log
$PYTHON -c "from tiff import scrape_all; scrape_all()"  >> tiff_scraper.log 2>&1  || echo "$(date -u) - tiff failed" >> run_scrapers_random.log
$PYTHON -c "from fox import scrape_all; scrape_all()"   >> fox_scraper.log 2>&1   || echo "$(date -u) - fox failed" >> run_scrapers_random.log

# Mark completion for the collate step to detect
echo "$(date -u +'%Y-%m-%d %H:%M:%S') - scrapers completed" > scrapers_last_done.txt

echo "$(date -u +'%Y-%m-%d %H:%M:%S') - run_scrapers_random.sh - finished" >> run_scrapers_random.log
exit 0
