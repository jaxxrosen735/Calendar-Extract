# Toronto Screenings Calendar Aggregator - Deployment Guide

## Overview

This system aggregates multiple calendar sources (Revue Cinema, TIFF, etc.) into a single master calendar that can be subscribed to from Google Calendar, Apple Calendar, Outlook, etc.

**Services:**
- **scraper/** (contains `revue.py`, `tiff.py`, `fox.py`, `scheduling.py`) — scrapers run nightly (random 11 PM - 4 AM ET).
- **cal_collate.py** - Combines all .ics files (daily at 5 AM ET)

Each service runs independently with its own logging and scheduling. A `omdb_not_found.txt` file collects titles not matched by the OMDb API for later review.

**Architecture:**
- Each scraper is modular and can run independently
- Collation service automatically includes all `*.ics` files

## Setup

### Prerequisites
- Python 3.8+
- Recommended: virtual environment

### Installation

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **OMDb API key (required for runtime lookups):**
   - The scrapers use OMDb to fetch runtimes (used to calculate event end times = start + 15min previews + runtime).
- **Preferred (recommended):** Create an `api.env` file inside the `scraper/` folder containing `OMDB_API_KEY="your_key_here"`. The scrapers load `scraper/api.env` automatically via `python-dotenv`.
   - **Alternative:** Set `OMDB_API_KEY` (or `API_KEY`) in the environment if you prefer not to use `api.env`.
   - Unmatched titles are appended to `omdb_not_found.txt`.
   - OMDb rate limit: ~1000 requests / 24 hours — cache is implemented to minimize calls.

3. **Install Playwright browsers:**
   ```bash
   python -m playwright install chromium
   ```

## Running Locally

### One-time scrape example:
```bash
python -c "from scraper.revue import scrape_all; scrape_all()"
```

### Scheduled mode (runs immediately + daily scheduler):
```bash
# Run scraper once and start the in-process scheduler
python scraper/revue.py -s   # short flag for --schedule
```

This will:
1. Run the scraper immediately
2. Start a background scheduler **(requires `-s` / `--schedule`)** that runs daily at a random time between 11 PM - 4 AM ET
3. Update `revue.ics` on each run
4. Log all activity to `revue_scraper.log`

Note: scrapers are **one‑off by default**; omit `-s` if you want a single run (useful for cron).

## Server Deployment

### Option 1: Systemd Service

Create `/etc/systemd/system/revue-scraper.service` (run scraper in scheduled mode):
```ini
[Unit]
Description=Revue Cinema Calendar Scraper (scheduled mode)
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Calendar Extract
# Note: `-s` (or --schedule) tells the scraper to run as a long-running scheduler
ExecStart=/path/to/.venv/bin/python /path/to/Calendar\ Extract/scraper/revue.py -s
Restart=on-failure
RestartSec=10
StandardOutput=append:/path/to/Calendar Extract/revue_scraper.log
StandardError=append:/path/to/Calendar Extract/revue_scraper.log

[Install]
WantedBy=multi-user.target
```

Enable and start (example):
```bash
sudo systemctl enable revue-scraper
sudo systemctl start revue-scraper
```

Systemd unit for the centralized scheduler

Create `/etc/systemd/system/toronto-scheduler.service`:
```ini
[Unit]
Description=Toronto Screenings Scheduler (centralized APScheduler)
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Calendar Extract
EnvironmentFile=/path/to/Calendar Extract/api.env
ExecStart=/path/to/.venv/bin/python /path/to/Calendar\ Extract/scraper/scheduling.py
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=60
StartLimitBurst=5
StandardOutput=append:/path/to/Calendar Extract/scheduling.log
StandardError=append:/path/to/Calendar Extract/scheduling.log

[Install]
WantedBy=multi-user.target
```

Enable and start the scheduler service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable toronto-scheduler
sudo systemctl start toronto-scheduler
```

Tips:
- `EnvironmentFile` makes it easy to provide `OMDB_API_KEY` without embedding secrets in the unit file.
- `Restart=on-failure` + `StartLimit*` prevent crash loops while keeping the service resilient.
- Logs are written to `scheduling.log` (or view with `journalctl -u toronto-scheduler`).

### Systemd timers (cron replacement)

If you'd prefer to use systemd timers instead of cron the repository includes example timer + service units under `deploy/`.
These timers replicate the managed-cron workflow (`run_scrapers_random.sh` → `wait_for_scrapers_and_collate.sh` → `verify_collate_and_rotate.sh`) and support randomized delays via the script itself and `RandomizedDelaySec` in the timer.

Install and enable the example timers:

```bash
# Copy unit files into place and reload systemd
sudo cp deploy/toronto-*.service /etc/systemd/system/
sudo cp deploy/toronto-*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable & start timers (set-and-forget)
sudo systemctl enable --now toronto-scrapers.timer toronto-collate.timer toronto-verify.timer

# Inspect scheduled timers
systemctl list-timers --all | grep toronto
```

Notes:
- `toronto-scrapers.timer` fires at midnight and the `run_scrapers_random.sh` script applies a 0–4h randomized sleep (the timer also sets `RandomizedDelaySec=14400` by default).
- `toronto-collate.timer` runs `wait_for_scrapers_and_collate.sh` at 04:30; `toronto-verify.timer` runs `verify_collate_and_rotate.sh` at 05:30.
- To remove: `sudo systemctl disable --now toronto-*.timer toronto-*.service`


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

# Copy scraper folder and run the Revue scraper in scheduled mode
COPY scraper/ ./scraper/

CMD ["python", "scraper/revue.py", "-s"]
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

If you prefer simpler cron scheduling instead of the in-process scheduler. Add the scraper to your crontab to run it daily at your chosen time:

```bash
# Run at a fixed time daily (example: 2:30 AM local time)
30 2 * * * cd /path/to/Calendar\ Extract && /path/to/.venv/bin/python scraper/revue.py
```

Alternatively use the included idempotent cron installer (`deploy/install_crontab.sh`) to set up the full daily workflow (scrapers → collate → rotate).

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

**"ModuleNotFoundError"**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**"Browser crashed"**
- Reduce `PAGES_TO_SCRAPE` or add delays

## Monitoring

The scraper logs everything to `*_scraper.log` including:
- Start/stop times
- Number of events extracted
- Error codes and stack traces
- Scheduler status

Health checks & restart guidance

- Systemd: prefer `Restart=on-failure` (already present in examples). Add a small health‑check script that verifies the combined calendar is present and reasonably fresh; configure external monitoring or an OnFailure target if you want alerting.

Example health check script (`deploy/health_check.sh`):
```bash
#!/usr/bin/env bash
# Return 0 if toronto_screenings.ics exists and is newer than 36 hours, otherwise non-zero
FILE="/path/to/Calendar Extract/toronto_screenings.ics"
if [ -f "$FILE" ] && [ $(find "$FILE" -mmin -2160 2>/dev/null) ]; then
  exit 0
else
  echo "toronto_screenings.ics missing or stale" >&2
  exit 1
fi
```

- Docker: use `HEALTHCHECK` in the scheduler image (example below). Combine with `restart: unless-stopped` in `docker-compose.yml` for automatic restarts.

Dockerfile.scheduler (healthcheck example)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y \
    libgconf-2-4 libx11-6 libxext6 libxrender-dev curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r requirements.txt \
    && python -m playwright install chromium
COPY . .
ENV PYTHONUNBUFFERED=1

# Healthcheck: consider toronto_screenings.ics presence/age (start-period allows initial run)
HEALTHCHECK --interval=5m --timeout=10s --start-period=2m --retries=3 \
  CMD bash -lc "test -s /app/toronto_screenings.ics && find /app/toronto_screenings.ics -mmin -4320 >/dev/null || exit 1"

CMD ["python", "scraper/scheduling.py"]
```

docker-compose (suggested settings)
```yaml
version: '3.8'
services:
  scheduler:
    build:
      context: .
      dockerfile: Dockerfile.scheduler
    restart: unless-stopped
    volumes:
      - ./data:/app
    environment:
      - OMDB_API_KEY=your_key_here
    healthcheck:
      test: ["CMD", "bash", "-lc", "test -s /app/toronto_screenings.ics && find /app/toronto_screenings.ics -mmin -4320 >/dev/null || exit 1"]
      interval: 5m
      timeout: 10s
      retries: 3
      start_period: 2m
```
## Performance Notes

- **Headless mode**: Runs ~30 seconds per full scrape
- **Memory usage**: ~200-300MB
- **Network**: ~2-5 MB per scrape
- **Storage**: ICS file is ~40KB

---

For questions or issues, check the log files.
