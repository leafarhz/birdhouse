#!/usr/bin/env bash
# Generate a timelapse video from the day's birdhouse photos.
# Intended to run via cron at midnight: 0 0 * * * /home/x/birdhouse/scripts/daily_timelapse.sh
#
# Stitches all JPEGs from yesterday into an MP4 at 12fps.

set -euo pipefail

PHOTOS_DIR="/srv/birdhouse-photos"
TIMELAPSE_DIR="/srv/birdhouse-photos/timelapses"
LOG="/srv/birdhouse-photos/timelapse.log"

# Yesterday's date (the day we're making a timelapse for)
DATE=$(date -d "yesterday" +%Y%m%d)
HUMAN_DATE=$(date -d "yesterday" +%Y-%m-%d)

mkdir -p "$TIMELAPSE_DIR"

echo "$(date) — Starting timelapse for $HUMAN_DATE" >> "$LOG"

# Collect photos from yesterday (bird_YYYYMMDD_*.jpg and motion_YYYYMMDD_*.jpg)
TMPDIR=$(mktemp -d)
COUNT=0
for f in "$PHOTOS_DIR"/bird_${DATE}_*.jpg "$PHOTOS_DIR"/motion_${DATE}_*.jpg; do
    [ -f "$f" ] || continue
    COUNT=$((COUNT + 1))
    # Symlink with sequential numbering for ffmpeg
    ln -s "$f" "$TMPDIR/$(printf 'frame_%05d.jpg' $COUNT)"
done

if [ "$COUNT" -lt 2 ]; then
    echo "$(date) — Only $COUNT photos for $HUMAN_DATE, skipping timelapse" >> "$LOG"
    rm -rf "$TMPDIR"
    exit 0
fi

OUTPUT="$TIMELAPSE_DIR/timelapse_${DATE}.mp4"

ffmpeg -y -framerate 12 -i "$TMPDIR/frame_%05d.jpg" \
    -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
    "$OUTPUT" >> "$LOG" 2>&1

rm -rf "$TMPDIR"

echo "$(date) — Timelapse complete: $OUTPUT ($COUNT frames)" >> "$LOG"
