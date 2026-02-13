"""
Revue Cinema Calendar Scraper
Scrapes the Revue Cinema scheduling calendar and generates revue.ics
Integrates with OMDb API to get runtimes for accurate end times
"""

from scraper_utils import setup_logging, launch_browser, find_next_button, schedule_daily, log_omdb_not_found
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import json
import time
import requests
import re
import os

# Configuration
BASE_URL = "https://prod3.agileticketing.net/websales/pages/entrypoint.aspx?GUID=9416d3bf-ad16-479c-9d40-f0abda7cb4e9&"
OUTPUT_FILE = "revue.ics"
PAGES_TO_SCRAPE = 3 
LOG_FILE = "revue_scraper.log"
DEBUG_OMDB_FILE = "debug_omdb.json"
import os
import difflib
from dotenv import load_dotenv

# Load dotenv from api.env (if present) so users can keep secrets in a file
load_dotenv(dotenv_path='api.env')

OMDB_API_URL = "https://www.omdbapi.com/"
# Prefer explicit OMDB_API_KEY, fall back to generic API_KEY for backward compatibility
OMDB_API_KEY = os.environ.get("OMDB_API_KEY") or os.environ.get("API_KEY")
if not OMDB_API_KEY:
    raise RuntimeError("OMDB API key not found. Add OMDB_API_KEY (or API_KEY) to api.env or the environment.")

# Setup logging
logger = setup_logging(LOG_FILE)

# Cache for OMDb API calls
omdb_cache = {}
not_found_titles = set()

def log_omdb_debug(title, cleaned_title, response_data):
    """Appends raw OMDb API response to a debug file."""
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

def clean_event_title(raw_title):
    """
    Extracts the movie title from the Revue Event string.
    Regex logic: Captures uppercase letters (including accents), numbers, and spaces.
    Stops as soon as it hits a lowercase letter or special character.
    """
    # Remove prefix
    text = re.sub(r'^Revue Event:\s*', '', raw_title, flags=re.IGNORECASE)
    
    # Range \u00C0-\u00DE covers capital accented letters like É, À, Ö, etc.
    pattern = r'([A-Z0-9\u00C0-\u00DE][A-Z0-9\u00C0-\u00DE\s]+?)(?=[^A-Z0-9\u00C0-\u00DE\s]|$)'
    match = re.search(pattern, text)
    
    if match:
        cleaned = match.group(1).strip()
        if len(cleaned) > 1:
            logger.debug(f"Regex Cleaned (with accents): '{raw_title}' -> '{cleaned}'")
            return cleaned
    
    return raw_title

def get_movie_runtime(raw_title):
    """Fetch runtime from OMDb API with a fuzzy-search fallback and log responses."""
    cleaned_title = clean_event_title(raw_title)

    if cleaned_title in omdb_cache:
        return omdb_cache[cleaned_title]

    # 1) Try exact title lookup
    try:
        params = {'apikey': OMDB_API_KEY, 't': cleaned_title, 'type': 'movie'}
        response = requests.get(OMDB_API_URL, params=params, timeout=5)
        data = response.json()
        log_omdb_debug(raw_title, cleaned_title, data)

        if data.get('Response') == 'True' and data.get('Runtime') not in (None, 'N/A'):
            runtime_str = ''.join(filter(str.isdigit, data['Runtime']))
            runtime_minutes = int(runtime_str)
            omdb_cache[cleaned_title] = runtime_minutes
            return runtime_minutes

        # 2) Fuzzy-search fallback: use the OMDb `s=` search endpoint and pick best match
        search_params = {'apikey': OMDB_API_KEY, 's': cleaned_title, 'type': 'movie'}
        search_resp = requests.get(OMDB_API_URL, params=search_params, timeout=5)
        search_data = search_resp.json()

        if search_data.get('Response') == 'True' and 'Search' in search_data:
            candidates = [c.get('Title', '') for c in search_data.get('Search', [])]
            best = difflib.get_close_matches(cleaned_title, candidates, n=1, cutoff=0.6)
            if best:
                # fetch by exact title returned by search to get runtime
                params = {'apikey': OMDB_API_KEY, 't': best[0], 'type': 'movie'}
                candidate_resp = requests.get(OMDB_API_URL, params=params, timeout=5)
                candidate_data = candidate_resp.json()
                log_omdb_debug(raw_title, best[0], candidate_data)
                if candidate_data.get('Response') == 'True' and candidate_data.get('Runtime') not in (None, 'N/A'):
                    runtime_minutes = int(''.join(filter(str.isdigit, candidate_data['Runtime'])))
                    omdb_cache[cleaned_title] = runtime_minutes
                    return runtime_minutes

    except Exception as ex:
        logger.debug(f"Error fetching from OMDb for '{cleaned_title}': {ex}")

    omdb_cache[cleaned_title] = None
    not_found_titles.add(raw_title)
    return None


