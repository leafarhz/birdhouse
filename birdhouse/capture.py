#!/usr/bin/env python3
"""Birdhouse Camera — capture loop.

Takes photos at a configurable interval using libcamera-still,
detects motion between frames, adapts capture rate, stamps timestamps,
uploads to network storage, and cleans up old local files.
"""

import json
import logging
import math
import os
import shutil
import subprocess
import time
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import PHOTOS_DIR, LOG_FILE, load_settings

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("capture")

# Also log to stdout so journalctl shows output
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
log.addHandler(console)


# ── Solar calculations (Colorado) ────────────────────────────────────

LATITUDE = 39.74
LONGITUDE = -104.99


def _sunrise_sunset():
    """Calculate sunrise/sunset hours for Colorado.

    Returns (sunrise_hour, sunset_hour) as floats in local time.
    Accounts for seasonal variation — ~15h sun in summer, ~9h in winter.
    """
    now = datetime.now()
    day_of_year = now.timetuple().tm_yday

    declination = math.radians(
        -23.44 * math.cos(math.radians(360 / 365 * (day_of_year + 10)))
    )

    lat_rad = math.radians(LATITUDE)
    cos_hour = -math.tan(lat_rad) * math.tan(declination)
    cos_hour = max(-1, min(1, cos_hour))
    hour_angle = math.degrees(math.acos(cos_hour))

    solar_noon_utc = 12.0 - LONGITUDE / 15.0
    solar_noon_local = solar_noon_utc - 7  # MST offset

    sunrise = solar_noon_local - hour_angle / 15.0
    sunset = solar_noon_local + hour_angle / 15.0

    return sunrise, sunset


def _is_daytime():
    """Return True if sun is up in Colorado."""
    sunrise, sunset = _sunrise_sunset()
    hour = datetime.now().hour + datetime.now().minute / 60.0
    return sunrise <= hour <= sunset


# ── Timestamp overlay ────────────────────────────────────────────────

def _stamp_photo(img, text):
    """Burn a timestamp string onto the bottom-left of a grayscale image."""
    draw = ImageDraw.Draw(img)

    # Try to load a monospace font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 24)
    except (IOError, OSError):
        font = ImageFont.load_default()

    # Text position: bottom-left with padding
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = 10
    y = img.height - text_h - 14

    # Draw dark background rectangle for readability
    draw.rectangle([x - 4, y - 4, x + text_w + 8, y + text_h + 8], fill=0)
    draw.text((x, y), text, fill=255, font=font)

    return img


# ── Motion detection ─────────────────────────────────────────────────

# Percentage of pixels that must differ to count as motion
MOTION_THRESHOLD_PCT = 3.0
# Per-pixel intensity difference to count as "changed"
PIXEL_DIFF_THRESHOLD = 30
# How many rapid-fire captures after motion is detected
MOTION_BURST_COUNT = 15
# Interval during motion burst (seconds)
MOTION_BURST_INTERVAL = 10

# Keep the previous frame in memory for comparison
_prev_frame = None


def detect_motion(current_path):
    """Compare current photo to previous frame. Returns True if motion detected."""
    global _prev_frame

    current = np.array(Image.open(current_path))

    if _prev_frame is None:
        _prev_frame = current
        return False

    # Compute absolute difference
    diff = np.abs(current.astype(np.int16) - _prev_frame.astype(np.int16))
    changed_pixels = np.count_nonzero(diff > PIXEL_DIFF_THRESHOLD)
    total_pixels = diff.size
    pct_changed = (changed_pixels / total_pixels) * 100

    _prev_frame = current

    motion = pct_changed > MOTION_THRESHOLD_PCT
    if motion:
        log.info("Motion detected! %.1f%% pixels changed", pct_changed)
    return motion


# ── Photo capture ────────────────────────────────────────────────────

def take_photo(width, height, quality, motion_tag=False):
    """Capture a JPEG via libcamera-still. Returns the file path or None."""
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    prefix = "motion" if motion_tag else "bird"
    filename = f"{prefix}_{timestamp}.jpg"
    filepath = os.path.join(PHOTOS_DIR, filename)

    cmd = [
        "libcamera-still",
        "--width", str(width),
        "--height", str(height),
        "--quality", str(quality),
        "--nopreview",
        "-o", filepath,
    ]

    if _is_daytime():
        cmd += ["--timeout", "5000", "--awb", "tungsten"]
        mode = "day"
    else:
        cmd += ["--immediate", "--shutter", "1000000", "--gain", "8", "--awb", "tungsten"]
        mode = "night"

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)

        # Convert to grayscale
        img = Image.open(filepath).convert("L")

        # Stamp timestamp + mode
        stamp_text = now.strftime("%Y-%m-%d  %H:%M:%S") + f"  [{mode}]"
        if motion_tag:
            stamp_text += "  *MOTION*"
        img = _stamp_photo(img, stamp_text)

        img.save(filepath, quality=quality)
        log.info("Captured %s (%s mode)", filename, mode)
        return filepath
    except subprocess.CalledProcessError as exc:
        log.error("libcamera-still failed: %s", exc.stderr.decode().strip())
    except subprocess.TimeoutExpired:
        log.error("libcamera-still timed out")
    return None


