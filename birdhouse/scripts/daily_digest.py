#!/usr/bin/env python3
"""Birdhouse Camera — Daily email digest.

Sends a summary of the day's activity: photo count, motion events,
Pi health stats, and attaches the best motion-detected photo (if any).

Run via cron at 8pm: 0 20 * * * python3 /home/x/birdhouse/scripts/daily_digest.py

Configure SMTP settings below or via environment variables.
"""

import glob
import json
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

PHOTOS_DIR = "/srv/birdhouse-photos"
STATS_FILE = os.path.join(PHOTOS_DIR, "pi_stats.json")

# ── Email config (set via environment or edit here) ──────────────────
SMTP_HOST = os.environ.get("BIRDHOUSE_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("BIRDHOUSE_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("BIRDHOUSE_SMTP_USER", "")
SMTP_PASS = os.environ.get("BIRDHOUSE_SMTP_PASS", "")
EMAIL_TO = os.environ.get("BIRDHOUSE_EMAIL_TO", "")
EMAIL_FROM = os.environ.get("BIRDHOUSE_EMAIL_FROM", SMTP_USER)


def get_todays_photos():
    """Get lists of today's regular and motion photos."""
    today = datetime.now().strftime("%Y%m%d")
    all_photos = sorted(glob.glob(os.path.join(PHOTOS_DIR, f"*_{today}_*.jpg")))
    regular = [p for p in all_photos if os.path.basename(p).startswith("bird_")]
    motion = [p for p in all_photos if os.path.basename(p).startswith("motion_")]
    return regular, motion


def get_pi_stats():
    """Read latest Pi stats."""
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE) as f:
            return json.load(f)
    return {}


def build_digest():
    """Build the digest email content."""
    regular, motion = get_todays_photos()
    stats = get_pi_stats()
    today = datetime.now().strftime("%B %d, %Y")

    total = len(regular) + len(motion)
    motion_count = len(motion)

    body = f"""Birdhouse Camera — Daily Digest for {today}
{'=' * 50}

Photos captured today: {total}
  Regular:  {len(regular)}
  Motion:   {motion_count}

Pi Status:
  CPU Temp:    {stats.get('cpu_temp', 'N/A')}
  Uptime:      {stats.get('uptime', 'N/A')}
  Disk Free:   {stats.get('disk_free', 'N/A')} ({stats.get('disk_pct', 'N/A')} used)
  WiFi Signal: {stats.get('wifi_signal', 'N/A')}
"""

    if motion_count > 0:
        body += f"\nMotion was detected {motion_count} time(s) today!\n"
    else:
        body += "\nNo motion detected today. The birds are being shy.\n"

    # Pick the best motion photo to attach (largest file = most detail)
    attachment = None
    if motion:
        attachment = max(motion, key=os.path.getsize)
        body += f"\nAttached: {os.path.basename(attachment)}\n"

    return body, attachment


def send_email(subject, body, attachment_path=None):
    """Send the digest email."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO]):
        print("Email not configured — printing digest to stdout instead:\n")
        print(body)
        if attachment_path:
            print(f"(Would attach: {attachment_path})")
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            img = MIMEImage(f.read(), name=os.path.basename(attachment_path))
        msg.attach(img)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())

    print(f"Digest sent to {EMAIL_TO}")


if __name__ == "__main__":
    today = datetime.now().strftime("%B %d")
    subject = f"Birdhouse Camera — {today} Digest"
    body, attachment = build_digest()
    send_email(subject, body, attachment)
