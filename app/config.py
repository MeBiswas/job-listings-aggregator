"""
Central configuration, loaded from environment variables (or a .env file).
Keeping all tunables here means you can deploy the same code against
SQLite (zero-config) or PostgreSQL/MySQL (production) just by changing
DATABASE_URL.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database ---
    # Defaults to a local SQLite file so the project runs with zero setup.
    # For Postgres use e.g. postgresql+psycopg2://user:pass@localhost:5432/jobsdb
    # For MySQL use e.g. mysql+pymysql://user:pass@localhost:3306/jobsdb
    database_url: str = "sqlite:///./jobs.db"

    # --- Scraping ---
    selenium_headless: bool = True
    scrape_page_limit: int = 3          # pages per source, per run
    scrape_timeout_seconds: int = 20

    # --- Scheduler ---
    scrape_interval_hours: int = 1
    enable_scheduler: bool = True

    # --- Email notifications ---
    enable_email_notifications: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_email_from: str = ""
    notify_email_to: str = ""

    # --- API ---
    api_title: str = "Job Listings Aggregator"
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
