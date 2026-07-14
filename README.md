# Job Listings Aggregator

Collects job postings from multiple sources into one database and exposes
them through a searchable REST API + web dashboard.

```
Scheduler (hourly)
      │
      ▼
  Selenium            → opens JS-heavy job sites in a headless browser
      │
      ▼
 BeautifulSoup        → extracts title, company, location, salary,
      │                 experience, skills, apply URL from the HTML
      ▼
 Data cleaning (pandas)→ trims/normalizes fields, drops bad rows,
      │                  removes in-batch duplicates
      ▼
 Deduplication + DB    → hash-based fingerprint, unique constraint,
      │                  SQLite or PostgreSQL via SQLAlchemy
      ▼
   FastAPI             → REST API with filters (skill, remote, experience,
      │                  location, company, free-text search)
      ▼
 Dashboard / REST APIs → static HTML+JS dashboard, or hit the API directly
```

## What's included

- **Two scraper patterns**: `RemoteOKScraper` (Selenium, for JS-rendered
  pages) and `WeWorkRemotelyScraper` (plain `requests`, for static pages) -
  both feeding the same pipeline.
- **`SampleDataScraper`**: a network-free generator that seeds realistic
  demo listings. This is what makes the project **work immediately on
  first run**, with zero external dependencies - real job sites change
  their markup often and can rate-limit or block scrapers, so a project
  wired *only* to live sites can fail for reasons that have nothing to do
  with the code. Remove it from `app/scrapers/__init__.py` once you've
  confirmed the real scrapers work against your target sites.
- **Deduplication** via a normalized hash of (title, company, apply URL),
  enforced with a DB-level unique constraint - safe even against concurrent
  scrapers.
- **Filters**: skill, remote-only, minimum years of experience, location,
  company, source, and free-text search - all combinable, all paginated.
- **Hourly automation**: either an in-process APScheduler job, or a
  standalone script for cron (`scripts/run_scrapers.py`) - pick one.
- **Email digest** of newly found jobs after each scrape cycle (off by
  default; toggle with an env var once you've added SMTP creds).
- **11 automated tests** covering dedup, filters, pandas cleaning, and every
  API endpoint.

## Quickstart (local, SQLite, ~2 minutes)

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # defaults already work as-is

uvicorn app.main:app --reload
```

Open **http://localhost:8000** for the dashboard, or **http://localhost:8000/docs**
for interactive API docs (Swagger UI).

The app creates `jobs.db` (SQLite) automatically on first run - there's
nothing else to configure. To populate it with jobs immediately instead of
waiting for the first hourly run:

```bash
curl -X POST http://localhost:8000/scrape/trigger
```

That runs the sample-data generator plus the two live scrapers (which will
work against RemoteOK/WeWorkRemotely as long as Chrome + chromedriver are
installed locally, or gracefully log an error and skip themselves if not -
either way, the sample data guarantees the dashboard has content).

## Run the tests

```bash
pip install pytest httpx
pytest -v
```

## Running with Docker (includes Chromium, for the Selenium scraper)

```bash
docker compose up --build
```

This builds an image with Chromium + chromium-driver preinstalled (so the
Selenium scraper works out of the box in the container, no local browser
needed) and starts the API on **http://localhost:8000**.

To switch from SQLite to PostgreSQL, uncomment the `db` service in
`docker-compose.yml` and update `DATABASE_URL` in the `api` service to:
`postgresql+psycopg2://jobs_user:jobs_password@db:5432/jobsdb`

## Switching database backends

Everything goes through SQLAlchemy, so switching is a one-line env var
change - no code changes needed:

```bash
# SQLite (default)
DATABASE_URL=sqlite:///./jobs.db

# PostgreSQL
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/jobsdb

# MySQL
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/jobsdb
```
For MySQL, also add `pymysql` to `requirements.txt` (not installed by
default, to keep the base install lighter).

## API reference

| Endpoint | Description |
|---|---|
| `GET /jobs` | Search jobs. Query params: `skill`, `remote`, `min_experience`, `location`, `company`, `source`, `search`, `page`, `page_size`. |
| `GET /jobs/{id}` | Fetch a single job by ID. |
| `GET /stats` | Totals, breakdown by source/location, top skills. |
| `POST /scrape/trigger` | Kick off a scrape cycle immediately (in the background). |
| `GET /health` | Health check. |

Example filter combinations:

```bash
# Python jobs
curl "http://localhost:8000/jobs?skill=python"

# Remote jobs
curl "http://localhost:8000/jobs?remote=true"

# 4+ years of experience
curl "http://localhost:8000/jobs?min_experience=4"

# Mohali or Bangalore
curl "http://localhost:8000/jobs?location=Mohali"
curl "http://localhost:8000/jobs?location=Bangalore"

# Combined
curl "http://localhost:8000/jobs?skill=python&remote=true&min_experience=4&location=Bangalore"
```

## Bonus features

**Hourly automation** - two options, pick one:

1. **Built-in scheduler** (default): `ENABLE_SCHEDULER=true` in `.env`.
   APScheduler runs `run_all_scrapers()` every `SCRAPE_INTERVAL_HOURS` hours
   inside the FastAPI process. Nothing else to set up.
2. **Cron**: set `ENABLE_SCHEDULER=false` in `.env`, then add the line from
   `crontab.example` to your crontab (`crontab -e`). This calls
   `scripts/run_scrapers.py` directly, independent of whether the API
   server is running. Don't enable both at once, or you'll scrape twice as
   often as intended.

**Email notifications** - set in `.env`:

```
ENABLE_EMAIL_NOTIFICATIONS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFY_EMAIL_FROM=you@gmail.com
NOTIFY_EMAIL_TO=you@gmail.com,teammate@gmail.com
```
A digest email is sent after any scrape cycle that finds new (non-duplicate)
jobs. Use an app password, not your real account password, if using Gmail.

**Duplicate removal** - handled two ways in the pipeline: pandas drops
in-batch duplicates before anything touches the DB, and a unique DB
constraint on a normalized (title, company, apply-URL) hash makes it
impossible to insert the same posting twice even across separate runs or
sources.

## Adding a new scraper

1. Create `app/scrapers/my_source_scraper.py`, subclass `BaseScraper`,
   implement `urls_to_scrape()` and `parse_page(html)`. Set
   `requires_selenium = False` if the site's HTML is server-rendered (use
   plain `requests` - faster, no browser needed); leave it `True` for
   JS-heavy sites.
