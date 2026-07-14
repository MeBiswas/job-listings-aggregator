"""
Basic test suite. Run with:  pytest -v

Uses a fresh in-memory SQLite DB per test session so tests never touch your
real jobs.db and always start from a clean slate.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENABLE_SCHEDULER"] = "false"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models, schemas, crud
from app.dedup import compute_dedup_hash
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


SAMPLE_JOB = schemas.JobCreate(
    title="Python Backend Developer",
    company="Acme Corp",
    location="Mohali",
    salary="10-15 LPA",
    experience="4-6 years",
    skills="Python, Django, PostgreSQL",
    apply_url="https://example.com/jobs/123",
    source="sample_demo",
    is_remote=False,
    posted_date="2026-07-01",
)


def test_dedup_hash_is_stable_and_normalizes_case():
    h1 = compute_dedup_hash("Python Dev", "Acme Corp", "https://x.com/job/1?ref=abc")
    h2 = compute_dedup_hash("  python dev ", "ACME CORP", "https://x.com/job/1?ref=xyz")
    assert h1 == h2  # different casing/whitespace/query-string, same job


def test_parse_min_experience_years():
    assert crud.parse_min_experience_years("4-6 years") == 4
    assert crud.parse_min_experience_years("5+ years") == 5
    assert crud.parse_min_experience_years("Fresher") == 0
    assert crud.parse_min_experience_years(None) is None


def test_create_job_inserts_new_row(db_session):
    job, was_duplicate = crud.create_job(db_session, SAMPLE_JOB)
    assert job is not None
    assert was_duplicate is False
    assert db_session.query(models.Job).count() == 1


def test_create_job_deduplicates_identical_posting(db_session):
    crud.create_job(db_session, SAMPLE_JOB)
    job2, was_duplicate = crud.create_job(db_session, SAMPLE_JOB)
    assert was_duplicate is True
    assert db_session.query(models.Job).count() == 1


def test_get_jobs_filters_by_skill_and_experience(db_session):
    crud.create_job(db_session, SAMPLE_JOB)
    crud.create_job(
        db_session,
        schemas.JobCreate(
            title="Junior React Developer",
            company="Beta LLC",
            location="Bangalore",
            experience="1-2 years",
            skills="React, JavaScript",
            apply_url="https://example.com/jobs/456",
            source="sample_demo",
            is_remote=True,
        ),
    )

    python_jobs, total = crud.get_jobs(db_session, skill="Python")
    assert total == 1
    assert python_jobs[0].company == "Acme Corp"

    senior_jobs, total = crud.get_jobs(db_session, min_experience=4)
    assert total == 1

    remote_jobs, total = crud.get_jobs(db_session, remote=True)
    assert total == 1
    assert remote_jobs[0].company == "Beta LLC"

    mohali_jobs, total = crud.get_jobs(db_session, location="Mohali")
    assert total == 1


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_jobs_endpoint_empty(client):
    resp = client.get("/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


def test_jobs_endpoint_with_filters(client, db_session):
    crud.create_job(db_session, SAMPLE_JOB)
    resp = client.get("/jobs", params={"skill": "python", "location": "mohali"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "Python Backend Developer"


def test_job_detail_and_404(client, db_session):
    job, _ = crud.create_job(db_session, SAMPLE_JOB)
    resp = client.get(f"/jobs/{job.id}")
    assert resp.status_code == 200
    assert resp.json()["company"] == "Acme Corp"

    resp_missing = client.get("/jobs/999999")
    assert resp_missing.status_code == 404


def test_stats_endpoint(client, db_session):
    crud.create_job(db_session, SAMPLE_JOB)
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_jobs"] == 1
    assert "sample_demo" in body["by_source"]


def test_pandas_cleaning_drops_bad_rows_and_dedupes():
    from app.scrape_runner import _clean_with_pandas

    raw = [
        {"title": "Dev A", "company": "X", "apply_url": "https://x.com/1"},
        {"title": "Dev A", "company": "x", "apply_url": "https://x.com/1?ref=2"},  # dup
        {"title": "  ", "company": "Y", "apply_url": "https://y.com/1"},  # blank title, dropped
        {"title": "Dev B", "company": None, "apply_url": "https://z.com/1"},  # missing company, dropped
    ]
    cleaned = _clean_with_pandas(raw)
    assert len(cleaned) == 1
    assert cleaned[0]["title"] == "Dev A"
