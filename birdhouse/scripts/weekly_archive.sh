#!/usr/bin/env bash
# Archive birdhouse photos older than 7 days into weekly zip files.
# Intended to run via cron weekly: 0 1 * * 0 /home/x/birdhouse/scripts/weekly_archive.sh

set -euo pipefail

PHOTOS_DIR="/srv/birdhouse-photos"
ARCHIVE_DIR="/srv/birdhouse-photos/archives"
LOG="/srv/birdhouse-photos/archive.log"

mkdir -p "$ARCHIVE_DIR"

echo "$(date) — Starting weekly archive" >> "$LOG"

# Find photos older than 7 days
OLD_FILES=$(find "$PHOTOS_DIR" -maxdepth 1 -name "*.jpg" -mtime +7 -type f | sort)

if [ -z "$OLD_FILES" ]; then
    echo "$(date) — No photos older than 7 days, nothing to archive" >> "$LOG"
    exit 0
fi

# Group by week (use the Monday of each photo's week)
declare -A WEEKS
for f in $OLD_FILES; do
    basename=$(basename "$f")
    # Extract date from filename: bird_YYYYMMDD_HHMMSS.jpg or motion_YYYYMMDD_HHMMSS.jpg
    file_date=$(echo "$basename" | grep -oP '\d{8}' | head -1)
    if [ -z "$file_date" ]; then
        continue
    fi
    # Get the Monday of that week
    week_start=$(date -d "${file_date:0:4}-${file_date:4:2}-${file_date:6:2} last monday" +%Y%m%d 2>/dev/null || echo "$file_date")
    WEEKS["$week_start"]+="$f "
done

TOTAL=0
for week in "${!WEEKS[@]}"; do
    files=(${WEEKS[$week]})
    count=${#files[@]}
    archive="$ARCHIVE_DIR/week_${week}_${count}photos.zip"

    zip -j -q "$archive" "${files[@]}"
    rm "${files[@]}"

    TOTAL=$((TOTAL + count))
    echo "$(date) — Archived $count photos into $archive" >> "$LOG"
done

echo "$(date) — Archive complete: $TOTAL photos archived" >> "$LOG"
