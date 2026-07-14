"""
Orchestrates a full scrape cycle:

  Selenium/requests (per scraper) -> BeautifulSoup parse -> pandas cleaning
  -> dedup + DB insert -> (optional) email digest of newly added jobs

This is what both the hourly scheduler and the manual "/scrape/trigger"
API endpoint call.
"""
import logging
from typing import List, Dict

import pandas as pd

from app.database import SessionLocal
from app import crud, schemas
from app.scrapers import ACTIVE_SCRAPERS
from app.config import settings
from app.notifier import send_new_jobs_email

logger = logging.getLogger(__name__)


def _clean_with_pandas(raw_jobs: List[Dict]) -> List[Dict]:
    """
    Use pandas to clean/normalize the batch of scraped rows before they hit
    the DB: trims whitespace, drops rows missing required fields, and does
    an in-batch duplicate drop (by title+company+apply_url) before the
    per-row DB-level dedup even runs.
    """
    if not raw_jobs:
        return []

    df = pd.DataFrame(raw_jobs)

    required = ["title", "company", "apply_url"]
    for col in required:
        if col not in df.columns:
            df[col] = None
    df = df.dropna(subset=required)
    df = df[(df["title"].str.strip() != "") & (df["company"].str.strip() != "")]

    string_cols = ["title", "company", "location", "salary", "experience", "skills", "apply_url"]
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)

    df["_dedup_key"] = (
        df["title"].str.lower().str.strip()
        + "|"
        + df["company"].str.lower().str.strip()
        + "|"
        + df["apply_url"].str.split("?").str[0].str.lower().str.rstrip("/")
    )
    df = df.drop_duplicates(subset="_dedup_key", keep="first").drop(columns="_dedup_key")

    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")


def run_all_scrapers() -> List[schemas.ScrapeRunResult]:
    results: List[schemas.ScrapeRunResult] = []
    db = SessionLocal()
    newly_inserted_ids: List[int] = []

    try:
        for scraper in ACTIVE_SCRAPERS:
            errors: List[str] = []
            try:
                raw_jobs = scraper.run()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scraper %s crashed", scraper.source_name)
                results.append(
                    schemas.ScrapeRunResult(
                        source=scraper.source_name,
                        jobs_found=0,
                        jobs_inserted=0,
                        jobs_duplicate=0,
                        errors=[str(exc)],
                    )
                )
                continue

            cleaned = _clean_with_pandas(raw_jobs)

            inserted = 0
            duplicates = 0
            for row in cleaned:
                try:
                    job_in = schemas.JobCreate(**row)
                except Exception as exc:  # noqa: BLE001 - bad row shape from a flaky site
                    errors.append(f"skipped malformed row: {exc}")
                    continue

                db_job, was_duplicate = crud.create_job(db, job_in)
                if was_duplicate:
                    duplicates += 1
                elif db_job is not None:
                    inserted += 1
                    newly_inserted_ids.append(db_job.id)

            results.append(
                schemas.ScrapeRunResult(
                    source=scraper.source_name,
                    jobs_found=len(raw_jobs),
                    jobs_inserted=inserted,
                    jobs_duplicate=duplicates,
                    errors=errors,
                )
            )
            logger.info(
                "[%s] found=%d inserted=%d duplicates=%d",
                scraper.source_name,
                len(raw_jobs),
                inserted,
                duplicates,
            )

        if settings.enable_email_notifications and newly_inserted_ids:
            try:
                from app import models as _models

                new_job_rows = (
                    db.query(_models.Job).filter(_models.Job.id.in_(newly_inserted_ids)).all()
                )
                send_new_jobs_email(new_job_rows)
                crud.mark_notified(db, newly_inserted_ids)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to send new-jobs email notification")

    finally:
        db.close()

    return results
