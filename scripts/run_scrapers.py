#!/usr/bin/env python3
"""
Standalone entrypoint for running one scrape cycle - meant to be called by
cron (or any external scheduler) instead of relying on the APScheduler job
baked into the FastAPI app.

Usage (manual):
    python scripts/run_scrapers.py

Usage (cron, every hour, see crontab.example for the full line):
    0 * * * *  cd /path/to/job-listings-aggregator && ./venv/bin/python scripts/run_scrapers.py >> logs/scrape.log 2>&1

If you use this script for scheduling, set ENABLE_SCHEDULER=false in your
.env so the app doesn't *also* run its internal APScheduler job - otherwise
you'd be scraping twice as often as intended.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrape_runner import run_all_scrapers  # noqa: E402


def main():
    results = run_all_scrapers()
    total_found = sum(r.jobs_found for r in results)
    total_inserted = sum(r.jobs_inserted for r in results)
    total_dupes = sum(r.jobs_duplicate for r in results)

    print(f"Scrape cycle complete. found={total_found} inserted={total_inserted} duplicates={total_dupes}")
    for r in results:
        print(f"  - {r.source}: found={r.jobs_found} inserted={r.jobs_inserted} duplicates={r.jobs_duplicate} errors={r.errors}")


if __name__ == "__main__":
    main()
