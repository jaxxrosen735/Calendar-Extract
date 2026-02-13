#!/usr/bin/env bash
# Install / remove the project cron block into the current user's crontab
# Usage:
#   ./install_crontab.sh        # install (default)
#   ./install_crontab.sh --remove
#   ./install_crontab.sh --show
#   ./install_crontab.sh --dry-run

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="${PROJECT_DIR}/deploy/crontab.backup.${TIMESTAMP}"

CRON_HEADER="# >>> toronto-screenings cron block >>>"
CRON_FOOTER="# <<< toronto-screenings cron block <<<"

CRON_BLOCK=$(cat <<CRON
${CRON_HEADER}
# Managed by deploy/install_crontab.sh — safely replaceable block
0 0 * * * cd "${PROJECT_DIR}" && ./scripts/run_scrapers_random.sh >> "${PROJECT_DIR}/run_scrapers_random.log" 2>&1
30 4 * * * cd "${PROJECT_DIR}" && ./scripts/wait_for_scrapers_and_collate.sh >> "${PROJECT_DIR}/cal_collate_cron.log" 2>&1
30 5 * * * cd "${PROJECT_DIR}" && ./scripts/verify_collate_and_rotate.sh >> "${PROJECT_DIR}/log_rotation_cron.log" 2>&1
${CRON_FOOTER}
CRON
)

_usage() {
  cat <<USAGE
Usage: $0 [--remove|--show|--dry-run]

Options:
  --remove    Remove the installed cron block (if present)
  --show      Print the current crontab and highlight managed block (if any)
  --dry-run   Print the cron block that would be installed (do not modify crontab)
  (no args)   Install or replace the managed cron block
USAGE
}

COMMAND="install"
for arg in "$@"; do
  case "$arg" in
    --remove) COMMAND="remove" ;;
    --show) COMMAND="show" ;;
    --dry-run) COMMAND="dry-run" ;;
    --help|-h) _usage; exit 0 ;;
    *) echo "Unknown arg: $arg"; _usage; exit 1 ;;
  esac
done

# Safely read current crontab (empty string if none)
_current_crontab() {
  crontab -l 2>/dev/null || true
}

_install_block() {
  echo "Backing up existing crontab to: ${BACKUP}"
  _current_crontab > "${BACKUP}" || true

  # Remove any existing managed block, then append new block
  awk "BEGIN{inblock=0} 
       /${CRON_HEADER//"/\"}/ {inblock=1; next} 
       /${CRON_FOOTER//"/\"}/ {inblock=0; next} 
       !inblock {print}" "${BACKUP}" > "${BACKUP}.cleaned" || true

  # Write cleaned + new block to temp file and load into crontab
  printf '%s\n' "$(cat "${BACKUP}.cleaned")" > "${BACKUP}.new"
  printf '%s\n' "${CRON_BLOCK}" >> "${BACKUP}.new"
  crontab "${BACKUP}.new"

  echo "Installed cron block (backup at ${BACKUP})."
}

_remove_block() {
  echo "Backing up existing crontab to: ${BACKUP}"
  _current_crontab > "${BACKUP}" || true

  # Remove managed block and re-install cleaned crontab
  awk "BEGIN{inblock=0} 
       /${CRON_HEADER//"/\"}/ {inblock=1; next} 
       /${CRON_FOOTER//"/\"}/ {inblock=0; next} 
       !inblock {print}" "${BACKUP}" > "${BACKUP}.cleaned"

  crontab "${BACKUP}.cleaned"
  echo "Removed managed cron block (backup at ${BACKUP})."
}

_show_crontab() {
  echo "--- current crontab ---"
  _current_crontab || echo "(no crontab)"
  echo "--- managed cron block that would be installed ---"
  echo "${CRON_BLOCK}"
}

case "$COMMAND" in
  dry-run)
    echo "--- dry-run: cron block to install ---"
    echo "${CRON_BLOCK}"
    ;;
  show)
    _show_crontab
    ;;
  remove)
    _remove_block
    ;;
  install)
    _install_block
    ;;
  *)
    echo "Unknown command: $COMMAND" ; _usage ; exit 1 ;;
esac

exit 0
