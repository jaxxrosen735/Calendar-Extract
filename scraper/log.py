"""
Log rotation and daily zipping utility.

- Renames `*_scraper.log` → `*_scraper_YYYYMMDD.log` (if non-empty)
- Renames `omdb_not_found.txt` → `omdb_not_found_YYYYMMDD.txt` (if present)
- Bundles all rotated files into `YYYYMMDD_logs.zip` and removes the rotated copies
- Recreates empty original `*_scraper.log` files so scrapers can continue logging

Usage:
    python3 log.py            # rotate logs for today and create daily zip
    from log import rotate_and_zip_logs

This centralizes the previous OMDb log-zip logic and adds scraper-log rotation.
"""

import glob
import os
import zipfile
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _dated_name(path: str, date_str: str) -> str:
    base, ext = os.path.splitext(path)
    return f"{base}_{date_str}{ext}"


def rotate_and_zip_logs(date: str | None = None) -> str | None:
    """Rotate today's scraper logs and omdb_not_found, then zip them.

    Args:
        date: Optional YYYYMMDD string. Defaults to today's local date.

    Returns:
        Path to the created zip archive, or None if nothing was archived.
    """
    date = date or datetime.now().strftime('%Y%m%d')
    log_files = list(glob.glob('*_scraper.log'))
    collate_log = 'cal_collate.log'
    omdb_src = 'omdb_not_found.txt'
    files_to_archive = []

    # Collect all log files to archive (including collate and omdb logs)
    for src in log_files:
        if os.path.isfile(src) and os.path.getsize(src) > 0:
            newname = f"{date}_{src}"
            files_to_archive.append((src, newname))
    if os.path.isfile(collate_log) and os.path.getsize(collate_log) > 0:
        newname = f"{date}_{collate_log}"
        files_to_archive.append((collate_log, newname))
    if os.path.isfile(omdb_src) and os.path.getsize(omdb_src) > 0:
        # append a small archive marker for traceability
        try:
            with open(omdb_src, 'a', encoding='utf-8') as f:
                f.write(f"\nArchived by rotate_and_zip_logs: {datetime.now().isoformat()}\n")
        except Exception as ex:
            logger.warning("Failed to append archive marker to %s: %s", omdb_src, ex)
        newname = f"{date}_{omdb_src}"
        files_to_archive.append((omdb_src, newname))

    if not files_to_archive:
        logger.info("No logs to rotate for %s", date)
        return None

    # 1) Copy all log files to new dated names (preserve contents for archiving)
    for src, dst in files_to_archive:
        try:
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                fdst.write(fsrc.read())
            logger.info("Copied %s -> %s", src, dst)
        except Exception as ex:
            logger.warning("Failed copying %s to %s: %s", src, dst, ex)

    # 2) Zip all new files together: <YYYYMMDD>_logs.zip
    zip_name = f"{date}_logs.zip"
    try:
        with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for _, dst in files_to_archive:
                try:
                    zf.write(dst, arcname=os.path.basename(dst))
                except Exception as ex:
                    logger.warning("Failed to add %s to zip: %s", dst, ex)
        logger.info("Created archive %s (contains %d files)", zip_name, len(files_to_archive))

        # 3) Remove the new files now that they're archived
        for _, dst in files_to_archive:
            try:
                os.remove(dst)
            except Exception as ex:
                logger.warning("Failed to remove dated file %s: %s", dst, ex)

        # After archiving, create new blank log files for all expected logs
        blank_logs = [
            'fox_scraper.log',
            'tiff_scraper.log',
            'revue_scraper.log',
            'cal_collate.log',
            'omdb_not_found.txt',
        ]
        for fname in blank_logs:
            try:
                open(fname, 'w', encoding='utf-8').close()
                logger.info("Created blank log file: %s", fname)
            except Exception as ex:
                logger.warning("Failed to create blank log file %s: %s", fname, ex)
        return zip_name

    except Exception as ex:
        logger.error("Failed to create zip %s: %s", zip_name, ex, exc_info=True)
        return None


if __name__ == '__main__':
    zipfile_path = rotate_and_zip_logs()
    if zipfile_path:
        logger.info("Rotation complete — archive: %s", zipfile_path)
    else:
        logger.info("Rotation complete — no archive created.")
