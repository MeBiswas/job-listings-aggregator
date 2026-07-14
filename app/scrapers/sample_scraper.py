"""
A network-free "scraper" that returns realistic sample listings.

Why this exists: live job sites change their HTML constantly and some are
behind bot protection, so a scraper tied only to real sites can fail for
reasons that have nothing to do with your code (blocked network, changed
markup, rate limiting). This module lets you:

  1. See the whole pipeline (dedup -> DB -> API -> dashboard -> email) work
     correctly the moment you deploy, with zero external dependencies.
  2. Have a reliable fallback/demo source if the live scrapers need
     selector updates for the sites' current markup.

It's wired into the scheduler alongside the real scrapers - disable it in
`app/scrapers/__init__.py` (ACTIVE_SCRAPERS) once you've confirmed the real
scrapers work against your target sites.
"""
import random
from datetime import datetime, timedelta
from typing import List, Dict

from app.scrapers.base import BaseScraper

_TITLES = [
    "Python Backend Developer", "Senior Python Engineer", "Full Stack Developer (Python/React)",
    "Data Engineer", "Machine Learning Engineer", "Django Developer", "DevOps Engineer",
    "Software Engineer - Backend", "Python Automation Engineer", "API Developer",
]
_COMPANIES = [
    "Northwind Analytics", "BlueCrest Softwares", "Pixel Forge Labs", "Quantum Byte Technologies",
    "Skyline Data Systems", "Vertex Cloud Solutions", "Nimbus Tech Pvt Ltd", "Orbital Software Studio",
]
_LOCATIONS = ["Mohali", "Bangalore", "Remote", "Pune", "Hyderabad", "Chandigarh", "Gurugram"]
_SKILL_POOL = [
    "Python", "Django", "FastAPI", "Flask", "PostgreSQL", "MySQL", "Docker", "AWS",
    "REST APIs", "Selenium", "Pandas", "SQLAlchemy", "React", "Kubernetes", "Redis", "Git",
]
_EXPERIENCE_BUCKETS = ["0-1 years", "1-3 years", "2-4 years", "4-6 years", "5+ years", "7+ years"]


class SampleDataScraper(BaseScraper):
    source_name = "sample_demo"
    requires_selenium = False  # generates data locally, no HTTP call at all

    def __init__(self, count: int = 25, seed: int = 42):
        self.count = count
        self._rng = random.Random(seed)

    def urls_to_scrape(self) -> List[str]:
        # No real URL is fetched for this source; base.run() calls fetch_html
        # only if this list is non-empty, so we override run() instead.
        return []

    def parse_page(self, html: str) -> List[Dict]:
        return []

    def run(self) -> List[Dict]:
        jobs = []
        for i in range(self.count):
            title = self._rng.choice(_TITLES)
            company = self._rng.choice(_COMPANIES)
            location = self._rng.choice(_LOCATIONS)
            is_remote = location == "Remote" or self._rng.random() < 0.3
            experience = self._rng.choice(_EXPERIENCE_BUCKETS)
            skills = ", ".join(self._rng.sample(_SKILL_POOL, k=self._rng.randint(3, 6)))
            salary_low = self._rng.choice([6, 8, 10, 12, 15, 18])
            salary_high = salary_low + self._rng.choice([3, 4, 5, 6])
            posted_days_ago = self._rng.randint(0, 6)
            posted_date = (datetime.utcnow() - timedelta(days=posted_days_ago)).strftime("%Y-%m-%d")

            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "salary": f"₹{salary_low}L - ₹{salary_high}L per annum",
                    "experience": experience,
                    "skills": skills,
                    # unique-ish per generated run index so repeated runs mostly
                    # dedup against existing rows (realistic demo behaviour)
                    "apply_url": f"https://example-careers.com/jobs/{company.lower().replace(' ', '-')}-{title.lower().replace(' ', '-')}-{i}",
                    "source": self.source_name,
                    "is_remote": is_remote,
                    "posted_date": posted_date,
                }
            )
        return jobs
