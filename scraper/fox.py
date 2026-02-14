"""
Fox Theatre Calendar Scraper
Scrapes foxtheatre.ca/whats-on/now-showing/ for event listings and generates fox.ics
"""

from scraper_utils import setup_logging, launch_browser, schedule_daily, log_omdb_not_found, sort_events_by_start
import argparse
import sys
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import pytz
import requests
import json
import re
import time
import os
import difflib

# Configuration
BASE_URL = "https://www.foxtheatre.ca/whats-on/now-showing/"
OUTPUT_FILE = "fox.ics"
LOG_FILE = "fox_scraper.log"
DEBUG_OMDB_FILE = "debug_omdb.json"
from dotenv import load_dotenv

# Load dotenv from api.env to read OMDb key
load_dotenv(dotenv_path='api.env')
OMDB_API_URL = "https://www.omdbapi.com/"
OMDB_API_KEY = os.environ.get("OMDB_API_KEY") or os.environ.get("API_KEY")
if not OMDB_API_KEY:
    raise RuntimeError("OMDB API key not found. Add OMDB_API_KEY (or API_KEY) to api.env or the environment.")
FOX_LOCATION = "Fox Theatre, 2236 Queen St E, Toronto, ON M4E 1G2, Canada"
LOCAL_TZ = pytz.timezone("America/Toronto")

# Setup logging
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', encoding='utf-8'):
        pass
logger = setup_logging(LOG_FILE)

# Debug flag
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--debug', action='store_true', help='Enable OMDb debug logging')
args, unknown = parser.parse_known_args()
DEBUG_OMDB = args.debug

