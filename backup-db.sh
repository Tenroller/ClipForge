#!/bin/bash

# Database Backup Script for AI Video Generator
echo "🗄️  Creating database backup..."

# Create backups directory if it doesn't exist
mkdir -p backups

# Get current timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Backup PostgreSQL
echo "📦 Backing up PostgreSQL database..."
docker-compose exec -T postgres pg_dump -U videohelper_user -d videohelper > "backups/postgres_backup_${TIMESTAMP}.sql"

# Backup Redis (if needed)
echo "📦 Backing up Redis data..."
docker-compose exec -T redis redis-cli --rdb - > "backups/redis_backup_${TIMESTAMP}.rdb"

# Backup output volumes
echo "📦 Backing up output files..."
docker run --rm -v ai-video-generator_shared_output:/data -v $(pwd)/backups:/backup alpine tar czf "/backup/output_backup_${TIMESTAMP}.tar.gz" -C /data .

echo "✅ Backup completed!"
echo "Files created:"
echo "   - PostgreSQL: backups/postgres_backup_${TIMESTAMP}.sql"
echo "   - Redis: backups/redis_backup_${TIMESTAMP}.rdb"
echo "   - Output files: backups/output_backup_${TIMESTAMP}.tar.gz"