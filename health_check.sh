#!/usr/bin/env bash
set -euo pipefail

# Simple health check for the collated calendar used by systemd / external monitors.
# Returns 0 when `toronto_screenings.ics` exists and is newer than 36 hours (2160 minutes).

DIR="$(cd "$(dirname "$0")/.." && pwd)"
FILE="$DIR/toronto_screenings.ics"
MAX_AGE_MIN=$((36 * 60))   # 36 hours

if [ -f "$FILE" ] && find "$FILE" -mmin -"${MAX_AGE_MIN}" -print -quit >/dev/null 2>&1; then
  exit 0
else
  echo "toronto_screenings.ics missing or stale (older than ${MAX_AGE_MIN} minutes)" >&2
  exit 1
fi
