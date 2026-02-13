"""
TIFF (Toronto International Film Festival) Calendar Scraper
Scrapes tiff.net/calendar for event listings and generates tiff.ics
Integrates with OMDb API to get runtimes for accurate end times
"""

from scraper_utils import setup_logging, launch_browser, schedule_daily, log_omdb_not_found
import sys
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import json
import time
import re
import logging as stdlib_logging
import requests
import os
import difflib

# Configuration
BASE_URL = "https://www.tiff.net/calendar"
OUTPUT_FILE = "tiff.ics"
LOG_FILE = "tiff_scraper.log"
from dotenv import load_dotenv

# Load dotenv from api.env to read OMDb key
load_dotenv(dotenv_path='api.env')
OMDB_API_URL = "https://www.omdbapi.com/"
OMDB_API_KEY = os.environ.get("OMDB_API_KEY") or os.environ.get("API_KEY")
if not OMDB_API_KEY:
    raise RuntimeError("OMDB API key not found. Add OMDB_API_KEY (or API_KEY) to api.env or the environment.")
# Updated for optimal Google Maps recognition
TIFF_LOCATION = "TIFF Lightbox, 350 King St W, Toronto, ON M5V 3X5, Canada"
LOCAL_TZ = pytz.timezone("America/Toronto")

# Setup logging
logger = setup_logging(LOG_FILE)

# Cache for OMDb API calls to avoid repeated requests (limited to 1000/day)
omdb_cache = {}
not_found_titles = set()

