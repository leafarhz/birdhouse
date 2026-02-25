# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Birdhouse Camera — a Raspberry Pi-powered camera system designed to be mounted on a birdhouse for wildlife observation. The system captures photos/video of birds and uploads them to cloud storage.

### Goals
- Capture images/video of birds visiting the birdhouse
- Solar-powered with battery backup for continuous outdoor operation
- Automatically send photos to a cloud drive
- Low-maintenance, weather-resistant setup

## Hardware

- **Raspberry Pi 4** (on local network at `10.0.0.102`)
- **Camera module:** IMX219 (detected, `libcamera-still` confirmed working)
- **Solar panel + 38800mAh battery bank** for off-grid power
- **Birdhouse enclosure**

## Raspberry Pi Access

- **Host:** 10.0.0.102
- **Username:** rafablazer
- **SSH:** `ssh rafablazer@10.0.0.102`
- **OS:** Raspberry Pi OS Bookworm (Debian 12)
- **SD card device (when mounted on Mac):** disk6 (bootfs = disk6s1, rootfs = disk6s2)
- **Python:** 3.11, Flask 2.2, Pillow 9.4, requests pre-installed

## Project Structure

```
birdhouse/
├── capture.py          # Camera capture loop (libcamera-still + upload)
├── config.py           # Settings management (JSON-backed)
├── web/
│   ├── app.py          # Flask web portal (dashboard, gallery, logs, settings)
│   ├── templates/
│   │   └── index.html
│   └── static/
│       └── style.css
├── services/
│   ├── birdhouse-capture.service   # systemd unit for capture loop
│   └── birdhouse-web.service       # systemd unit for Flask on :5000
├── photos/             # Local photo storage (auto-cleaned after upload)
└── setup.sh            # Deploy script (rsync to Pi + install services)
```

## Deployment

From Mac: `bash birdhouse/setup.sh` — copies files to Pi and installs systemd services.

## Storage

- **Upload path:** `/mnt/birdhouse-cloud/photos` (mount point for network storage)
- Storage backend TBD — WD My Cloud Home or local server via SMB/CIFS

## Status

Software implementation complete. Next steps:
- Deploy to Pi with `setup.sh`
- Configure network storage mount
- Start services and verify end-to-end capture + upload
