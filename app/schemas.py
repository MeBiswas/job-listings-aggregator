from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    salary: Optional[str] = None
    experience: Optional[str] = None
    min_experience_years: Optional[int] = None
    skills: Optional[str] = None
    apply_url: str
    source: str
    is_remote: bool = False
    posted_date: Optional[str] = None


class JobCreate(JobBase):
    pass


class JobOut(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scraped_at: datetime


class PaginatedJobs(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[JobOut]


class StatsOut(BaseModel):
    total_jobs: int
    remote_jobs: int
    by_source: dict
    by_location: dict
    top_skills: dict


class ScrapeRunResult(BaseModel):
    source: str
    jobs_found: int
    jobs_inserted: int
    jobs_duplicate: int
    errors: List[str] = []


class ScrapeTriggerResponse(BaseModel):
    status: str
    detail: str
