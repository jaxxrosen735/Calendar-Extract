# Toronto Screenings Calendar Aggregator

A modular calendar scraping system that aggregates cinema schedules from multiple sources into a single unified calendar.

**Current Sources:**
- **Revue Cinema** → `revue.ics` 
- **TIFF (Toronto International Film Festival)** → `tiff.ics`
- **Fox Theatre** → `fox.ics`
- **Combined Calendar** → `toronto_screenings.ics` (all events merged)

## Installation

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add OMDb API key (using `scraper/api.env`)
# Create a file named `api.env` in the `scraper/` folder containing:
# OMDB_API_KEY="your_omdb_api_key_here"

# 4. Install Playwright browsers
python -m playwright install chromium
```

## Usage

### Run individual scrapers

```bash
# Revue Cinema (one-off)
python scraper/revue.py

# TIFF (one-off)
python scraper/tiff.py

# Fox Theatre (one-off)
python scraper/fox.py

# Collate calendars (one-off)
python cal_collate.py
```

### Run with automatic daily scheduling

There are two supported ways to run scheduled jobs — **cron-based** or a **long-running scheduler**.

Cron 

Using the idempotent cron installer 

The repository includes `deploy/install_crontab.sh` which installs a managed crontab block that runs the full daily workflow for you:

- `run_scrapers_random.sh` — invoked at 00:00 daily by the cron block; sleeps a random delay (0–4 hours) and runs `revue`, `tiff` and `fox` scrapers (so scraping occurs between 00:00–04:00 local time).
- `wait_for_scrapers_and_collate.sh` — scheduled at 04:30; waits for the scrapers to finish then runs `cal_collate.collate_all()` to produce `toronto_screenings.ics`.
- `verify_collate_and_rotate.sh` — scheduled at 05:30; verifies the combined calendar and runs `log.rotate_and_zip_logs()` (creates the daily `YYYYMMDD_logs.zip`).

Once installed you can set it and forget it — the crontab runs every day, updates the `.ics` files, and archives logs automatically.

```bash
# Install the managed cron block (idempotent)
./deploy/install_crontab.sh

# Dry-run / inspect / remove
./deploy/install_crontab.sh --dry-run   # show what would be installed
./deploy/install_crontab.sh --show      # show current crontab + managed block
./deploy/install_crontab.sh --remove    # remove the managed block
```

Long-running scheduler

Run the centralized in‑process scheduler directly (keeps running until stopped) or run an individual scraper in scheduled mode.

```bash
# Start the centralized in-process scheduler
python3 scraper/scheduling.py
# Or start a single scraper with its internal scheduler
python3 scraper/revue.py --schedule
```

Systemd example (short)

```ini
[Unit]
Description=Toronto Screenings Scheduler
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Calendar Extract
ExecStart=/path/to/.venv/bin/python scraper/scheduling.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Systemd timer option (cron replacement)

- You can use systemd timers instead of cron to run the full daily workflow. Example unit files are provided in the `deploy/` directory (`toronto-scrapers.timer`, `toronto-collate.timer`, `toronto-verify.timer`).
- `toronto-scrapers.timer` runs `run_scrapers_random.sh` (script applies a random sleep 0–4h); `toronto-collate.timer` runs at 04:30 and `toronto-verify.timer` runs at 05:30.
- Install by copying `deploy/toronto-*.service|.timer` to `/etc/systemd/system/`, then `sudo systemctl daemon-reload` and `sudo systemctl enable --now <timer-name>`.

Docker example

```dockerfile
# Dockerfile.scheduler (example)
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt && python -m playwright install chromium
CMD ["python", "scraper/scheduling.py"]
```

# build & run
```bash
docker build -t toronto-scheduler -f Dockerfile.scheduler .
docker run -d -v /path/to/output:/app toronto-scheduler
```

For full service and container examples see `DEPLOYMENT.md`.

Notes:
- Scrapers are **cron-friendly by default**: `python scraper/revue.py` performs a one-off run suitable for cron.
- To set-and-forget, install the managed cron block with `./deploy/install_crontab.sh` — it is idempotent and will run scrapers, collate calendars, and rotate logs daily.
- When using cron, ensure `api.env` (containing `OMDB_API_KEY`) exists in `scraper/` (i.e. `scraper/api.env`) and that `.venv` (if used) is present.
- Use Ctrl+C to stop any interactive scheduler.

## Output Files

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `revue.ics` | Revue Cinema events | Daily (nightly — cron installer runs scrapers between 00:00–04:00 local time; `scheduling.py` uses 23:00–04:00 ET) |
| `tiff.ics` | TIFF events (includes `location` + OMDb-based end times) | Daily (nightly — cron installer runs scrapers between 00:00–04:00 local time; `scheduling.py` uses 23:00–04:00 ET) |
| `fox.ics` | Fox Theatre events | Daily (nightly — cron installer runs scrapers between 00:00–04:00 local time; `scheduling.py` uses 23:00–04:00 ET) |
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
├── scraper/                 # Python scraper modules + helpers
│   ├── scraper_utils.py     # Shared utilities (logging, browser, scheduling helpers)
│   ├── revue.py             # Revue Cinema scraper (one‑off by default; use --schedule to run scheduler)
│   ├── fox.py               # Fox Theatre scraper (one‑off by default; use --schedule to run scheduler)
│   ├── tiff.py              # TIFF scraper (one‑off by default; use --schedule to run scheduler)
│   └── scheduling.py        # Centralized scheduler for scrapers + collation (long-running service)
├── scripts/                 # Shell helpers used by cron / timers
│   ├── run_scrapers_random.sh
│   ├── wait_for_scrapers_and_collate.sh
│   └── verify_collate_and_rotate.sh
├── cal_collate.py           # Calendar collation service (combined .ics)
├── log.py                   # Log rotation & daily archive utility (can be invoked from scripts)
├── deploy/                  # Cron/systemd examples and installers (ignored by git)
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── DEPLOYMENT.md            # Server deployment guide
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
- Reduce `PAGES_TO_SCRAPE`


See [DEPLOYMENT.md](DEPLOYMENT.md) for production server setup.

