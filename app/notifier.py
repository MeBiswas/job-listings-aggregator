"""
Sends a digest email listing newly discovered jobs after a scrape run.

Disabled by default (ENABLE_EMAIL_NOTIFICATIONS=false) so the project runs
with zero SMTP configuration out of the box. Turn it on by setting:

  ENABLE_EMAIL_NOTIFICATIONS=true
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=you@gmail.com
  SMTP_PASSWORD=your-app-password      # use an app password, not your real password
  NOTIFY_EMAIL_FROM=you@gmail.com
  NOTIFY_EMAIL_TO=you@gmail.com,teammate@gmail.com
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)


def _build_html(jobs) -> str:
    rows = ""
    for job in jobs:
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;"><b>{job.title}</b></td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{job.company}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{job.location or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{job.experience or '-'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">
            <a href="{job.apply_url}">Apply</a>
          </td>
        </tr>
        """
    return f"""
    <html><body style="font-family:Arial,sans-serif;">
      <h2>{len(jobs)} new job(s) found</h2>
      <table style="border-collapse:collapse;width:100%;">
        <tr style="background:#f5f5f5;">
          <th style="padding:8px;text-align:left;">Title</th>
          <th style="padding:8px;text-align:left;">Company</th>
          <th style="padding:8px;text-align:left;">Location</th>
          <th style="padding:8px;text-align:left;">Experience</th>
          <th style="padding:8px;text-align:left;">Link</th>
        </tr>
        {rows}
      </table>
    </body></html>
    """


def send_new_jobs_email(jobs: List) -> None:
    if not jobs:
        return
    if not settings.enable_email_notifications:
        logger.info("Email notifications disabled; skipping send for %d new jobs.", len(jobs))
        return
    if not settings.smtp_host or not settings.notify_email_to:
        logger.warning("Email notifications enabled but SMTP_HOST/NOTIFY_EMAIL_TO not set; skipping.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Aggregator: {len(jobs)} new job(s) found"
    msg["From"] = settings.notify_email_from or settings.smtp_user
    recipients = [addr.strip() for addr in settings.notify_email_to.split(",") if addr.strip()]
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(_build_html(jobs), "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(msg["From"], recipients, msg.as_string())

    logger.info("Sent new-jobs email to %s (%d jobs)", recipients, len(jobs))
