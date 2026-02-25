"""Birdhouse Camera configuration."""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")
LOG_FILE = os.path.join(BASE_DIR, "birdhouse.log")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Defaults
DEFAULTS = {
    "capture_interval": 120,       # seconds between captures
    "resolution_width": 1920,
    "resolution_height": 1080,
    "jpeg_quality": 85,
    "upload_enabled": True,
    "upload_path": "/mnt/birdhouse-cloud",
    "max_local_photos": 100,       # keep at most this many locally before cleanup
    "web_port": 5000,
}


def load_settings():
    """Load settings from disk, falling back to defaults."""
    settings = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            saved = json.load(f)
        settings.update(saved)
    return settings


def save_settings(settings):
    """Persist settings to disk."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
