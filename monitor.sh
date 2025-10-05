#!/bin/bash

# Monitoring Script for AI Video Generator Services
echo "🔍 AI Video Generator - Service Monitor"
echo "========================================"

# Check Docker Compose status
echo ""
echo "📊 Container Status:"
docker-compose ps

echo ""
echo "🏥 Health Checks:"

# Test Backend API
if curl -s http://localhost:9000/health > /dev/null; then
    echo "✅ Backend API (9000) - Healthy"
else
    echo "❌ Backend API (9000) - Not responding"
fi

# Test Video Processor
if curl -s http://localhost:8090/health > /dev/null; then
    echo "✅ Video Processor (8090) - Healthy"
else
    echo "❌ Video Processor (8090) - Not responding"
fi

# Test Frontend
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend (3000) - Healthy"
else
    echo "❌ Frontend (3000) - Not responding"
fi

# Test PostgreSQL
if docker-compose exec -T postgres pg_isready -U videohelper_user -d videohelper > /dev/null 2>&1; then
    echo "✅ PostgreSQL (5433) - Ready"
else
    echo "❌ PostgreSQL (5433) - Not ready"
fi

# Test Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis (6380) - Ready"
else
    echo "❌ Redis (6380) - Not ready"
fi

echo ""
echo "💾 Storage Usage:"
docker system df

echo ""
echo "🔧 Volume Status:"
docker volume ls | grep ai-video-generator

echo ""
echo "📈 Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"

echo ""
echo "📋 Recent Logs (Last 10 lines):"
echo "Backend:"
docker-compose logs --tail=5 backend | tail -5
echo ""
echo "Video Processor:"
docker-compose logs --tail=5 video-processor | tail -5

echo ""
echo "🔗 Service URLs:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:9000"
echo "   API Docs: http://localhost:9000/docs"
echo "   PostgreSQL: localhost:5433"
echo "   Redis: localhost:6380"