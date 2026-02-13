"""
Central scheduler for scrapers and collation.
Moves scheduling responsibility out of individual scraper modules.

- Schedules `revue.scrape_all`, `tiff.scrape_all`, and `fox.scrape_all` using `schedule_daily`
  (random time between 23:00 and 04:00 ET by default)
- Schedules `cal_collate.collate_all` at 05:00 ET using `schedule_at_time`

Run this module to start all background schedulers:
    python3 scheduling.py

Or import `start()` and call programmatically from another long-running service.
"""

import time
import logging
from scraper_utils import schedule_daily, schedule_at_time

# Import scraper entry points (functions should perform a single run)
from revue import scrape_all as revue_scrape
from tiff import scrape_all as tiff_scrape
from fox import scrape_all as fox_scrape
from cal_collate import collate_all as collate_all

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def start():
    """Start all scheduled jobs and return scheduler handles (list)."""
    schedulers = []

    logger.info("Scheduling Revue scraper (daily window: 23:00-04:00 ET)")
    schedulers.append(
        schedule_daily(
            revue_scrape,
            job_id='revue_scraper',
            job_name='Revue Cinema Calendar Scraper',
            min_hour=23,
            max_hour=4
        )
    )

    logger.info("Scheduling TIFF scraper (daily window: 23:00-04:00 ET)")
    schedulers.append(
        schedule_daily(
            tiff_scrape,
            job_id='tiff_scraper',
            job_name='TIFF Calendar Scraper',
            min_hour=23,
            max_hour=4
        )
    )

    logger.info("Scheduling Fox scraper (daily window: 23:00-04:00 ET)")
    schedulers.append(
        schedule_daily(
            fox_scrape,
            job_id='fox_scraper',
            job_name='Fox Theatre Calendar Scraper',
            min_hour=23,
            max_hour=4
        )
    )

    logger.info("Scheduling calendar collation (daily at 05:00 ET)")
    schedulers.append(
        schedule_at_time(
            collate_all,
            job_id='collate_calendars',
            job_name='Calendar Collation Service',
            hour=5,
            minute=0
        )
    )

    return schedulers


if __name__ == '__main__':
    logger.info('Starting centralized scheduling service...')
    scheds = start()
    try:
        logger.info('Schedulers started — running until interrupted (Ctrl+C)')
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Shutting down all schedulers...')
        for s in scheds:
            try:
                s.shutdown()
            except Exception:
                pass
        logger.info('Schedulers stopped')
