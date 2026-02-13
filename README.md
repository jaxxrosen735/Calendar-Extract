# Toronto Screenings Calendar Aggregator - Quick Start

A modular calendar scraping system that aggregates cinema schedules from multiple sources into a single unified calendar.

**Current Sources:**
- **Revue Cinema** → `revue.ics` 
- **TIFF (Toronto International Film Festival)** → `tiff.ics`
- **Fox Theatre** → `fox.ics`
- **Combined Calendar** → `toronto_screenings.ics` (all events merged)

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
# Revue Cinema
python -c "from revue import scrape_all; scrape_all()"

# TIFF
python -c "from tiff import scrape_all; scrape_all()"

# Fox Theatre
python -c "from fox import scrape_all; scrape_all()"

# Collate calendars
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
| `fox.ics` | Fox Theatre events | Daily (random time 11 PM - 4 AM) |
| `toronto_screenings.ics` | Combined all sources (revue + tiff + fox) | Daily at 5 AM ET |
| `revue_scraper.log` | Revue scraper logs | Rotated daily if non-empty; live file recreated |
| `fox_scraper.log` | Fox Theatre scraper logs | Rotated daily if non-empty; live file recreated |
| `tiff_scraper.log` | TIFF scraper logs | Rotated daily if non-empty; live file recreated |
| `cal_collate.log` | Collation service logs | Rotated daily if non-empty; live file recreated |
| `omdb_not_found.txt` | Titles not matched in OMDb (aggregated across scrapers) | Rotated & archived daily into `YYYYMMDD_logs.zip` |

### Logs & rotation

- At the end of the collation run `cal_collate.collate_all()` the project rotates any non-empty `*_scraper.log` files, `cal_collate.log`, and `omdb_not_found.txt` into dated files (for example `revue_scraper_20260213.log`).
- Rotated files are bundled into a single daily archive named `YYYYMMDD_logs.zip` (e.g. `20260213_logs.zip`) and the intermediate dated files are removed after archiving.
- The rotation logic lives in `log.py` (function `rotate_and_zip_logs()`); `cal_collate` invokes it automatically after a successful collation.
- After rotation the live filenames (`revue_scraper.log`, etc.) are recreated as empty files so scrapers continue writing to the same paths.
- To run manually: `python3 log.py` (or `from log import rotate_and_zip_logs; rotate_and_zip_logs()`).
- If you want automatic retention (delete archives older than N days), add a retention step — recommended as a follow-up.


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
├── fox.py                 # Fox Theatre scraper
├── tiff.py                  # TIFF scraper
├── cal_collate.py           # Calendar collation service
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── DEPLOYMENT.md          # Server deployment guide
```

## Troubleshooting

**Check what's happening:**

- Live logs (current run):
```bash
tail -f revue_scraper.log
tail -f tiff_scraper.log
tail -f cal_collate.log
```

- Inspect today's archived bundle (rotated at collation):
```bash
ls -l $(date +%Y%m%d)_logs.zip
unzip -l $(date +%Y%m%d)_logs.zip
```

- Force a manual rotation / create today's archive:
```bash
python3 log.py
```

**No events found:**
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

See [DEPLOYMENT.md](DEPLOYMENT.md) for production server setup.

