#!/usr/bin/env bash
# =============================================================================
# backup_db.sh — SQLite database backup for Strype Cloud
# =============================================================================
# Creates a consistent backup using SQLite's .backup command (safe with WAL mode).
#
# Usage:
#   bash scripts/backup_db.sh [/path/to/strype.db] [/path/to/backup/dir]
#
# Cron example (daily at 3 AM):
#   0 3 * * * /app/scripts/backup_db.sh /app/backend/data/strype.db /app/backups
# =============================================================================

set -euo pipefail

DB="${1:-./backend/data/strype.db}"
DEST="${2:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"

if [ ! -f "$DB" ]; then
    echo "ERROR: Database not found at: $DB"
    exit 1
fi

mkdir -p "$DEST"

STAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="$DEST/strype_${STAMP}.db"

echo "Backing up $DB → $OUTFILE ..."
sqlite3 "$DB" ".backup '$OUTFILE'"

SIZE=$(du -h "$OUTFILE" | cut -f1)
echo "Backup complete: $OUTFILE ($SIZE)"

# Prune old backups
PRUNED=$(find "$DEST" -name "strype_*.db" -mtime +${KEEP_DAYS} -delete -print | wc -l)
if [ "$PRUNED" -gt 0 ]; then
    echo "Pruned $PRUNED backup(s) older than ${KEEP_DAYS} days"
fi
