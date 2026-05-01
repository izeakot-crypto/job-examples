#!/bin/bash
# Daily PostgreSQL backup for seo_articles.
# Stores gzipped dumps in /var/backups/seo_articles, keeps last 30 days.
set -euo pipefail

BACKUP_DIR=/var/backups/seo_articles
DB_NAME=seo_articles
DB_USER=seo_user
CREDS_FILE=/root/.seo_db_creds
TIMESTAMP=$(date +%Y%m%d-%H%M)
OUTFILE="$BACKUP_DIR/seo_articles-$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [ ! -f "$CREDS_FILE" ]; then
    echo "ERROR: $CREDS_FILE not found" >&2
    exit 1
fi

DB_PASS=$(grep ^DB_PASSWORD= "$CREDS_FILE" | cut -d= -f2)
export PGPASSWORD="$DB_PASS"

pg_dump -h localhost -U "$DB_USER" -d "$DB_NAME" -F c | gzip > "$OUTFILE"

# Verify file is non-empty
if [ ! -s "$OUTFILE" ]; then
    echo "ERROR: backup file is empty: $OUTFILE" >&2
    rm -f "$OUTFILE"
    exit 1
fi

# Prune backups older than 30 days
find "$BACKUP_DIR" -name 'seo_articles-*.sql.gz' -type f -mtime +30 -delete

echo "Backup complete: $OUTFILE ($(du -h "$OUTFILE" | cut -f1))"