def log_omdb_debug(title, cleaned_title, response_data):
    if not DEBUG_OMDB:
        return
    debug_entry = {
        "timestamp": datetime.now().isoformat(),
        "original_title": title,
        "cleaned_title": cleaned_title,
        "response": response_data
    }
    try:
        with open(DEBUG_OMDB_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(debug_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to {DEBUG_OMDB_FILE}: {e}")

def get_movie_duration_minutes(title):
    """
    Fetches runtime from OMDb with a fuzzy-search fallback and adds 15 minutes for previews.
    Returns: integer minutes (includes the 15-minute previews) or 120 (fallback).
    """
    url = OMDB_API_URL
    search_title = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()

    try:
        # Exact lookup
        response = requests.get(url, params={"apikey": OMDB_API_KEY, "t": search_title}, timeout=5)
        data = response.json()
        log_omdb_debug(title, search_title, data)
        if data.get("Response") == "True" and data.get("Runtime") != "N/A":
            runtime_mins = int(''.join(filter(str.isdigit, data.get("Runtime"))))
            return runtime_mins + 15

        # Fuzzy-search fallback using `s=` search
        search_resp = requests.get(url, params={"apikey": OMDB_API_KEY, "s": search_title, "type": "movie"}, timeout=5)
        search_data = search_resp.json()
        if search_data.get('Response') == 'True' and 'Search' in search_data:
            candidates = [c.get('Title', '') for c in search_data.get('Search', [])]
            best = difflib.get_close_matches(search_title, candidates, n=1, cutoff=0.6)
            if best:
                cand_resp = requests.get(url, params={"apikey": OMDB_API_KEY, "t": best[0], "type": "movie"}, timeout=5)
                cand = cand_resp.json()
                log_omdb_debug(title, best[0], cand)
                if cand.get('Response') == 'True' and cand.get('Runtime') not in (None, 'N/A'):
                    runtime_mins = int(''.join(filter(str.isdigit, cand.get('Runtime'))))
                    return runtime_mins + 15

    except Exception as e:
        logger.debug(f"OMDb API Error for {title}: {e}")

    # Log lookup failures (include source)
    try:
        log_omdb_not_found(title, 'fox.py')
    except Exception:
        pass
    return 120 # 2 hour fallback

def parse_page(soup, calendar_obj):
    """Parses events and explicitly sets DTEND."""
    event_count = 0
    day_cells = soup.find_all(attrs={"data-date": True})
    logger.info(f"Scanning {len(day_cells)} potential calendar cells.")

    for cell in day_cells:
        date_val = cell.get('data-date') 
        if not date_val:
            continue
            
        try:
            base_date = datetime.strptime(date_val, '%Y-%m-%d')
        except ValueError:
            continue

        event_links = cell.find_all('a', class_=lambda x: x and 'fc-event' in x)
        
        for link in event_links:
            try:
                time_elem = link.find(class_='fc-event-time')
                title_elem = link.find(class_='fc-event-title')
                
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                time_str = time_elem.get_text(strip=True) if time_elem else "00:00"

                # Parse the time string
                hr, mn = 0, 0
                time_match = re.search(r'(\d+)(?::(\d+))?\s*([ap]m|[ap])?', time_str.lower())
                
                if time_match:
                    hr = int(time_match.group(1))
                    mn = int(time_match.group(2)) if time_match.group(2) else 0
                    ampm = time_match.group(3)
                    
                    if ampm and ('p' in ampm) and hr < 12: hr += 12
                    if ampm and ('a' in ampm) and hr == 12: hr = 0

                # Combine into an Eastern-aware datetime for DTSTART
                naive_start = base_date.replace(hour=hr, minute=mn, second=0, microsecond=0)
                event_start = LOCAL_TZ.localize(naive_start)

                # Initialize ICS Event
                e = Event()
                e.name = title
                e.begin = event_start
                e.location = FOX_LOCATION
                
                # --- EXPLICIT DTEND CALCULATION ---
                duration_mins = get_movie_duration_minutes(title)
                # Setting e.end explicitly forces the library to write DTEND instead of DURATION
                e.end = event_start + timedelta(minutes=duration_mins)
                
                calendar_obj.events.add(e)
                event_count += 1
                logger.debug(f"Added: {title} | Start: {e.begin} | End: {e.end}")

            except Exception as e:
                logger.error(f"Error parsing event in cell {date_val}: {e}")
                
    return event_count

def scrape_all():
    """Main scraping function for Fox Theatre."""
    logger.info("=" * 80)
    logger.info("STARTING FOX THEATRE CALENDAR SCRAPE")
    
    p = None
    browser = None
    try:
        p, browser, page = launch_browser(headless=True)
        full_cal = Calendar()
        
        logger.info(f"Loading {BASE_URL}")
        page.goto(BASE_URL)
        page.wait_for_timeout(3000) 
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        total_events = parse_page(soup, full_cal)
        # Sort events by start time before writing ICS
        sorted_events = sort_events_by_start(list(full_cal.events))
        full_cal.events = set(sorted_events)
        if total_events > 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.writelines(full_cal.serialize_iter())
            logger.info(f"SUCCESS: Saved {total_events} events to {OUTPUT_FILE}")
        else:
            logger.warning("No events found.")
        
    except Exception as ex:
        logger.error(f"Critical error: {ex}", exc_info=True)
    finally:
        if browser: browser.close()
        if p: p.stop()

def schedule_scrape():
    """Schedule the Fox Theatre scraper to run daily at a random time between 11 PM and 4 AM ET."""
    logger.info("Initializing scheduler for Fox Theatre scraper...")
    scheduler = schedule_daily(
        scrape_all,
        job_id='fox_scraper',
        job_name='Fox Theatre Calendar Scraper',
        min_hour=23,
        max_hour=4
    )
    return scheduler


if __name__ == "__main__":
    # Default behaviour: one-off run (cron-friendly). Use --schedule to run background scheduler.
    if '--schedule' in sys.argv or '-s' in sys.argv:
        logger.info("Fox Theatre Calendar Scraper Starting (scheduled mode)")
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
        logger.info("Fox Theatre Calendar Scraper Starting — one-off run")
        scrape_all()