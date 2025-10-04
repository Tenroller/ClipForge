# AI Video Generator - Docker Setup

This Docker configuration provides a complete containerized setup for the AI Video Generator application with four services:

## Services

### 1. Frontend (Port 3000)
- **Technology**: React + Vite + Nginx
- **Purpose**: User interface for video generation
- **URL**: http://localhost:3000

### 2. Backend API (Port 8080)
- **Technology**: FastAPI + Python
- **Purpose**: Main API server and job management
- **URL**: http://localhost:8080
- **API Docs**: http://localhost:8080/docs

### 3. Video Processor (Port 8090)
- **Technology**: FastAPI + Python
- **Purpose**: Video generation microservice
- **URL**: http://localhost:8090

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least 4GB RAM available for containers
- Required API keys (see Configuration section)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd ai-video-generator
```

### 2. Configure Environment
```bash
# Copy the environment template
cp docker.env.example .env

# Edit .env file with your API keys
nano .env  # or your preferred editor
```

### 3. Start Services
```bash
# Production mode
./docker-start.sh

# Or manually
docker-compose up -d
```

### 4. Access Application
- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- API Documentation: http://localhost:8080/docs

## Configuration

### Required API Keys
Edit the `.env` file with your actual API keys:

```env
# At least one AI API key is required
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# Required for background videos
PEXELS_API_KEY=your_pexels_api_key_here
```

### Optional Configuration
```env
# Backend settings
BACKEND_API_KEY=your_secure_api_key_here
MAX_CONCURRENT_JOBS=2
JOB_TIMEOUT_SECONDS=3600

# Logging
LOG_LEVEL=INFO
DEBUG_MODE=false
```

## Development Mode

For development with hot reloading:

```bash
# Start development services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

## Volume Management

The application uses Docker volumes for:
- **shared_output**: Generated videos (shared between backend and video processor)
- **shared_temp**: Temporary files during processing
- **backend_logs**: Backend application logs
- **processor_logs**: Video processor logs
- **backend_cache**: Backend cache data

### Backup Volumes
```bash
# Backup output videos
docker run --rm -v ai-video-generator_shared_output:/data -v $(pwd):/backup alpine tar czf /backup/output-backup.tar.gz -C /data .

# Restore output videos
docker run --rm -v ai-video-generator_shared_output:/data -v $(pwd):/backup alpine tar xzf /backup/output-backup.tar.gz -C /data
```

## Service Communication

Services communicate through a dedicated Docker network:
- Frontend → Backend: HTTP requests via nginx proxy
- Backend → Video Processor: HTTP API calls
- Shared storage via Docker volumes

## Monitoring and Logs

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f video-processor
docker-compose logs -f frontend
```

### Health Checks
```bash
# Check service health
curl http://localhost:8080/health  # Backend
curl http://localhost:8090/health  # Video Processor
curl http://localhost:3000         # Frontend
```

### Container Status
```bash
# View running containers
docker-compose ps

# View resource usage
docker stats
```

## Troubleshooting

### Service Won't Start
1. Check if ports are available:
   ```bash
   lsof -i :3000  # Frontend
   lsof -i :8080  # Backend
   lsof -i :8090  # Video Processor
   ```

2. Check Docker logs:
   ```bash
   docker-compose logs [service-name]
   ```

### API Key Issues
- Ensure all required API keys are set in `.env`
- Restart services after updating environment variables:
  ```bash
  docker-compose down
  docker-compose up -d
  ```

### Video Generation Fails
1. Check video processor logs:
   ```bash
   docker-compose logs video-processor
   ```

2. Verify FFmpeg installation in container:
   ```bash
   docker-compose exec video-processor ffmpeg -version
   ```

3. Check available disk space:
   ```bash
   docker system df
   ```

### Performance Issues
- Increase Docker memory allocation (recommended: 4GB+)
- Monitor container resource usage:
  ```bash
  docker stats
  ```

## Stopping Services

```bash
# Stop all services
./docker-stop.sh

# Or manually
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

## Security Notes

- The setup includes basic security headers via nginx
- API keys are passed through environment variables
- Services communicate over a private Docker network
- Consider using Docker secrets for production deployments

## Production Deployment

For production deployment:

1. Use a reverse proxy (nginx/traefik) with SSL/TLS
2. Set up proper secret management
3. Configure persistent volume storage
4. Implement log aggregation
5. Set up monitoring and alerting
6. Use Docker swarm or Kubernetes for orchestration