#!/usr/bin/env bash
set -euo pipefail

# Ensure toronto_screenings.ics exists (re-run collate if necessary), then run log rotation
# Usage: scheduled once daily after collate (e.g. 05:30)

cd "$(dirname "$0")"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

# If combined calendar is missing or older than 24h, attempt to collate again
if [ ! -f "$PROJECT_ROOT/toronto_screenings.ics" ] || [ $(find "$PROJECT_ROOT/toronto_screenings.ics" -mtime +0 2>/dev/null || true) ]; then
  echo "$(date -u +'%Y-%m-%d %H:%M:%S') - toronto_screenings.ics missing/old — re-running collate" >> "$PROJECT_ROOT/cal_collate.log"
  $PYTHON "$PROJECT_ROOT/cal_collate.py" >> "$PROJECT_ROOT/cal_collate.log" 2>&1 || echo "$(date -u) - collate retry failed" >> "$PROJECT_ROOT/cal_collate.log"
fi

# If collated file present and non-empty, run log rotation
if [ -f "$PROJECT_ROOT/toronto_screenings.ics" ] && [ -s "$PROJECT_ROOT/toronto_screenings.ics" ]; then
  echo "$(date -u +'%Y-%m-%d %H:%M:%S') - verified toronto_screenings.ics exists — running log.py" >> "$PROJECT_ROOT/cal_collate.log"
  $PYTHON "$PROJECT_ROOT/scraper/log.py" >> "$PROJECT_ROOT/cal_collate.log" 2>&1 || python3 "$PROJECT_ROOT/scraper/log.py" >> "$PROJECT_ROOT/cal_collate.log" 2>&1 || echo "$(date -u) - log.py failed" >> "$PROJECT_ROOT/cal_collate.log"
else
  echo "$(date -u +'%Y-%m-%d %H:%M:%S') - toronto_screenings.ics still missing — skipping log rotation" >> "$PROJECT_ROOT/cal_collate.log"
fi

exit 0
