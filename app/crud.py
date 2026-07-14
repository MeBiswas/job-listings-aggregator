import re
from typing import Optional, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models, schemas
from app.dedup import compute_dedup_hash


def parse_min_experience_years(experience_text: Optional[str]) -> Optional[int]:
    """
    Extract a minimum-years-of-experience integer from free text like:
      "4-6 years", "4+ years", "2 to 4 Yrs", "Fresher", "Entry level"
    Returns None if nothing numeric can be found.
    """
    if not experience_text:
        return None
    text = experience_text.lower()
    if "fresher" in text or "entry" in text or "intern" in text:
        return 0
    match = re.search(r"(\d+)\s*(?:\+|-|to)?", text)
    if match:
        return int(match.group(1))
    return None


def create_job(db: Session, job: schemas.JobCreate) -> Tuple[Optional[models.Job], bool]:
    """
    Insert a job if it's not a duplicate.
    Returns (job_row_or_None, was_duplicate).
    """
    dedup_hash = compute_dedup_hash(job.title, job.company, job.apply_url)

    existing = db.query(models.Job).filter(models.Job.dedup_hash == dedup_hash).first()
    if existing:
        return existing, True

    min_years = job.min_experience_years
    if min_years is None:
        min_years = parse_min_experience_years(job.experience)

    db_job = models.Job(
        title=job.title.strip(),
        company=job.company.strip(),
        location=(job.location or "").strip() or None,
        salary=(job.salary or "").strip() or None,
        experience=(job.experience or "").strip() or None,
        min_experience_years=min_years,
        skills=(job.skills or "").strip() or None,
        apply_url=job.apply_url.strip(),
        source=job.source,
        is_remote=job.is_remote,
        posted_date=job.posted_date,
        dedup_hash=dedup_hash,
    )
    db.add(db_job)
    try:
        db.commit()
        db.refresh(db_job)
        return db_job, False
    except IntegrityError:
        # Another concurrent insert beat us to it (race on the unique index).
        db.rollback()
        return None, True


def get_jobs(
    db: Session,
    skill: Optional[str] = None,
    remote: Optional[bool] = None,
    min_experience: Optional[int] = None,
    location: Optional[str] = None,
    company: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[models.Job], int]:
    query = db.query(models.Job)

    if skill:
        query = query.filter(models.Job.skills.ilike(f"%{skill}%"))
    if remote is not None:
        query = query.filter(models.Job.is_remote == remote)
    if min_experience is not None:
        query = query.filter(models.Job.min_experience_years >= min_experience)
    if location:
        query = query.filter(models.Job.location.ilike(f"%{location}%"))
    if company:
        query = query.filter(models.Job.company.ilike(f"%{company}%"))
    if source:
        query = query.filter(models.Job.source == source)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.Job.title.ilike(like))
            | (models.Job.company.ilike(like))
            | (models.Job.skills.ilike(like))
        )

    total = query.count()
    results = (
        query.order_by(models.Job.scraped_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return results, total


def get_job(db: Session, job_id: int) -> Optional[models.Job]:
    return db.query(models.Job).filter(models.Job.id == job_id).first()


def get_stats(db: Session) -> dict:
    total_jobs = db.query(func.count(models.Job.id)).scalar() or 0
    remote_jobs = (
        db.query(func.count(models.Job.id)).filter(models.Job.is_remote.is_(True)).scalar() or 0
    )

    by_source_rows = (
        db.query(models.Job.source, func.count(models.Job.id)).group_by(models.Job.source).all()
    )
    by_location_rows = (
        db.query(models.Job.location, func.count(models.Job.id))
        .filter(models.Job.location.isnot(None))
        .group_by(models.Job.location)
        .order_by(func.count(models.Job.id).desc())
        .limit(10)
        .all()
    )

    skill_counter: dict = {}
    for (skills_text,) in db.query(models.Job.skills).filter(models.Job.skills.isnot(None)):
        for s in skills_text.split(","):
            s = s.strip()
            if not s:
                continue
            skill_counter[s] = skill_counter.get(s, 0) + 1
    top_skills = dict(sorted(skill_counter.items(), key=lambda kv: kv[1], reverse=True)[:15])

    return {
        "total_jobs": total_jobs,
        "remote_jobs": remote_jobs,
        "by_source": dict(by_source_rows),
        "by_location": dict(by_location_rows),
        "top_skills": top_skills,
    }


def get_unnotified_jobs(db: Session) -> List[models.Job]:
    return db.query(models.Job).filter(models.Job.notified.is_(False)).all()


def mark_notified(db: Session, job_ids: List[int]) -> None:
    if not job_ids:
        return
    db.query(models.Job).filter(models.Job.id.in_(job_ids)).update(
        {models.Job.notified: True}, synchronize_session=False
    )
    db.commit()
