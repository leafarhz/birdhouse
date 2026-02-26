#!/usr/bin/env python3
"""Birdhouse Camera — Flask web portal (runs on Ubuntu storage server)."""

import json
import os
from datetime import datetime

from flask import Flask, render_template, jsonify, request, send_from_directory

app = Flask(__name__)

PHOTOS_DIR = "/srv/birdhouse-photos"
TIMELAPSE_DIR = os.path.join(PHOTOS_DIR, "timelapses")
STATS_FILE = os.path.join(PHOTOS_DIR, "pi_stats.json")


# ── helpers ──────────────────────────────────────────────────────────

def _photo_list(date_filter=None):
    """Return list of photo filenames sorted newest-first, optionally filtered by date."""
    if not os.path.isdir(PHOTOS_DIR):
        return []
    photos = [f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")]
    if date_filter:
        # date_filter is "YYYYMMDD"
        photos = [f for f in photos if date_filter in f]
    photos.sort(reverse=True)
    return photos


def _motion_photos(date_filter=None):
    """Return only motion-detected photos."""
    photos = _photo_list(date_filter)
    return [f for f in photos if f.startswith("motion_")]


def _timelapse_list():
    """Return list of timelapse video filenames sorted newest-first."""
    if not os.path.isdir(TIMELAPSE_DIR):
        return []
    videos = [f for f in os.listdir(TIMELAPSE_DIR) if f.endswith(".mp4")]
    videos.sort(reverse=True)
    return videos


def _available_dates():
    """Return sorted list of dates (YYYY-MM-DD) that have photos."""
    if not os.path.isdir(PHOTOS_DIR):
        return []
    dates = set()
    for f in os.listdir(PHOTOS_DIR):
        if not f.endswith(".jpg"):
            continue
        # Extract YYYYMMDD from bird_YYYYMMDD_HHMMSS.jpg or motion_YYYYMMDD_HHMMSS.jpg
        parts = f.split("_")
        if len(parts) >= 2 and len(parts[1]) == 8 and parts[1].isdigit():
            d = parts[1]
            dates.add(f"{d[:4]}-{d[4:6]}-{d[6:8]}")
    return sorted(dates, reverse=True)


def _pi_stats():
    """Read the latest Pi stats JSON written by the capture script."""
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {}


# ── routes ───────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    photos = _photo_list()
    latest = photos[0] if photos else None
    motion = _motion_photos()
    stats = _pi_stats()
    stats["photo_count"] = len(photos)
    stats["motion_count"] = len(motion)
    return render_template("index.html",
                           page="dashboard",
                           latest=latest,
                           stats=stats,
                           recent_motion=motion[:6])


@app.route("/gallery")
def gallery():
    date_filter = request.args.get("date", "")
    date_yyyymmdd = date_filter.replace("-", "") if date_filter else None
    photos = _photo_list(date_yyyymmdd)
    dates = _available_dates()
    stats = _pi_stats()
    stats["photo_count"] = len(_photo_list())
    return render_template("index.html",
                           page="gallery",
                           photos=photos,
                           dates=dates,
                           selected_date=date_filter,
                           stats=stats)


@app.route("/motion")
def motion():
    date_filter = request.args.get("date", "")
    date_yyyymmdd = date_filter.replace("-", "") if date_filter else None
    photos = _motion_photos(date_yyyymmdd)
    dates = _available_dates()
    return render_template("index.html",
                           page="motion",
                           photos=photos,
                           dates=dates,
                           selected_date=date_filter)


@app.route("/timelapses")
def timelapses():
    videos = _timelapse_list()
    return render_template("index.html", page="timelapses", videos=videos)


@app.route("/photos/<filename>")
def serve_photo(filename):
    return send_from_directory(PHOTOS_DIR, filename)


@app.route("/timelapses/<filename>")
def serve_timelapse(filename):
    return send_from_directory(TIMELAPSE_DIR, filename)


# ── API endpoints ────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    stats = _pi_stats()
    stats["photo_count"] = len(_photo_list())
    stats["motion_count"] = len(_motion_photos())
    return jsonify(stats)


@app.route("/api/latest")
def api_latest():
    photos = _photo_list()
    latest = photos[0] if photos else None
    return jsonify({"latest": latest})


# ── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
