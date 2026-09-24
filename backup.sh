#!/usr/bin/env bash
# Create a PostgreSQL backup using pg_dump inside the postgres container,
# and save it to ./backups/ on the host (git-ignored).
set -euo pipefail

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"
BACKUP_DIR="./backups"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/barq_tasks_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

echo "Backing up database '${DB_NAME}' from container 'postgres'..."
docker compose -p "$PROJECT" exec -T postgres \
    pg_dump -U "$DB_USER" -d "$DB_NAME" -F custom > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "FAIL: backup file is empty or was not created: $BACKUP_FILE" >&2
    exit 1
fi

echo "PASS: backup written to $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
echo "$BACKUP_FILE"
