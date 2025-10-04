#!/bin/bash

# Stop AI Video Generator Services
echo "🛑 Stopping AI Video Generator services..."

# Stop all services
docker-compose down

echo "🧹 Cleaning up..."

# Optional: Remove unused Docker images and containers
read -p "Do you want to clean up unused Docker resources? (y/N): " cleanup
if [[ $cleanup =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing unused Docker resources..."
    docker system prune -f
    docker volume prune -f
fi

echo "✅ AI Video Generator services stopped"