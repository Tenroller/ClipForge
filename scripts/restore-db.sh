#!/usr/bin/env bash
# =============================================================================
# ClipForge - PostgreSQL Database Restore Script
# =============================================================================
#
# Restores a compressed backup created by backup-db.sh into the PostgreSQL
# database running inside the Docker "postgres" service container.
#
# Usage:
#   ./scripts/restore-db.sh <backup_file>
#   ./scripts/restore-db.sh backups/db/clipforge_videohelper_20260311_020000.sql.gz
#   ./scripts/restore-db.sh -l                    # List available backups
#   ./scripts/restore-db.sh -c my-compose <file>  # Custom compose project
#
# WARNING: This will DROP and recreate the target database. All existing data
#          will be lost. A safety backup is created automatically before restore.
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Default configuration (override with flags or environment variables)
# ---------------------------------------------------------------------------
BACKUP_DIR="${BACKUP_DIR:-./backups/db}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-}"
DB_NAME="${DB_NAME:-videohelper}"
DB_USER="${DB_USER:-videohelper_user}"
DOCKER_SERVICE="${DOCKER_SERVICE:-postgres}"
SKIP_CONFIRM="${SKIP_CONFIRM:-false}"

# ---------------------------------------------------------------------------
# Parse command-line arguments
# ---------------------------------------------------------------------------
usage() {
    echo "Usage: $0 [-c compose_project] [-n db_name] [-u db_user] [-s docker_service] [-y] [-l] [-h] <backup_file>"
    echo ""
    echo "Options:"
    echo "  -c  Docker Compose project name (default: auto-detect)"
    echo "  -n  Database name (default: videohelper)"
    echo "  -u  Database user (default: videohelper_user)"
    echo "  -s  Docker service name (default: postgres)"
    echo "  -y  Skip confirmation prompt (use with caution)"
    echo "  -l  List available backups and exit"
    echo "  -h  Show this help message"
    echo ""
    echo "Arguments:"
    echo "  backup_file  Path to a .sql.gz backup file created by backup-db.sh"
    exit 0
}

list_backups() {
    echo "Available backups in '$BACKUP_DIR':"
    echo ""
    if [[ -d "$BACKUP_DIR" ]]; then
        local count=0
        while IFS= read -r backup; do
            local size
            size=$(du -h "$backup" | cut -f1)
            local modified
            modified=$(date -r "$backup" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || stat -c '%y' "$backup" 2>/dev/null | cut -d. -f1)
            echo "  [$size]  $modified  $(basename "$backup")"
            count=$((count + 1))
        done < <(find "$BACKUP_DIR" -name "clipforge_*.sql.gz" -type f | sort -r)
        echo ""
        if [[ "$count" -eq 0 ]]; then
            echo "  No backups found."
        else
            echo "  Total: $count backup(s)"
        fi
    else
        echo "  Backup directory does not exist: $BACKUP_DIR"
    fi
    exit 0
}

LIST_MODE=false

while getopts "c:n:u:s:ylh" opt; do
    case "$opt" in
        c) COMPOSE_PROJECT="$OPTARG" ;;
        n) DB_NAME="$OPTARG" ;;
        u) DB_USER="$OPTARG" ;;
        s) DOCKER_SERVICE="$OPTARG" ;;
        y) SKIP_CONFIRM="true" ;;
        l) LIST_MODE=true ;;
        h) usage ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))

if [[ "$LIST_MODE" == "true" ]]; then
    list_backups
fi

# ---------------------------------------------------------------------------
# Validate backup file argument
# ---------------------------------------------------------------------------
if [[ $# -lt 1 ]]; then
    echo "Error: No backup file specified." >&2
    echo "" >&2
    usage
fi

BACKUP_FILE="$1"

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

[[ -f "$BACKUP_FILE" ]] || die "Backup file not found: $BACKUP_FILE"
[[ "$BACKUP_FILE" == *.sql.gz ]] || die "Expected a .sql.gz file, got: $BACKUP_FILE"

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
# Confirmation prompt
# ---------------------------------------------------------------------------
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo "============================================="
echo "  ClipForge Database Restore"
echo "============================================="
echo ""
echo "  Backup file : $(basename "$BACKUP_FILE") ($BACKUP_SIZE)"
echo "  Database    : $DB_NAME"
echo "  User        : $DB_USER"
echo "  Container   : $CONTAINER_ID"
echo ""
echo "  WARNING: This will DROP the existing database"
echo "  '$DB_NAME' and replace it with the backup."
echo "  ALL CURRENT DATA WILL BE LOST."
echo ""
echo "============================================="

if [[ "$SKIP_CONFIRM" != "true" ]]; then
    read -r -p "Type 'yes' to proceed: " CONFIRM
    if [[ "$CONFIRM" != "yes" ]]; then
        log "Restore cancelled by user."
        exit 0
    fi
fi

# ---------------------------------------------------------------------------
# Create a safety backup before restore
# ---------------------------------------------------------------------------
SAFETY_DIR="${BACKUP_DIR}/pre-restore"
mkdir -p "$SAFETY_DIR"
SAFETY_FILE="${SAFETY_DIR}/clipforge_${DB_NAME}_pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"

log "Creating safety backup before restore..."
if docker exec "$CONTAINER_ID" pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl 2>/dev/null | gzip > "$SAFETY_FILE"; then
    if [[ -s "$SAFETY_FILE" ]]; then
        log "Safety backup saved: $SAFETY_FILE ($(du -h "$SAFETY_FILE" | cut -f1))"
    else
        rm -f "$SAFETY_FILE"
        log "Warning: Safety backup is empty (database may already be empty). Continuing..."
    fi
else
    rm -f "$SAFETY_FILE"
    log "Warning: Could not create safety backup. The database may not exist yet. Continuing..."
fi

# ---------------------------------------------------------------------------
# Terminate existing connections and drop/recreate the database
# ---------------------------------------------------------------------------
log "Terminating active connections to '$DB_NAME'..."
docker exec "$CONTAINER_ID" psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
    >/dev/null 2>&1 || true

log "Dropping and recreating database '$DB_NAME'..."
docker exec "$CONTAINER_ID" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" || die "Failed to drop database."
docker exec "$CONTAINER_ID" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";" || die "Failed to create database."

# ---------------------------------------------------------------------------
# Restore the backup
# ---------------------------------------------------------------------------
log "Restoring from: $(basename "$BACKUP_FILE")..."

if gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER_ID" psql -U "$DB_USER" -d "$DB_NAME" --quiet --single-transaction; then
    log "Restore completed successfully."
else
    die "Restore failed. The database may be in an inconsistent state. Safety backup: $SAFETY_FILE"
fi

# ---------------------------------------------------------------------------
# Verify restore
# ---------------------------------------------------------------------------
log "Verifying restore..."
TABLE_COUNT=$(docker exec "$CONTAINER_ID" psql -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

log "Restore verification: $TABLE_COUNT table(s) found in '$DB_NAME'."

if [[ "$TABLE_COUNT" -eq 0 ]]; then
    log "Warning: No tables found after restore. The backup may have been empty or contained only schema-less data."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================="
echo "  Restore Complete"
echo "============================================="
echo "  Database   : $DB_NAME"
echo "  Tables     : $TABLE_COUNT"
echo "  Source     : $(basename "$BACKUP_FILE")"
if [[ -f "$SAFETY_FILE" && -s "$SAFETY_FILE" ]]; then
    echo "  Safety bkp : $SAFETY_FILE"
fi
echo "============================================="
echo ""
log "You may need to restart application services: docker compose restart backend video-processor"

exit 0