# ── Stats + Upload ───────────────────────────────────────────────────

def gather_pi_stats(motion_today=0):
    """Collect system stats from the Pi."""
    stats = {"timestamp": datetime.now().isoformat(), "motion_events_today": motion_today}

    try:
        temp = open("/sys/class/thermal/thermal_zone0/temp").read().strip()
        stats["cpu_temp"] = f"{int(temp) / 1000:.1f} C"
    except Exception:
        stats["cpu_temp"] = "N/A"

    try:
        out = subprocess.check_output(["uptime", "-p"], text=True).strip()
        stats["uptime"] = out.replace("up ", "")
    except Exception:
        stats["uptime"] = "N/A"

    try:
        out = subprocess.check_output(
            ["df", "-h", "--output=avail,pcent", "/home"], text=True
        )
        lines = out.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            stats["disk_free"] = parts[0]
            stats["disk_pct"] = parts[1]
    except Exception:
        stats["disk_free"] = "N/A"
        stats["disk_pct"] = "N/A"

    try:
        out = subprocess.check_output(
            ["iwconfig", "wlan0"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.split("\n"):
            if "Signal level" in line:
                stats["wifi_signal"] = line.split("Signal level=")[-1].strip()
                break
        else:
            stats["wifi_signal"] = "N/A"
    except Exception:
        stats["wifi_signal"] = "N/A"

    return stats


def upload_photo(filepath, upload_path, motion_today=0):
    """Copy photo + Pi stats JSON to the upload destination."""
    if not os.path.isdir(upload_path):
        log.warning("Upload path %s not available — skipping upload", upload_path)
        return False

    try:
        shutil.copy2(filepath, upload_path)
        log.info("Uploaded %s -> %s", os.path.basename(filepath), upload_path)

        stats = gather_pi_stats(motion_today)
        stats_path = os.path.join(upload_path, "pi_stats.json")
        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2)
        log.info("Updated pi_stats.json")

        return True
    except OSError as exc:
        log.error("Upload failed: %s", exc)
        return False


def cleanup_old_photos(max_keep):
    """Delete oldest local photos when count exceeds max_keep."""
    if not os.path.isdir(PHOTOS_DIR):
        return
    photos = sorted(
        (os.path.join(PHOTOS_DIR, f) for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")),
        key=os.path.getmtime,
    )
    while len(photos) > max_keep:
        oldest = photos.pop(0)
        os.remove(oldest)
        log.info("Cleaned up %s", os.path.basename(oldest))


# ── Main loop ────────────────────────────────────────────────────────

def run():
    """Main capture loop with motion detection and adaptive interval."""
    log.info("Birdhouse capture starting")

    motion_burst_remaining = 0
    motion_count_today = 0
    current_day = datetime.now().date()

    while True:
        settings = load_settings()
        width = settings["resolution_width"]
        height = settings["resolution_height"]
        quality = settings["jpeg_quality"]

        # Reset daily motion counter at midnight
        today = datetime.now().date()
        if today != current_day:
            log.info("New day — resetting motion counter (yesterday: %d events)", motion_count_today)
            motion_count_today = 0
            current_day = today

        # Determine if we're in a motion burst
        is_burst = motion_burst_remaining > 0
        motion_tag = is_burst

        filepath = take_photo(width, height, quality, motion_tag=motion_tag)

        if filepath:
            # Check for motion
            motion = detect_motion(filepath)
            if motion and not is_burst:
                motion_count_today += 1
                motion_burst_remaining = MOTION_BURST_COUNT
                log.info("Starting motion burst (%d rapid captures)", MOTION_BURST_COUNT)

            if settings["upload_enabled"]:
                uploaded = upload_photo(filepath, settings["upload_path"], motion_count_today)
                if uploaded:
                    os.remove(filepath)
                    log.info("Removed local copy after upload")

            cleanup_old_photos(settings["max_local_photos"])

        # Adaptive interval
        if motion_burst_remaining > 0:
            motion_burst_remaining -= 1
            interval = MOTION_BURST_INTERVAL
            log.info("Motion burst: %d captures remaining (every %ds)", motion_burst_remaining, interval)
        else:
            interval = settings["capture_interval"]

        log.info("Sleeping %d seconds until next capture", interval)
        time.sleep(interval)


if __name__ == "__main__":
    run()
