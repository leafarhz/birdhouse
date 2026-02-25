#!/usr/bin/env python3
"""Birdhouse Camera — Flask web portal (runs on Ubuntu storage server)."""

import json
import os

from flask import Flask, render_template, jsonify, request, send_from_directory

app = Flask(__name__)

PHOTOS_DIR = "/srv/birdhouse-photos"
STATS_FILE = os.path.join(PHOTOS_DIR, "pi_stats.json")


# ── helpers ──────────────────────────────────────────────────────────

def _photo_list():
    """Return list of photo filenames sorted newest-first."""
    if not os.path.isdir(PHOTOS_DIR):
        return []
    photos = [f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")]
    photos.sort(reverse=True)
    return photos


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
    stats = _pi_stats()
    stats["photo_count"] = len(photos)
    return render_template("index.html", latest=latest, stats=stats)


@app.route("/gallery")
def gallery():
    photos = _photo_list()
    stats = _pi_stats()
    stats["photo_count"] = len(photos)
    return render_template("index.html", gallery=True, photos=photos, stats=stats)


@app.route("/photos/<filename>")
def serve_photo(filename):
    return send_from_directory(PHOTOS_DIR, filename)


# ── API endpoints ────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    stats = _pi_stats()
    stats["photo_count"] = len(_photo_list())
    return jsonify(stats)


# ── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
