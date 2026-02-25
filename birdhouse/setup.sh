#!/usr/bin/env bash
# Birdhouse Camera — Deploy to Raspberry Pi
#
# Run from your Mac:
#   bash birdhouse/setup.sh
#
# This copies the project to the Pi and installs the systemd services.

set -euo pipefail

PI_HOST="rafablazer@10.0.0.102"
REMOTE_DIR="/home/rafablazer/birdhouse"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Copying project files to Pi..."
rsync -avz --exclude '__pycache__' --exclude '*.pyc' \
  "$SCRIPT_DIR/" "$PI_HOST:$REMOTE_DIR/"

echo "==> Setting up on Pi..."
ssh "$PI_HOST" bash <<'REMOTE'
set -euo pipefail

PROJECT="/home/rafablazer/birdhouse"

# Create photos dir and mount point
mkdir -p "$PROJECT/photos"
sudo mkdir -p /mnt/birdhouse-cloud/photos

# Install systemd services
sudo cp "$PROJECT/services/birdhouse-capture.service" /etc/systemd/system/
sudo cp "$PROJECT/services/birdhouse-web.service"     /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable birdhouse-capture birdhouse-web

echo ""
echo "==> Services installed and enabled."
echo "    Start them now with:"
echo "      sudo systemctl start birdhouse-capture"
echo "      sudo systemctl start birdhouse-web"
echo ""
echo "    Web portal: http://10.0.0.102:5000"
REMOTE

echo "==> Done!"
