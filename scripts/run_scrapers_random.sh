#!/usr/bin/env bash
set -euo pipefail

# Run all three scrapers at a random time between 00:00 and 04:00.
# Usage: invoked once daily by cron at 00:00; the script chooses a random delay.

cd "$(dirname "$0")"

# Project root
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Prefer venv python if available
PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

# Random delay in seconds (0 .. 4*3600-1)
DELAY=$((RANDOM % 14400))
echo "$(date -u +'%Y-%m-%d %H:%M:%S') - run_scrapers_random.sh - sleeping for ${DELAY}s" >> "$PROJECT_ROOT/run_scrapers_random.log"
sleep "$DELAY"

echo "$(date -u +'%Y-%m-%d %H:%M:%S') - run_scrapers_random.sh - starting scrapers" >> "$PROJECT_ROOT/run_scrapers_random.log"

# Run scrapers sequentially; write logs to project root
$PYTHON "$PROJECT_ROOT/scraper/revue.py" >> "$PROJECT_ROOT/revue_scraper.log" 2>&1 || echo "$(date -u) - revue failed" >> "$PROJECT_ROOT/run_scrapers_random.log"
$PYTHON "$PROJECT_ROOT/scraper/tiff.py"  >> "$PROJECT_ROOT/tiff_scraper.log" 2>&1  || echo "$(date -u) - tiff failed" >> "$PROJECT_ROOT/run_scrapers_random.log"
$PYTHON "$PROJECT_ROOT/scraper/fox.py"   >> "$PROJECT_ROOT/fox_scraper.log"   2>&1   || echo "$(date -u) - fox failed" >> "$PROJECT_ROOT/run_scrapers_random.log"

# Mark completion for the collate step to detect
echo "$(date -u +'%Y-%m-%d %H:%M:%S') - scrapers completed" > "$PROJECT_ROOT/scrapers_last_done.txt"

echo "$(date -u +'%Y-%m-%d %H:%M:%S') - run_scrapers_random.sh - finished" >> "$PROJECT_ROOT/run_scrapers_random.log"
exit 0
