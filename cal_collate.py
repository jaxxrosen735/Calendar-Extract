"""
Calendar Collation Service
Combines multiple calendar .ics files into a single master calendar (toronto_screenings.ics)
Runs daily at 5 AM ET and monitors file modification times
"""

from scraper_utils import setup_logging, schedule_at_time
from ics import Calendar
import os
import glob
import logging as stdlib_logging
from datetime import datetime, timedelta
import time
import zipfile

# Configuration
OUTPUT_FILE = "toronto_screenings.ics"
LOG_FILE = "cal_collate.log"
ICS_PATTERN = "*.ics"  # Pattern to match calendar files
EXCLUDE_FILES = {"toronto_screenings.ics"}  # Files to exclude from combining

# Setup logging
logger = setup_logging(LOG_FILE)

def find_ics_files(pattern: str = ICS_PATTERN):
    """Find all .ics files matching the pattern.
    
    Args:
        pattern: Glob pattern to match files (default: '*.ics')
    
    Returns:
        List of .ics files, sorted by modification time (newest first)
    """
    files = [f for f in glob.glob(pattern) if os.path.isfile(f) and f not in EXCLUDE_FILES]
    
    # Sort by modification time (newest first)
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    
    return files

def get_file_info(filepath: str):
    """Get file information including size and modification time.
    
    Args:
        filepath: Path to the file
    
    Returns:
        dict with file info
    """
    try:
        stat = os.stat(filepath)
        mtime = datetime.fromtimestamp(stat.st_mtime)
        size = stat.st_size
        return {
            'path': filepath,
            'mtime': mtime,
            'size': size,
            'age_minutes': (datetime.now() - mtime).total_seconds() / 60
        }
    except Exception as ex:
        logger.error(f"Error getting file info for {filepath}: {ex}")
        return None

def combine_calendars(files: list):
    """Combine multiple calendar files into a single calendar.
    
    Args:
        files: List of .ics file paths to combine
    
    Returns:
        Combined Calendar object
    """
    master_cal = Calendar()
    total_events = 0
    
    for filepath in files:
        try:
            logger.info(f"Reading {filepath}...")
            with open(filepath, 'r', encoding='utf-8') as f:
                cal = Calendar(f.read())
                
            events = list(cal.events)
            logger.info(f"  {filepath} contains {len(events)} events")
            
            # Add events to master calendar
            for event in events:
                master_cal.events.add(event)
                total_events += 1
        
        except Exception as ex:
            logger.error(f"Error reading {filepath}: {ex}", exc_info=True)
            continue
    
    logger.info(f"Total events in combined calendar: {total_events}")
    return master_cal

def collate_all():
    """Main collation function."""
    logger.info("=" * 80)
    logger.info("STARTING CALENDAR COLLATION")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info("=" * 80)
    
    try:
        # Find all .ics files
        ics_files = find_ics_files()
        
        if not ics_files:
            logger.warning("No .ics files found to collate!")
            return
        
        logger.info(f"Found {len(ics_files)} .ics file(s) to process:")
        
        # Log file info
        for filepath in ics_files:
            info = get_file_info(filepath)
            if info:
                logger.info(
                    f"  - {filepath} "
                    f"({info['size']:,} bytes, "
                    f"modified {info['age_minutes']:.1f} min ago)"
                )
        
        # Combine calendars
        logger.info("=" * 80)
        logger.info("COMBINING CALENDARS")
        logger.info("=" * 80)
        
        master_cal = combine_calendars(ics_files)
        
        # Save combined calendar
        logger.info("=" * 80)
        logger.info(f"SAVING COMBINED CALENDAR: {OUTPUT_FILE}")
        logger.info("=" * 80)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.writelines(master_cal.serialize_iter())
        
        events_count = len(master_cal.events)
        logger.info(f"✓ Successfully saved {OUTPUT_FILE} with {events_count} events")
        
        # Log final file info
        final_info = get_file_info(OUTPUT_FILE)
        if final_info:
            logger.info(
                f"  Output file: {final_info['size']:,} bytes"
            )
    
    except Exception as ex:
        logger.error(f"Error during collation: {ex}", exc_info=True)
    
    logger.info("=" * 80)
    logger.info("COLLATION COMPLETE")
    logger.info("=" * 80)

    # Post-collation: archive `omdb_not_found.txt` so the next scraper batch starts fresh.
    try:
        omdb_file = 'omdb_not_found.txt'
        if os.path.exists(omdb_file) and os.path.getsize(omdb_file) > 0:
            # Append archive timestamp to the text file for traceability
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(omdb_file, 'a', encoding='utf-8') as f:
                f.write(f"\nArchived by cal_collate: {ts}\n")

            # Create a time-stamped zip archive and include the txt file inside it
            zip_name = f"omdb_not_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(omdb_file, arcname=os.path.basename(omdb_file))

            logger.info(f"Archived and compressed '{omdb_file}' → '{zip_name}'")

            # Remove the original so scrapers will generate a fresh `omdb_not_found.txt` next run
            try:
                os.remove(omdb_file)
                logger.info(f"Removed original '{omdb_file}' to allow fresh generation on next scraper run")
            except Exception as rm_ex:
                logger.warning(f"Could not remove '{omdb_file}': {rm_ex}")
        else:
            logger.info("No omdb_not_found.txt to archive (missing or empty)")
    except Exception as ex:
        logger.error(f"Failed to archive omdb_not_found.txt: {ex}", exc_info=True)


def schedule_collation():
    """Schedule the collation to run daily at 5 AM ET."""
    logger.info("Initializing scheduler for calendar collation...")
    scheduler = schedule_at_time(
        collate_all,
        job_id='collate_calendars',
        job_name='Calendar Collation Service',
        hour=5,
        minute=0
    )
    return scheduler

if __name__ == "__main__":
    logger.info("Calendar Collation Service Starting")
    
    # Run once immediately
    logger.info("Running initial collation...")
    collate_all()
    
    # Schedule for daily runs at 5 AM
    logger.info("\nStarting scheduled collation service...")
    scheduler = schedule_collation()
    
    try:
        logger.info("Collation service is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler stopped")
