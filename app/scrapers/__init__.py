"""
Registry of scrapers the aggregator will run.

To point this at real job sites:
  1. Make sure Chrome/Chromium + a matching chromedriver are installed
     (see README / Dockerfile - already set up there).
  2. Remove SampleDataScraper below once you've validated the real scrapers
     work end-to-end (site markup does change over time - re-check the
     CSS selectors in remoteok_scraper.py / weworkremotely_scraper.py
     periodically).
  3. Add more scrapers the same way: subclass BaseScraper, implement
     urls_to_scrape() + parse_page(), append an instance to ACTIVE_SCRAPERS.
"""
from app.scrapers.sample_scraper import SampleDataScraper
from app.scrapers.remoteok_scraper import RemoteOKScraper
from app.scrapers.weworkremotely_scraper import WeWorkRemotelyScraper

ACTIVE_SCRAPERS = [
    SampleDataScraper(count=25),
    RemoteOKScraper(search_terms=["python"]),
    WeWorkRemotelyScraper(categories=["remote-programming-jobs"]),
]
