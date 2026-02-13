"""
Shared utilities for calendar scrapers
Extracted common functions to be used by revue.py, tiff.py, and other scrapers
"""

import logging
import random
import pytz
from datetime import datetime
from playwright.sync_api import sync_playwright
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def setup_logging(log_filename: str) -> logging.Logger:
    """Configure logging for a scraper.
    
    Args:
        log_filename: Name of the log file (e.g., 'revue_scraper.log')
    
    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def launch_browser(headless: bool = True):
    """Launch a Playwright browser with proper anonymization.
    
    Args:
        headless: Whether to run in headless mode (default True)
    
    Returns:
        tuple: (playwright instance, browser, page)
    """
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    page = browser.new_page(
        user_agent=USER_AGENT,
        extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'}
    )
    return p, browser, page

def find_next_button(page, selectors: list = None):
    """Find the Next button with multiple fallback selectors.
    
    Args:
        page: Playwright page object
        selectors: List of selectors to try (uses defaults if None)
    
    Returns:
        Button element if found, None otherwise
    """
    if selectors is None:
        selectors = [
            "a#ctl00_MainContent_NextLink",
            "a[id*='NextLink']",
            "a:has-text('Next')",
            "a[onclick*='NextLink']",
        ]
    
    logger = logging.getLogger(__name__)
    
    for selector in selectors:
        try:
            logger.debug(f"Trying selector: {selector}")
            next_button = page.query_selector(selector)
            if next_button:
                logger.info(f"Found Next button with selector: {selector}")
                return next_button
        except Exception as ex:
            logger.debug(f"Selector '{selector}' failed: {ex}")
            continue
    
    logger.warning("Could not find Next button with any selector")
    return None

def schedule_daily(
    scrape_function,
    job_id: str,
    job_name: str,
    min_hour: int = 23,
    max_hour: int = 4
):
    """Schedule a scraper function to run daily at a random time within a time window.
    
    Args:
        scrape_function: The function to execute
        job_id: Unique job ID (e.g., 'revue_scraper')
        job_name: Human-readable job name
        min_hour: Start hour (e.g., 23 for 11 PM)
        max_hour: End hour (e.g., 4 for 4 AM, wraps around midnight)
    
    Returns:
        BackgroundScheduler instance
    """
    logger = logging.getLogger(__name__)
    scheduler = BackgroundScheduler(daemon=True)
    eastern = pytz.timezone('US/Eastern')
    
    # Generate random hour and minute
    if min_hour > max_hour:  # Wraps around midnight (e.g., 23 to 4)
        random_hour = random.choice(list(range(min_hour, 24)) + list(range(0, max_hour)))
    else:
        random_hour = random.randint(min_hour, max_hour)
    
    random_minute = random.randint(0, 59)
    
    logger.info(f"Scheduled {job_name} to run daily at {random_hour:02d}:{random_minute:02d} Eastern Time")
    
    trigger = CronTrigger(
        hour=random_hour,
        minute=random_minute,
        timezone=eastern
    )
    
    scheduler.add_job(
        scrape_function,
        trigger,
        id=job_id,
        name=job_name,
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started for {job_name}")
    
    return scheduler

def schedule_at_time(
    collate_function,
    job_id: str,
    job_name: str,
    hour: int = 5,
    minute: int = 0
):
    """Schedule a function to run daily at a specific time.
    
    Args:
        collate_function: The function to execute
        job_id: Unique job ID (e.g., 'collate_calendars')
        job_name: Human-readable job name
        hour: Hour to run (0-23, default 5 for 5 AM)
        minute: Minute to run (0-59, default 0)
    
    Returns:
        BackgroundScheduler instance
    """
    logger = logging.getLogger(__name__)
    scheduler = BackgroundScheduler(daemon=True)
    eastern = pytz.timezone('US/Eastern')
    
    logger.info(f"Scheduled {job_name} to run daily at {hour:02d}:{minute:02d} Eastern Time")
    
    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=eastern
    )
    
    scheduler.add_job(
        collate_function,
        trigger,
        id=job_id,
        name=job_name,
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started for {job_name}")
    
    return scheduler
