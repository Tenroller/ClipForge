#!/usr/bin/env bash
# =============================================================================
# ClipForge - PostgreSQL Database Backup Script
# =============================================================================
#
# Creates compressed, timestamped backups of the PostgreSQL database running
# inside the Docker "postgres" service container.
#
# Usage:
#   ./scripts/backup-db.sh                  # Use defaults
#   ./scripts/backup-db.sh -d /my/backups   # Custom backup directory
#   ./scripts/backup-db.sh -r 14            # Keep 14 days of backups
#   ./scripts/backup-db.sh -c my-compose    # Custom compose project name
#
# Cron example (daily at 2:00 AM):
#   0 2 * * * cd /path/to/ClipForge && ./scripts/backup-db.sh >> /var/log/clipforge-backup.log 2>&1
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Default configuration (override with flags or environment variables)
# ---------------------------------------------------------------------------
BACKUP_DIR="${BACKUP_DIR:-./backups/db}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-}"
DB_NAME="${DB_NAME:-videohelper}"
DB_USER="${DB_USER:-videohelper_user}"
DOCKER_SERVICE="${DOCKER_SERVICE:-postgres}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILENAME="clipforge_${DB_NAME}_${TIMESTAMP}.sql.gz"

# ---------------------------------------------------------------------------
# Parse command-line arguments
# ---------------------------------------------------------------------------
usage() {
    echo "Usage: $0 [-d backup_dir] [-r retention_days] [-c compose_project] [-n db_name] [-u db_user] [-s docker_service] [-h]"
    echo ""
    echo "Options:"
    echo "  -d  Backup directory (default: ./backups/db)"
    echo "  -r  Retention in days (default: 7)"
    echo "  -c  Docker Compose project name (default: auto-detect)"
    echo "  -n  Database name (default: videohelper)"
    echo "  -u  Database user (default: videohelper_user)"
    echo "  -s  Docker service name (default: postgres)"
    echo "  -h  Show this help message"
    exit 0
}

while getopts "d:r:c:n:u:s:h" opt; do
    case "$opt" in
        d) BACKUP_DIR="$OPTARG" ;;
        r) RETENTION_DAYS="$OPTARG" ;;
        c) COMPOSE_PROJECT="$OPTARG" ;;
        n) DB_NAME="$OPTARG" ;;
        u) DB_USER="$OPTARG" ;;
        s) DOCKER_SERVICE="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

die() {
    log "ERROR: $1" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker is not installed or not in PATH."

# Build the docker compose command (supports both V1 and V2)
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

if [[ -n "$COMPOSE_PROJECT" ]]; then
    COMPOSE_CMD="$COMPOSE_CMD -p $COMPOSE_PROJECT"
fi

# Verify the postgres container is running
CONTAINER_ID=$($COMPOSE_CMD ps -q "$DOCKER_SERVICE" 2>/dev/null || true)
if [[ -z "$CONTAINER_ID" ]]; then
    die "Container for service '$DOCKER_SERVICE' is not running. Start it with: docker compose up -d $DOCKER_SERVICE"
fi

# ---------------------------------------------------------------------------
# Prepare backup directory
# ---------------------------------------------------------------------------
mkdir -p "$BACKUP_DIR" || die "Could not create backup directory: $BACKUP_DIR"

BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# ---------------------------------------------------------------------------
# Run pg_dump inside the container, compress, and save to host
# ---------------------------------------------------------------------------
log "Starting backup of database '$DB_NAME'..."
log "Container: $CONTAINER_ID (service: $DOCKER_SERVICE)"
log "Destination: $BACKUP_PATH"

if docker exec "$CONTAINER_ID" pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl | gzip > "$BACKUP_PATH"; then
    BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
    log "Backup completed successfully. Size: $BACKUP_SIZE"
else
    # Remove partial file on failure
    rm -f "$BACKUP_PATH"
    die "pg_dump failed. Check that the database '$DB_NAME' exists and user '$DB_USER' has access."
fi

# Verify the backup file is not empty
if [[ ! -s "$BACKUP_PATH" ]]; then
    rm -f "$BACKUP_PATH"
    die "Backup file is empty. The database may be empty or pg_dump failed silently."
fi

# ---------------------------------------------------------------------------
# Retention: remove backups older than RETENTION_DAYS
# ---------------------------------------------------------------------------
log "Applying retention policy: keeping backups from the last $RETENTION_DAYS days..."

DELETED_COUNT=0
while IFS= read -r old_backup; do
    rm -f "$old_backup"
    log "  Removed old backup: $(basename "$old_backup")"
    DELETED_COUNT=$((DELETED_COUNT + 1))
done < <(find "$BACKUP_DIR" -name "clipforge_${DB_NAME}_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" 2>/dev/null)

if [[ "$DELETED_COUNT" -eq 0 ]]; then
    log "No old backups to remove."
else
    log "Removed $DELETED_COUNT old backup(s)."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "clipforge_${DB_NAME}_*.sql.gz" -type f 2>/dev/null | wc -l | tr -d ' ')
log "Backup complete. Total backups on disk: $TOTAL_BACKUPS"
log "Backup file: $BACKUP_PATH"

exit 0
