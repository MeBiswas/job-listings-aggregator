"""
Duplicate-postings handling.

Strategy: build a stable fingerprint from normalized (title, company, apply_url).
- Normalizing (lowercase, strip whitespace/punctuation) catches trivial
  differences like "Senior Python Developer" vs "senior python developer ".
- Hashing keeps the DB unique-constraint column short and index-friendly.
- Because `dedup_hash` has a UNIQUE constraint at the DB layer, even a race
  between two scrapers writing at once can't create a duplicate row.
"""
import hashlib
import re


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_dedup_hash(title: str, company: str, apply_url: str) -> str:
    # apply_url is normalized by stripping query params, since the same job
    # is often linked with different tracking params across scrapes.
    clean_url = (apply_url or "").split("?")[0].rstrip("/").lower()
    fingerprint = f"{_normalize(title)}|{_normalize(company)}|{clean_url}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
