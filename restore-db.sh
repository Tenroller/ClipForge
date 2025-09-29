#!/bin/bash

# Database Restore Script for AI Video Generator
echo "🔄 Database restore script for AI Video Generator"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <backup_timestamp>"
    echo "Example: $0 20231201_143022"
    echo ""
    echo "Available backups:"
    ls -la backups/ | grep backup
    exit 1
fi

TIMESTAMP=$1

# Check if backup files exist
if [ ! -f "backups/postgres_backup_${TIMESTAMP}.sql" ]; then
    echo "❌ PostgreSQL backup file not found: backups/postgres_backup_${TIMESTAMP}.sql"
    exit 1
fi

echo "⚠️  WARNING: This will restore the database to the backup from ${TIMESTAMP}"
echo "This will OVERWRITE all current data!"
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

echo "🔄 Stopping services..."
docker-compose down

echo "🗑️  Removing old database volume..."
docker volume rm ai-video-generator_postgres_data

echo "🚀 Starting database service..."
docker-compose up -d postgres redis

echo "⏳ Waiting for database to be ready..."
sleep 10

echo "📥 Restoring PostgreSQL database..."
cat "backups/postgres_backup_${TIMESTAMP}.sql" | docker-compose exec -T postgres psql -U videohelper_user -d videohelper

# Restore Redis if backup exists
if [ -f "backups/redis_backup_${TIMESTAMP}.rdb" ]; then
    echo "📥 Restoring Redis data..."
    docker-compose exec -T redis redis-cli FLUSHALL
    cat "backups/redis_backup_${TIMESTAMP}.rdb" | docker-compose exec -T redis redis-cli --pipe
fi

# Restore output files if backup exists
if [ -f "backups/output_backup_${TIMESTAMP}.tar.gz" ]; then
    echo "📥 Restoring output files..."
    docker run --rm -v ai-video-generator_shared_output:/data -v $(pwd)/backups:/backup alpine tar xzf "/backup/output_backup_${TIMESTAMP}.tar.gz" -C /data
fi

echo "🚀 Starting all services..."
docker-compose up -d

echo "✅ Database restore completed!"
echo "Services are starting up. Check with: docker-compose logs -f"