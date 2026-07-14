import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db, Base
from app import crud, schemas
from app.scrape_runner import run_all_scrapers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Create tables on startup if they don't exist yet (fine for SQLite/dev;
# for production Postgres you may prefer Alembic migrations instead).
Base.metadata.create_all(bind=engine)

scheduler = None  # set up in lifespan if enabled


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    if settings.enable_scheduler:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_all_scrapers,
            "interval",
            hours=settings.scrape_interval_hours,
            id="hourly_scrape",
        )
        scheduler.start()
        logger.info("Scheduler started: scraping every %s hour(s).", settings.scrape_interval_hours)
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.api_title,
    description="Aggregates job listings from multiple sources into one searchable API + dashboard.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse("static/index.html")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/jobs", response_model=schemas.PaginatedJobs, tags=["jobs"])
def list_jobs(
    skill: Optional[str] = Query(None, description="Filter by skill, e.g. 'python'"),
    remote: Optional[bool] = Query(None, description="Filter remote-only jobs"),
    min_experience: Optional[int] = Query(None, ge=0, description="Minimum years of experience, e.g. 4"),
    location: Optional[str] = Query(None, description="Filter by location, e.g. 'Mohali'"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    source: Optional[str] = Query(None, description="Filter by source, e.g. 'remoteok'"),
    search: Optional[str] = Query(None, description="Free-text search across title/company/skills"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Search jobs with filters, e.g.:
      /jobs?skill=python&remote=true&min_experience=4&location=Mohali
    """
    results, total = crud.get_jobs(
        db,
        skill=skill,
        remote=remote,
        min_experience=min_experience,
        location=location,
        company=company,
        source=source,
        search=search,
        page=page,
        page_size=page_size,
    )
    return schemas.PaginatedJobs(total=total, page=page, page_size=page_size, results=results)


@app.get("/jobs/{job_id}", response_model=schemas.JobOut, tags=["jobs"])
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/stats", response_model=schemas.StatsOut, tags=["jobs"])
def stats(db: Session = Depends(get_db)):
    return crud.get_stats(db)


@app.post("/scrape/trigger", response_model=schemas.ScrapeTriggerResponse, tags=["scraping"])
def trigger_scrape(background_tasks: BackgroundTasks):
    """
    Manually kick off a scrape cycle in the background (in addition to the
    automatic hourly run). Returns immediately; check GET /stats or GET /jobs
    afterwards to see results, or watch server logs for per-source counts.
    """
    background_tasks.add_task(run_all_scrapers)
    return schemas.ScrapeTriggerResponse(
        status="started",
        detail="Scrape cycle triggered in the background. Check /stats shortly for updated counts.",
    )
