# Toronto Screenings Calendar Aggregator - Quick Start

A modular calendar scraping system that aggregates film festivals and cinema schedules from multiple sources into a single unified calendar.

**Current Sources:**
- **Revue Cinema** → `revue.ics` (200+ events) — now uses OMDb for runtimes
- **TIFF (Toronto International Film Festival)** → `tiff.ics` — includes `location` and OMDb runtime/end-time calculation
- **Fox Theatre** → `fox.ics` — new scraper, includes `location` and OMDb runtime/end-time calculation
- **Combined Calendar** → `toronto_screenings.ics` (all events merged)

## Features

✅ **Modular Architecture** - Shared utilities allow adding new scraper sources easily  
✅ **Anonymous & Headless** - Playwright browser automation with standard user-agents  
✅ **Automatic Scheduling** - Random daily runs at off-peak hours (11 PM - 4 AM ET)  
✅ **Collation Service** - Combines all calendars into single master calendar at 5 AM ET  
✅ **Accurate Durations** - OMDb runtime lookups (requires `OMDB_API_KEY` environment variable) are used to compute event end times (start + 15 min previews + runtime). TIFF & Fox also include `location` fields. A fuzzy-title fallback reduces OMDb misses.  
✅ **Robustness** - Multiple selector fallbacks for HTML elements  
✅ **Verbose Logging** - Detailed logs for each scraper and service; `omdb_not_found.txt` collects titles OMDb couldn't match  
✅ **Production-Ready** - Designed for server deployment with systemd/Docker  

## Installation (5 minutes)

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add OMDb API key (using `api.env`)
# Create a file named `api.env` at project root containing:
# OMDB_API_KEY="your_omdb_api_key_here"
# (the scrapers load `api.env` automatically via python-dotenv)

# 4. Install Playwright browsers
python -m playwright install chromium
```

## Usage

### Run individual scrapers

```bash
# Revue Cinema (once immediately}
python -c "from revue import scrape_all; scrape_all()"

# TIFF (once immediately)
python -c "from tiff import scrape_all; scrape_all()"

# Collate calendars (once immediately)
python -c "from cal_collate import collate_all; collate_all()"
```

### Run with automatic daily scheduling

```bash
# Run all services with scheduling
python revue.py &          # Runs at random time 11 PM - 4 AM
python tiff.py &           # Runs at random time 11 PM - 4 AM  
python cal_collate.py &    # Runs at 5 AM ET daily
```

This will:
- Run each scraper immediately
- Start background schedulers for daily runs at configured times
- Update respective .ics files
- Combine all calendars into `toronto_screenings.ics`
- Press Ctrl+C to stop any service

## Output Files

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `revue.ics` | Revue Cinema events | Daily (random time 11 PM - 4 AM) |
| `tiff.ics` | TIFF events (includes `location` + OMDb-based end times) | Daily (random time 11 PM - 4 AM) |
| `toronto_screenings.ics` | Combined all sources (revue + tiff + fox) | Daily at 5 AM ET |
| `revue_scraper.log` | Revue scraper logs | Continuous |
| `fox_scraper.log` | Fox Theatre scraper logs | Continuous |
| `omdb_not_found.txt` | Titles not matched in OMDb (aggregated across scrapers) | Appended each run |
| `tiff_scraper.log` | TIFF scraper logs | Continuous |
| `cal_collate.log` | Collation service logs | Continuous |

## Subscribe to Calendar

Copy the URL of your hosted `toronto_screenings.ics` (or individual .ics files) and subscribe in:

- **Google Calendar:** Settings → From URL
- **Apple Calendar:** File → New Calendar Subscription
- **Outlook:** Add calendar → Subscribe from Web

Example:
```
https://your-server/toronto_screenings.ics
```

## Project Structure

```
├── scraper_utils.py         # Shared utilities (logging, browser, scheduling)
├── revue.py                 # Revue Cinema scraper
├── tiff.py                  # TIFF scraper
├── cal_collate.py           # Calendar collation service
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── DEPLOYMENT.md          # Server deployment guide
```

## Adding a New Scraper

To add another calendar source:

1. Create `new_source.py` importing from `scraper_utils`
2. Implement `parse_page(soup, calendar_obj)` function
3. Implement `scrape_all()` function using `launch_browser()`  
4. Add `schedule_daily()` call or use schedule_at_time()
5. Update `cal_collate.py` to include your .ics file automatically
6. Update documentation

See `tiff.py` for a complete example.

## Troubleshooting

**Check what's happening:**
```bash
tail -f revue_scraper.log
tail -f tiff_scraper.log
tail -f cal_collate.log
```

**No events found:**
- Check HTML in `debug_revue_pageX.html` or `debug_tiff_pageX.html`
- Update selectors in respective .py files
- Verify website structure hasn't changed

**ModuleNotFoundError:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**Browser crashes:**
- Increase server memory
- Reduce `PAGES_TO_SCRAPE`
- Add delays in page navigation

## Configuration

Edit these constants in each scraper:

```python
BASE_URL = "..."           # Website URL to scrape
OUTPUT_FILE = "..."        # ICS file name  
PAGES_TO_SCRAPE = 3       # How many pages to get
LOG_FILE = "..."          # Log file name
```

For scheduling times, see `scraper_utils.py`:
- `schedule_daily(...)` - Random time with min_hour, max_hour (wraps midnight)
- `schedule_at_time(...)` - Fixed time with hour, minute

## Questions?

Check the verbose logs - they contain detailed error information and timestamps!

See [DEPLOYMENT.md](DEPLOYMENT.md) for production server setup.

