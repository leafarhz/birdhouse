#!/usr/bin/env bash
# Test different brightness settings on the birdhouse camera
# Run from Mac: bash test_brightness.sh

set -euo pipefail

PI="rafablazer@10.0.0.102"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Taking 3 test photos on the Pi..."

ssh "$PI" bash <<'REMOTE'
set -euo pipefail

echo "[1/3] Long exposure (1s) + 8x gain..."
libcamera-still --width 1920 --height 1080 --quality 85 --nopreview --immediate \
  --shutter 1000000 --gain 8 -o /home/rafablazer/test_bright1.jpg

echo "[2/3] Max exposure (2s) + 16x gain..."
libcamera-still --width 1920 --height 1080 --quality 85 --nopreview --immediate \
  --shutter 2000000 --gain 16 -o /home/rafablazer/test_bright2.jpg

echo "[3/3] Auto-exposure with +2 EV compensation..."
libcamera-still --width 1920 --height 1080 --quality 85 --nopreview \
  --timeout 5000 --ev +2 -o /home/rafablazer/test_bright3.jpg

echo "Done capturing!"
REMOTE

echo "==> Copying photos to Mac..."
scp "$PI":/home/rafablazer/test_bright{1,2,3}.jpg "$LOCAL_DIR/"

echo ""
echo "==> All done! Photos saved to:"
echo "    $LOCAL_DIR/test_bright1.jpg  (1s exposure, 8x gain)"
echo "    $LOCAL_DIR/test_bright2.jpg  (2s exposure, 16x gain)"
echo "    $LOCAL_DIR/test_bright3.jpg  (auto +2 EV)"
