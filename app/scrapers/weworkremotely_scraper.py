"""
Scraper for https://weworkremotely.com

WeWorkRemotely's listing pages are server-rendered, so this scraper skips
Selenium entirely and uses plain `requests` + BeautifulSoup - faster and
lighter than spinning up a browser. It's included alongside the Selenium-based
RemoteOK scraper to show both patterns in one project: use Selenium only
where a site actually needs JS execution, plain HTTP everywhere else.
"""
from typing import List, Dict

from app.scrapers.base import BaseScraper, soupify


class WeWorkRemotelyScraper(BaseScraper):
    source_name = "weworkremotely"
    requires_selenium = False  # static HTML - no browser needed

    def __init__(self, categories: List[str] = None):
        self.categories = categories or ["remote-programming-jobs"]

    def urls_to_scrape(self) -> List[str]:
        return [f"https://weworkremotely.com/categories/{cat}" for cat in self.categories]

    def parse_page(self, html: str) -> List[Dict]:
        soup = soupify(html)
        jobs: List[Dict] = []

        listings = soup.select("li.feature") + soup.select("section.jobs article li")
        for li in listings:
            try:
                link = li.select_one("a[href*='/remote-jobs/']")
                if not link:
                    continue

                title_el = li.select_one("span.title")
                title = title_el.get_text(strip=True) if title_el else None
                if not title:
                    continue

                company_el = li.select_one("span.company")
                company = company_el.get_text(strip=True) if company_el else "Unknown"

                region_el = li.select_one("span.region")
                location = region_el.get_text(strip=True) if region_el else "Remote"

                href = link.get("href", "")
                apply_url = f"https://weworkremotely.com{href}" if href.startswith("/") else href

                jobs.append(
                    {
                        "title": title,
                        "company": company,
                        "location": location or "Remote",
                        "salary": None,
                        "experience": None,
                        "skills": None,
                        "apply_url": apply_url,
                        "source": self.source_name,
                        "is_remote": True,
                        "posted_date": None,
                    }
                )
            except Exception:
                continue

        return jobs
