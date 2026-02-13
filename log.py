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
    rotated = []

    # 1) Rotate *_scraper.log files
    for src in glob.glob('*_scraper.log'):
        try:
            if not os.path.isfile(src):
                continue
            # rotate only if file has content
            if os.path.getsize(src) > 0:
                dst = _dated_name(src, date)
                os.rename(src, dst)
                rotated.append(dst)
                logger.info("Rotated %s -> %s", src, dst)
                # create an empty placeholder so logging can continue
                open(src, 'a', encoding='utf-8').close()
            else:
                logger.debug("Skipping empty log file: %s", src)
        except Exception as ex:
            logger.warning("Failed rotating %s: %s", src, ex)

    # 2) Optionally rotate collate log (helpful to include in daily bundle)
    collate_log = 'cal_collate.log'
    if os.path.isfile(collate_log) and os.path.getsize(collate_log) > 0:
        try:
            dst = _dated_name(collate_log, date)
            os.rename(collate_log, dst)
            rotated.append(dst)
            logger.info("Rotated %s -> %s", collate_log, dst)
            open(collate_log, 'a', encoding='utf-8').close()
        except Exception as ex:
            logger.warning("Failed rotating %s: %s", collate_log, ex)

    # 3) Rotate omdb_not_found.txt (if present)
    omdb_src = 'omdb_not_found.txt'
    if os.path.isfile(omdb_src) and os.path.getsize(omdb_src) > 0:
        try:
            # append a small archive marker for traceability
            with open(omdb_src, 'a', encoding='utf-8') as f:
                f.write(f"\nArchived by rotate_and_zip_logs: {datetime.now().isoformat()}\n")

            omdb_dst = _dated_name('omdb_not_found.txt', date)
            os.rename(omdb_src, omdb_dst)
            rotated.append(omdb_dst)
            logger.info("Rotated %s -> %s", omdb_src, omdb_dst)
        except Exception as ex:
            logger.warning("Failed rotating %s: %s", omdb_src, ex)

    if not rotated:
        logger.info("No logs to rotate for %s", date)
        return None

    # 4) Zip all rotated files together: <YYYYMMDD>_logs.zip
    zip_name = f"{date}_logs.zip"
    try:
        with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for path in rotated:
                try:
                    zf.write(path, arcname=os.path.basename(path))
                except Exception as ex:
                    logger.warning("Failed to add %s to zip: %s", path, ex)
        logger.info("Created archive %s (contains %d files)", zip_name, len(rotated))

        # 5) Remove the rotated files now that they're archived
        for path in rotated:
            try:
                os.remove(path)
            except Exception as ex:
                logger.warning("Failed to remove rotated file %s: %s", path, ex)

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
