# Toronto Screenings Calendar Aggregator - Deployment Guide

## Overview

This system aggregates multiple calendar sources (Revue Cinema, TIFF, etc.) into a single master calendar that can be subscribed to from Google Calendar, Apple Calendar, Outlook, etc.

**Services:**
- **revue.py** - Scrapes Revue Cinema calendar (daily, random 11 PM - 4 AM ET). Now uses OMDb to fetch runtimes and writes accurate event end times.
- **tiff.py** - Scrapes TIFF calendar (daily, random 11 PM - 4 AM ET). Adds `location` in events and uses OMDb for runtime/end-time calculation (previews + runtime).
- **fox.py** - Scrapes Fox Theatre (daily, random 11 PM - 4 AM ET). Adds `location` and OMDb runtime lookups for accurate end times.
- **cal_collate.py** - Combines all .ics files (daily at 5 AM ET)

Each service runs independently with its own logging and scheduling. A shared `omdb_not_found.txt` file collects titles not matched by the OMDb API for later review.

**Architecture:**
- Shared utilities in `scraper_utils.py` reduce code duplication
- Each scraper is modular and can run independently
- Collation service automatically includes all `*.ics` files
- Easy to add new scrapers by following the template

## Setup

### Prerequisites
- Python 3.8+
- Virtual environment

### Installation

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   # or (explicit):
   pip install playwright beautifulsoup4 ics apscheduler pytz requests
   ```

3. **OMDb API key (required for runtime lookups):**
   - The scrapers use OMDb to fetch runtimes (used to calculate event end times = start + 15min previews + runtime).
   - **Preferred (recommended):** Create an `api.env` file at the project root containing `OMDB_API_KEY="your_key_here"`. The scrapers load `api.env` automatically via `python-dotenv`.
   - **Alternative:** Set `OMDB_API_KEY` (or `API_KEY`) in the environment if you prefer not to use `api.env`.
   - A fuzzy-title search fallback is implemented to reduce misses; unmatched titles are appended to `omdb_not_found.txt`.
   - OMDb rate limit: ~1000 requests / 24 hours — cache is implemented to minimize calls.

3. **Install Playwright browsers:**
   ```bash
   python -m playwright install chromium
   ```

## Running Locally

### One-time scrape:
```bash
python -c "from revue import scrape_all; scrape_all()"
```

### Scheduled mode (runs immediately + daily scheduler):
```bash
python revue.py
```

This will:
1. Run the scraper immediately
2. Start a background scheduler that runs daily at a random time between 11 PM - 4 AM ET
3. Update `revue.ics` on each run
4. Log all activity to `revue_scraper.log`

## Server Deployment

### Option 1: Systemd Service (Linux/macOS with Homebrew)

Create `/etc/systemd/system/revue-scraper.service`:
```ini
[Unit]
Description=Revue Cinema Calendar Scraper
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Calendar Extract
ExecStart=/path/to/.venv/bin/python revue.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/path/to/Calendar Extract/revue_scraper.log
StandardError=append:/path/to/Calendar Extract/revue_scraper.log

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable revue-scraper
sudo systemctl start revue-scraper
```

### Option 2: Docker Container

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libgconf-2-4 libx11-6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt && \
    python -m playwright install chromium

COPY revue.py .

CMD ["python", "revue.py"]
```

Create `requirements.txt`:
```
playwright>=1.40.0
beautifulsoup4>=4.12.0
ics>=0.7
apscheduler>=3.10.4
pytz>=2024.1
```

Build and run:
```bash
docker build -t revue-scraper .
docker run -d -v /path/to/output:/app revue-scraper
```

### Option 3: Cron Job (One-time daily run)

If you prefer simpler cron scheduling instead of built-in scheduler, modify `revue.py` main block:

```python
if __name__ == "__main__":
    scrape_all()  # Just run once
```

Then add to crontab:
```bash
# Run at random time between 11 PM and 4 AM
# Example: 2:30 AM daily
30 2 * * * cd /path/to/Calendar\ Extract && /path/to/.venv/bin/python revue.py
```

## Hosting the ICS File

### Option 1: Simple HTTP Server
```bash
python -m http.server 8000 --directory /path/to/Calendar\ Extract
```

Access at: `http://your-server:8000/revue.ics`

Note: In production you will probably host `toronto_screenings.ics` (the combined feed). All `.ics` outputs (including `revue.ics`, `tiff.ics`, `fox.ics`) are colocated in the project folder and auto-discovered by `cal_collate.py`.

### Option 2: Nginx
```nginx
server {
    listen 80;
    server_name calendar.example.com;
    root /path/to/Calendar\ Extract;
    
    location /revue.ics {
        add_header Cache-Control "max-age=3600";
        add_header Content-Type "text/calendar";
    }
}
```

### Option 3: AWS S3 / Google Cloud Storage
Automatically upload the ICS file after each scrape by adding:
```python
# Add at end of scrape_all() function
import subprocess
subprocess.run(['aws', 's3', 'cp', OUTPUT_FILE, 's3://your-bucket/revue.ics'])
```

## Subscribe in Calendar Apps

### Google Calendar
1. Go to Settings → Add calendar → From URL
2. Enter: `http://your-server/revue.ics`
3. Click Subscribe

### Apple Calendar / macOS
1. File → New Calendar Subscription
2. Enter: `http://your-server/revue.ics`

### Outlook
1. Add calendar → Subscribe from Web
2. Enter: `http://your-server/revue.ics`

## Troubleshooting

### Check logs:
```bash
tail -f revue_scraper.log
```

### Common issues:

**"No Next button found"**
- The selector may have changed. Check `debug_response_pageX.html` files
- Update selectors in `find_next_button()` function

**"Incapsula incident ID"**
- The website blocked the scraper. This shouldn't happen with Playwright headless
- Add delays or try rotating user agents

**"ModuleNotFoundError"**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**"Browser crashed"**
- Increase memory/resources on server
- Reduce `PAGES_TO_SCRAPE` or add delays

## Monitoring

The scraper logs everything to `revue_scraper.log` including:
- Start/stop times
- Number of events extracted
- Error codes and stack traces
- Scheduler status

Set up log rotation to prevent disk space issues:
```bash
# /etc/logrotate.d/revue-scraper
/path/to/Calendar\ Extract/revue_scraper.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
}
```

## Performance Notes

- **Headless mode**: Runs ~30 seconds per full scrape
- **Memory usage**: ~200-300MB
- **Network**: ~2-5 MB per scrape
- **Storage**: ICS file is ~40KB

---

For questions or issues, check the verbose logs in `revue_scraper.log`.
