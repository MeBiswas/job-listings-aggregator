from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    UniqueConstraint,
    Index,
)

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(300), nullable=False, index=True)
    company = Column(String(300), nullable=False, index=True)
    location = Column(String(300), nullable=True, index=True)
    salary = Column(String(150), nullable=True)
    experience = Column(String(150), nullable=True)   # raw text, e.g. "4-6 years"
    min_experience_years = Column(Integer, nullable=True, index=True)  # parsed number
    skills = Column(Text, nullable=True)               # comma-separated
    apply_url = Column(String(1000), nullable=False)
    source = Column(String(100), nullable=False, index=True)  # e.g. "remoteok"

    is_remote = Column(Boolean, default=False, index=True)
    posted_date = Column(String(100), nullable=True)   # site-provided text, kept raw

    # dedup_hash is a stable fingerprint of (title + company + apply_url),
    # normalized. It carries a unique constraint so duplicate scrapes across
    # runs/sources can never create a second row for the same posting.
    dedup_hash = Column(String(64), nullable=False, unique=True, index=True)

    scraped_at = Column(DateTime, default=utcnow)
    notified = Column(Boolean, default=False)   # has an email alert gone out for this job?

    __table_args__ = (
        Index("ix_jobs_remote_exp", "is_remote", "min_experience_years"),
    )

    def __repr__(self):
        return f"<Job id={self.id} title={self.title!r} company={self.company!r}>"
