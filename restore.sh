#!/usr/bin/env bash
# Restore a PostgreSQL backup (created by backup.sh) into the running
# postgres container. Usage: ./restore.sh <path-to-backup-file>
set -euo pipefail

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-file>" >&2
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
    echo "FAIL: backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "Restoring '${BACKUP_FILE}' into database '${DB_NAME}'..."
# --clean drops existing objects first so the restore reflects exactly
# what is in the dump file (needed to prove older data comes back).
docker compose -p "$PROJECT" exec -T postgres \
    pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists < "$BACKUP_FILE"

echo "PASS: restore command completed"