def save_not_found_titles():
    """Append Revue titles not found in OMDb to `omdb_not_found.txt` with source tag."""
    if not_found_titles:
        for title in sorted(not_found_titles):
            try:
                log_omdb_not_found(title, 'revue.py')
            except Exception:
                with open('omdb_not_found.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - revue.py - Not Found: {title}\n")

def parse_page(soup, calendar_obj):
    """Parses events and sets DTEND based on OMDb runtime + 15 mins."""
    event_count = 0
    json_scripts = soup.find_all('script', {'type': 'application/ld+json'})
    
    for script in json_scripts:
        try:
            data = json.loads(script.string)
            events = data if isinstance(data, list) else [data]
            
            for event_data in events:
                if event_data.get('@type') != 'Event':
                    continue
                
                event_name = event_data.get('name', 'Unknown Event')
                start_date_str = event_data.get('startDate', '')
                dt_start = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                
                runtime_minutes = get_movie_runtime(event_name)
                
                # Default to 120 minutes if not found (2 hours)
                base_runtime = runtime_minutes if runtime_minutes is not None else 120
                
                e = Event()
                e.name = event_name
                e.begin = dt_start
                e._duration = None 
                e.end = dt_start + timedelta(minutes=base_runtime + 15)
                
                location = event_data.get('location', {})
                if location:
                    # Prefer a concise, Google-recognizable address for Revue Cinema
                    loc_name = (location.get('name') if isinstance(location, dict) else str(location)) or ''
                    if 'revue' in loc_name.lower() or 'revue' in event_name.lower():
                        # Prefix with venue name so Google Calendar shows a clear location card
                        e.location = "Revue Cinema, 400 Roncesvalles Ave, Toronto, ON"
                    else:
                        # Use provided name/address when available
                        if isinstance(location, dict):
                            e.location = location.get('name', '') or location.get('address', '') or loc_name
                        else:
                            e.location = loc_name
                
                calendar_obj.events.add(e)
                event_count += 1
                
        except Exception as ex:
            logger.error(f"Error parsing event: {ex}")
            continue
            
    return event_count

def scrape_all():
    """Main scraping function."""
    logger.info("=" * 80)
    logger.info("STARTING REVUE CINEMA CALENDAR SCRAPE")
    
    p = None
    browser = None
    try:
        p, browser, page = launch_browser(headless=True)
        full_cal = Calendar()
        total_events = 0
        
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        
        for i in range(PAGES_TO_SCRAPE):
            soup = BeautifulSoup(page.content(), 'html.parser')
            added = parse_page(soup, full_cal)
            total_events += added
            
            if i < PAGES_TO_SCRAPE - 1:
                next_button = find_next_button(page)
                if next_button:
                    next_button.click()
                    page.wait_for_timeout(2000)
                else:
                    break
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.writelines(full_cal.serialize_iter())
        
        # Save any OMDb misses for manual review (tagged by source)
        try:
            save_not_found_titles()
        except Exception as ex:
            logger.debug(f"Failed to save not-found titles: {ex}")

        logger.info(f"SCRAPE COMPLETE: Found {total_events} events.")
        
    except Exception as ex:
        logger.error(f"Critical error: {ex}")
    finally:
        if browser: browser.close()
        if p: p.stop()

def schedule_scrape():
    """Schedule the scraper to run daily at a random time between 11 PM and 4 AM ET."""
    logger.info("Initializing scheduler for Revue scraper...")
    scheduler = schedule_daily(
        scrape_all,
        job_id='revue_scraper',
        job_name='Revue Cinema Calendar Scraper',
        min_hour=23,
        max_hour=4
    )
    return scheduler

if __name__ == "__main__":
    logger.info("Revue Cinema Calendar Scraper Starting")
    
    # Run once immediately
    logger.info("Running initial scrape...")
    scrape_all()
    
    # Schedule for daily runs
    logger.info("\nStarting scheduled scraper...")
    scheduler = schedule_scrape()
    
    try:
        logger.info("Scraper is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler stopped")