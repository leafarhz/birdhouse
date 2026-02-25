#!/usr/bin/env python3
"""Birdhouse Camera — capture loop.

Takes photos at a configurable interval using libcamera-still,
optionally copies them to a mounted storage location, and cleans up
old local files to conserve disk space.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime

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


def take_photo(width, height, quality):
    """Capture a JPEG via libcamera-still. Returns the file path or None."""
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bird_{timestamp}.jpg"
    filepath = os.path.join(PHOTOS_DIR, filename)

    cmd = [
        "libcamera-still",
        "--width", str(width),
        "--height", str(height),
        "--quality", str(quality),
        "--nopreview",
        "--immediate",
        "--shutter", "1000000",   # 1s exposure — needed for dark birdhouse interior
        "--gain", "8",            # 8x analog gain
        "-o", filepath,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        log.info("Captured %s (%dx%d, q%d)", filename, width, height, quality)
        return filepath
    except subprocess.CalledProcessError as exc:
        log.error("libcamera-still failed: %s", exc.stderr.decode().strip())
    except subprocess.TimeoutExpired:
        log.error("libcamera-still timed out")
    return None


def gather_pi_stats():
    """Collect system stats from the Pi."""
    stats = {"timestamp": datetime.now().isoformat()}

    # CPU temperature
    try:
        temp = open("/sys/class/thermal/thermal_zone0/temp").read().strip()
        stats["cpu_temp"] = f"{int(temp) / 1000:.1f} C"
    except Exception:
        stats["cpu_temp"] = "N/A"

    # Uptime
    try:
        out = subprocess.check_output(["uptime", "-p"], text=True).strip()
        stats["uptime"] = out.replace("up ", "")
    except Exception:
        stats["uptime"] = "N/A"

    # Disk usage
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

    # WiFi signal
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


def upload_photo(filepath, upload_path):
    """Copy photo + Pi stats JSON to the upload destination. Returns True on success."""
    if not os.path.isdir(upload_path):
        log.warning("Upload path %s not available — skipping upload", upload_path)
        return False

    try:
        shutil.copy2(filepath, upload_path)
        log.info("Uploaded %s -> %s", os.path.basename(filepath), upload_path)

        # Write Pi stats alongside photos
        stats = gather_pi_stats()
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


def run():
    """Main capture loop."""
    log.info("Birdhouse capture starting")

    while True:
        settings = load_settings()
        interval = settings["capture_interval"]
        width = settings["resolution_width"]
        height = settings["resolution_height"]
        quality = settings["jpeg_quality"]

        filepath = take_photo(width, height, quality)

        if filepath:
            if settings["upload_enabled"]:
                uploaded = upload_photo(filepath, settings["upload_path"])
                if uploaded:
                    # Remove local copy after successful upload
                    os.remove(filepath)
                    log.info("Removed local copy after upload")

            cleanup_old_photos(settings["max_local_photos"])

        log.info("Sleeping %d seconds until next capture", interval)
        time.sleep(interval)


if __name__ == "__main__":
    run()