def get_movie_runtime(title):
    """Fetch runtime from OMDb API with a fuzzy-search fallback."""
    if title in omdb_cache:
        return omdb_cache[title]

    try:
        logger.debug(f"OMDb lookup for: {title}")
        params = {'apikey': OMDB_API_KEY, 't': title, 'type': 'movie'}
        response = requests.get(OMDB_API_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('Response') == 'True' and 'Runtime' in data and data['Runtime'] != 'N/A':
            runtime_str = ''.join(filter(str.isdigit, data['Runtime']))
            runtime_minutes = int(runtime_str)
            omdb_cache[title] = runtime_minutes
            return runtime_minutes

        # Fuzzy-search fallback using `s=` search
        search_params = {'apikey': OMDB_API_KEY, 's': title, 'type': 'movie'}
        search_resp = requests.get(OMDB_API_URL, params=search_params, timeout=5)
        search_data = search_resp.json()
        if search_data.get('Response') == 'True' and 'Search' in search_data:
            candidates = [c.get('Title', '') for c in search_data.get('Search', [])]
            best = difflib.get_close_matches(title, candidates, n=1, cutoff=0.6)
            if best:
                params = {'apikey': OMDB_API_KEY, 't': best[0], 'type': 'movie'}
                candidate_resp = requests.get(OMDB_API_URL, params=params, timeout=5)
                cand = candidate_resp.json()
                if cand.get('Response') == 'True' and cand.get('Runtime') not in (None, 'N/A'):
                    runtime_minutes = int(''.join(filter(str.isdigit, cand['Runtime'])))
                    omdb_cache[title] = runtime_minutes
                    return runtime_minutes

        omdb_cache[title] = None
        not_found_titles.add(title)
        return None
    except Exception as ex:
        logger.debug(f"OMDb Error: {ex}")
        omdb_cache[title] = None
        not_found_titles.add(title)
        return None

def clean_title(title_text):
    """Clean movie title by removing extra whitespace and normalizing."""
    title = title_text.strip()
    title = re.sub(r'\s+', ' ', title)
    return title

def parse_page(soup, calendar_obj):
    """Parses event data from TIFF.net calendar page with proper timezone handling."""
    event_count = 0
    
    try:
        calendar_items = soup.find_all('div', class_='calendar-list-item')
        
        for container in calendar_items:
            # Extract date from h2 header
            date_header = container.find('h2', class_=lambda x: x and 'style__date' in (x or ''))
            if not date_header: continue
            
            date_text = date_header.get_text(strip=True)
            match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', date_text)
            if not match: continue
            
            date_str = f"{match.group(1)} {match.group(2)} 2026"
            event_date = datetime.strptime(date_str, "%b %d %Y").date()
            
            event_items = container.find_all('li')
            for event_item in event_items:
                try:
                    title_elem = event_item.find('h3', class_=lambda x: x and 'style__cardTitle' in (x or ''))
                    if not title_elem: continue
                    
                    title = clean_title(title_elem.get_text(strip=True))
                    
                    # Extract time
                    time_text = None
                    screening_button = event_item.find(class_=lambda x: x and 'style__screeningButton' in (x or ''))
                    if screening_button:
                        time_span = screening_button.find('span')
                        if time_span:
                            time_text = time_span.get_text(strip=True)
                    
                    if not time_text:
                        spans = event_item.find_all('span')
                        for span in spans:
                            span_text = span.get_text(strip=True)
                            if re.match(r'\d{1,2}:\d{2}(am|pm)?', span_text, re.IGNORECASE):
                                time_text = span_text
                                break
                    
                    if not time_text: continue

                    # Combine date and time, then localize to Eastern
                    try:
                        time_text_clean = time_text.replace(' ', '').lower()
                        time_obj = datetime.strptime(time_text_clean, "%I:%M%p").time()
                        naive_start = datetime.combine(event_date, time_obj)
                        # Localize to Toronto Time
                        start_datetime = LOCAL_TZ.localize(naive_start)
                    except Exception: continue
                    
                    # Get runtime and calculate end
                    runtime_minutes = get_movie_runtime(title)
                    actual_duration = runtime_minutes if runtime_minutes else 120
                    end_datetime = start_datetime + timedelta(minutes=actual_duration + 15)
                    
                    # Create event
                    e = Event()
                    e.name = title[:100]
                    e.begin = start_datetime
                    # Force DTEND instead of DURATION
                    e._duration = None
                    e.end = end_datetime
                    e.location = TIFF_LOCATION
                    
                    calendar_obj.events.add(e)
                    event_count += 1
                    
                except Exception as ex:
                    logger.debug(f"Error processing event item: {ex}")
                    continue
            
    except Exception as ex:
        logger.error(f"Error in parse_page: {ex}", exc_info=True)
    
    return event_count

def save_not_found_titles():
    """Save titles not found in OMDb to `omdb_not_found.txt`, tagging the source."""
    if not_found_titles:
        for title in sorted(not_found_titles):
            try:
                log_omdb_not_found(title, 'tiff.py')
            except Exception:
                # Fallback: append plainly if the helper fails
                with open('omdb_not_found.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - tiff.py - Not Found: {title}\n")

def scrape_all():
    """Main scraping function for TIFF.net calendar."""
    logger.info("=" * 80)
    logger.info("STARTING TIFF CALENDAR SCRAPE")
    
    p = None
    browser = None
    
    try:
        p, browser, page = launch_browser(headless=True)
        full_cal = Calendar()
        
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        
        # Scroll to load infinite content
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        total_events = parse_page(soup, full_cal)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.writelines(full_cal.serialize_iter())
        
        save_not_found_titles()
        logger.info(f"✓ Successfully saved {OUTPUT_FILE} with {total_events} events")
        
    except Exception as ex:
        logger.error(f"Error during scraping: {ex}", exc_info=True)
    finally:
        if browser: browser.close()
        if p: p.stop()

def schedule_scrape():
    """Schedule the TIFF scraper to run daily at a random time between 11 PM and 4 AM ET."""
    logger.info("Initializing scheduler for TIFF scraper...")
    scheduler = schedule_daily(
        scrape_all,
        job_id='tiff_scraper',
        job_name='TIFF Calendar Scraper',
        min_hour=23,
        max_hour=4
    )
    return scheduler


if __name__ == "__main__":
    # Default behaviour: one-off run (cron-friendly). Use --schedule to run background scheduler.
    if '--schedule' in sys.argv or '-s' in sys.argv:
        logger.info("TIFF Calendar Scraper Starting (scheduled mode)")
        scheduler = schedule_scrape()
        try:
            logger.info("Scheduler running — press Ctrl+C to stop")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler stopped")
    else:
        logger.info("TIFF Calendar Scraper Starting — one-off run")
        scrape_all()