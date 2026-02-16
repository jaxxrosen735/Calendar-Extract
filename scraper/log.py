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
    # We add a timestamp to the archived filename to prevent collisions if run multiple times/day
    timestamp = datetime.now().strftime('%H%M%S')
    
    files_to_zip = []
    
    for src, dated_name in files_to_archive:
        # dated_name is like "20260216_fox_scraper.log"
        # We want to insert time: "20260216_143000_fox_scraper.log"
        base, ext = os.path.splitext(dated_name)
        # reconstruction: base already has date like "20260216_fox_scraper"
        # Let's just append time to it.
        # However, _dated_name format is {base}_{date}{ext} -> fox_scraper_20260216.log
        # Let's inspect how _dated_name was constructed in lines 49, 52, 61.
        # It was just f"{date}_{src}". So "20260216_fox_scraper.log".
        # We will inject time after date.
        
        archived_filename = f"{date}_{timestamp}_{src}"
        
        try:
            # We don't need to copy to a temp file on disk if we just write to zip directly.
            # But the original logic copied to `dated_name` (temp file) then zipped that.
            # This might be to release the handle on the original file? 
            # Original logic: 
            #   copy src -> dst (timestamped)
            #   zip dst
            #   remove dst
            #   truncate src
            
            # Let's keep the pattern of creating a temp file to ensure we captured the content
            # before we truncate the original.
            
            with open(src, 'rb') as fsrc, open(archived_filename, 'wb') as fdst:
                fdst.write(fsrc.read())
            logger.info("Copied %s -> %s", src, archived_filename)
            files_to_zip.append(archived_filename)
            
        except Exception as ex:
            logger.warning("Failed copying %s to %s: %s", src, archived_filename, ex)

    if not files_to_zip:
        return None

    # 2) Zip all new files together: <YYYYMMDD>_logs.zip
    zip_name = f"{date}_logs.zip"
    try:
        # Use 'a' to append if exists, otherwise create.
        with zipfile.ZipFile(zip_name, 'a', compression=zipfile.ZIP_DEFLATED) as zf:
            for dst in files_to_zip:
                try:
                    zf.write(dst, arcname=dst)
                except Exception as ex:
                    logger.warning("Failed to add %s to zip: %s", dst, ex)
        logger.info("Updated archive %s (added %d files)", zip_name, len(files_to_zip))

        # 3) Remove the new temp files
        for dst in files_to_zip:
            try:
                os.remove(dst)
            except Exception as ex:
                logger.warning("Failed to remove temp file %s: %s", dst, ex)

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
                logger.debug("Cleared log file: %s", fname)
            except Exception as ex:
                logger.warning("Failed to clear log file %s: %s", fname, ex)
        return zip_name

    except Exception as ex:
        logger.error("Failed to update zip %s: %s", zip_name, ex, exc_info=True)
        return None


if __name__ == '__main__':
    zipfile_path = rotate_and_zip_logs()
    if zipfile_path:
        logger.info("Rotation complete — archive: %s", zipfile_path)
    else:
        logger.info("Rotation complete — no archive created.")
