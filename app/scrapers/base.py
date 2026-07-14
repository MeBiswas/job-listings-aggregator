"""
Shared Selenium plumbing for all scrapers.

Each concrete scraper subclasses BaseScraper and implements:
  - source_name
  - urls_to_scrape()   -> list of page URLs to visit
  - parse_page(html)   -> list of job dicts scraped from one page's HTML

The base class handles opening/closing the browser and turning any single
page failure into a logged error rather than crashing the whole run -
important since job sites change their markup often and one bad page
shouldn't take down the aggregator.
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict

from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    source_name: str = "base"
    # Sites that don't need JS rendering can set requires_selenium = False
    # and the scraper will use plain `requests` instead (faster, no browser).
    requires_selenium: bool = True

    @abstractmethod
    def urls_to_scrape(self) -> List[str]:
        ...

    @abstractmethod
    def parse_page(self, html: str) -> List[Dict]:
        ...

    def _make_driver(self):
        import os
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        if settings.selenium_headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )

        # In the Docker image we install Chromium + chromium-driver via apt
        # at fixed paths, so point Selenium at them directly instead of
        # relying on Selenium Manager to download a matching driver at
        # runtime (which needs outbound internet access to Google's CDN).
        chrome_binary = os.environ.get("SELENIUM_CHROME_BINARY")
        if chrome_binary and os.path.exists(chrome_binary):
            options.binary_location = chrome_binary

        driver_path = os.environ.get("SELENIUM_CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
        if os.path.exists(driver_path):
            service = Service(executable_path=driver_path)
            return webdriver.Chrome(service=service, options=options)

        # Fallback: let Selenium Manager resolve a driver automatically
        # (works fine for local development where Chrome is already installed).
        return webdriver.Chrome(options=options)

    def fetch_html(self, url: str) -> str:
        """Fetch rendered HTML for a URL, via Selenium or plain requests."""
        if not self.requires_selenium:
            import requests

            resp = requests.get(
                url,
                timeout=settings.scrape_timeout_seconds,
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobAggregatorBot/1.0)"},
            )
            resp.raise_for_status()
            return resp.text

        driver = self._make_driver()
        try:
            driver.set_page_load_timeout(settings.scrape_timeout_seconds)
            driver.get(url)
            # Give client-side rendered content a moment to load. Production
            # scrapers should replace this with an explicit WebDriverWait for
            # a known selector - a fixed sleep is the simplest thing that
            # works across many different sites for a demo project.
            time.sleep(3)
            return driver.page_source
        finally:
            driver.quit()

    def run(self) -> List[Dict]:
        """Scrape all configured pages for this source, return raw job dicts."""
        all_jobs: List[Dict] = []
        for url in self.urls_to_scrape():
            try:
                html = self.fetch_html(url)
                jobs = self.parse_page(html)
                logger.info("[%s] parsed %d jobs from %s", self.source_name, len(jobs), url)
                all_jobs.extend(jobs)
            except Exception as exc:  # noqa: BLE001 - one bad page must not kill the run
                logger.error("[%s] failed to scrape %s: %s", self.source_name, url, exc)
        return all_jobs


def soupify(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")