2. Register an instance in `ACTIVE_SCRAPERS` in `app/scrapers/__init__.py`.
3. That's it - the orchestrator, pandas cleaning, dedup, DB insert, filters,
   and email notification all pick it up automatically.

## Known limitations / maintenance notes

- **Site markup changes over time.** The CSS selectors in
  `remoteok_scraper.py` and `weworkremotely_scraper.py` reflect those sites'
  structure as of this writing. If a scraper starts returning 0 results,
  open the target page's HTML in a browser, inspect the current structure,
  and update the selectors in `parse_page()`. Both scrapers are written to
  degrade gracefully (skip a malformed row, log an error, move to the next
  source) rather than crash the whole scrape cycle.
- **Anti-bot protection.** Some sites block or rate-limit automated
  browsers. If a scraper is consistently blocked, consider adding delays
  between requests, rotating user agents, or checking the site's
  `robots.txt` and terms of service before scraping it.
- **The fixed `time.sleep(3)`** in `BaseScraper.fetch_html` is a simple
  wait for JS-rendered content to load. For production use against a
  specific site, replace it with an explicit Selenium
  `WebDriverWait` on a selector you know appears once the job list has
  loaded - more reliable and often faster.

## Project structure

```
app/
  main.py                FastAPI app, routes, scheduler wiring
  config.py               Environment-based settings
  database.py              SQLAlchemy engine/session
  models.py                Job table definition
  schemas.py                Pydantic request/response models
  crud.py                    DB queries + filters + experience parsing
  dedup.py                    Duplicate-detection hashing
  notifier.py                  Email digest sender
  scrape_runner.py               Orchestrates scrapers -> pandas -> DB -> email
  scrapers/
    base.py                       Selenium/requests plumbing shared by all scrapers
    remoteok_scraper.py            Selenium + BeautifulSoup example
    weworkremotely_scraper.py       requests + BeautifulSoup example
    sample_scraper.py                Network-free demo data generator
static/
  index.html              Dashboard (vanilla HTML/CSS/JS, no build step)
scripts/
  run_scrapers.py          Standalone entrypoint for cron
tests/
  test_api.py              11 tests covering dedup, filters, cleaning, API
Dockerfile                 Includes Chromium + chromedriver for Selenium
docker-compose.yml          API service (+ optional Postgres, commented out)
crontab.example             Sample cron line for hourly scraping
.env.example                All configuration options, documented
```
