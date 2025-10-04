#!/bin/bash

# Build and Start AI Video Generator Services
echo "🚀 Building and starting AI Video Generator services..."

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp docker.env.example .env
    echo "⚠️  Please edit .env file with your API keys before running the services"
    echo "   Required: PEXELS_API_KEY, GOOGLE_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY"
fi

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 15

# Check service health
echo "🔍 Checking service health..."
echo ""
echo "Service URLs:"
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8080"
echo "Video Processor: http://localhost:8090"
echo "PostgreSQL: localhost:5433"
echo "Redis: localhost:6380"

# Test health endpoints
echo ""
echo "Health checks:"
curl -s http://localhost:8080/health > /dev/null && echo "✅ Backend API is running" || echo "❌ Backend API is not responding"
curl -s http://localhost:8090/health > /dev/null && echo "✅ Video Processor is running" || echo "❌ Video Processor is not responding"
curl -s http://localhost:3000 > /dev/null && echo "✅ Frontend is running" || echo "❌ Frontend is not responding"

# Test database connections
echo ""
echo "Database connections:"
docker-compose exec -T postgres pg_isready -U videohelper_user -d videohelper > /dev/null 2>&1 && echo "✅ PostgreSQL is ready" || echo "❌ PostgreSQL is not ready"
docker-compose exec -T redis redis-cli ping > /dev/null 2>&1 && echo "✅ Redis is ready" || echo "❌ Redis is not ready"

echo ""
echo "🎉 AI Video Generator is ready!"
echo ""
echo "📋 Service Information:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8080"
echo "   API Docs: http://localhost:8080/docs"
echo "   PostgreSQL: localhost:5433"
echo "   Redis: localhost:6380"
echo ""
echo "🛠️  Useful Commands:"
echo "   View logs: docker-compose logs -f"
echo "   View specific service logs: docker-compose logs -f [service-name]"
echo "   Stop services: docker-compose down"
echo "   Stop and remove volumes: docker-compose down -v"
echo ""
echo "🔧 Database Access:"
echo "   PostgreSQL: docker-compose exec postgres psql -U videohelper_user -d videohelper"
echo "   Redis CLI: docker-compose exec redis redis-cli"