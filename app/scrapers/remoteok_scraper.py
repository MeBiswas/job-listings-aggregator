"""
Scraper for https://remoteok.com

RemoteOK renders its job list client-side, so this is the scraper that
exercises the Selenium part of the stack: we open the page in a headless
Chrome browser, let the JS populate the job table, then hand the rendered
HTML to BeautifulSoup for extraction.

NOTE ON MAINTENANCE: like any scraper, this depends on RemoteOK's current
markup. Job sites change their HTML periodically, and this box has no live
network access to verify selectors against the current production site at
build time. The selector logic below is written defensively (multiple
fallbacks, never raises on a missing field) so a markup change degrades to
"fewer fields populated" rather than a crash - but if RemoteOK changes their
layout significantly, update the CSS selectors in `parse_page`.
"""
from typing import List, Dict

from app.scrapers.base import BaseScraper, soupify


class RemoteOKScraper(BaseScraper):
    source_name = "remoteok"
    requires_selenium = True

    def __init__(self, search_terms: List[str] = None, max_pages: int = 1):
        self.search_terms = search_terms or ["python"]
        self.max_pages = max_pages

    def urls_to_scrape(self) -> List[str]:
        return [f"https://remoteok.com/remote-{term}-jobs" for term in self.search_terms]

    def parse_page(self, html: str) -> List[Dict]:
        soup = soupify(html)
        jobs: List[Dict] = []

        rows = soup.select("tr.job")
        for row in rows:
            try:
                title_el = row.select_one("h2") or row.select_one(".company_and_position h2")
                title = title_el.get_text(strip=True) if title_el else None
                if not title:
                    continue

                company_el = row.select_one("h3") or row.select_one(".companyLink h3")
                company = company_el.get_text(strip=True) if company_el else "Unknown"

                location_el = row.select_one(".location")
                location = location_el.get_text(strip=True) if location_el else "Remote"

                salary_els = row.select(".location") + row.select(".salary")
                salary = None
                for el in salary_els:
                    text = el.get_text(strip=True)
                    if "$" in text or "k" in text.lower():
                        salary = text
                        break

                tag_els = row.select(".tag") or row.select(".tags .tag")
                skills = ", ".join(t.get_text(strip=True) for t in tag_els if t.get_text(strip=True))

                href = row.get("data-url") or ""
                apply_url = f"https://remoteok.com{href}" if href.startswith("/") else (href or "https://remoteok.com")

                jobs.append(
                    {
                        "title": title,
                        "company": company,
                        "location": location or "Remote",
                        "salary": salary,
                        "experience": None,
                        "skills": skills or None,
                        "apply_url": apply_url,
                        "source": self.source_name,
                        "is_remote": True,
                        "posted_date": None,
                    }
                )
            except Exception:
                # Skip a malformed row rather than aborting the whole page.
                continue

        return jobs
