# Production Deployment Guide

This guide covers deploying the AI Video Generator to production environments.

## Quick Start (Docker)

The fastest way to deploy is using Docker Compose:

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd ai-video-generator

# 2. Create environment file
cp .env.example .env
# Edit .env with your API keys and configuration

# 3. Build and run
docker compose up -d

# 4. Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8080
```

## Environment Configuration

### Required Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Essential API keys
PEXELS_API_KEY=your_pexels_api_key
GOOGLE_API_KEY=your_google_api_key  # or GEMINI_API_KEY

# Security
API_KEY=your_secret_api_key
CORS_ALLOW_ORIGINS=https://yourdomain.com
```

### Optional Configuration

```bash
# Performance
MAX_CONCURRENT_JOBS=4
RATE_LIMIT_PER_MINUTE=20

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
ENABLE_JSON_LOGGING=true

# Storage
VIDEOHELPER_OUTPUT_DIR=/app/storage
DATABASE_PATH=/app/data/jobs.db
```

## Deployment Options

### 1. Docker Compose (Recommended)

**Pros**: Easy setup, isolated environment, includes reverse proxy
**Cons**: Single server only

```bash
# Production docker-compose.yml
version: '3.9'
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - NODE_ENV=production
    volumes:
      - ./storage:/app/storage
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
      args:
        VITE_API_BASE: https://api.yourdomain.com
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
```

### 2. Kubernetes

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: video-generator-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: video-generator-backend
  template:
    metadata:
      labels:
        app: video-generator-backend
    spec:
      containers:
      - name: backend
        image: your-registry/video-generator-backend:latest
        ports:
        - containerPort: 8080
        env:
        - name: PEXELS_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: pexels-key
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: api-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        volumeMounts:
        - name: storage
          mountPath: /app/storage
      volumes:
      - name: storage
        persistentVolumeClaim:
          claimName: video-storage
```

### 3. Cloud Platforms

#### Heroku
```bash
# Install Heroku CLI and login
heroku create your-app-name

# Set environment variables
heroku config:set PEXELS_API_KEY=your_key
heroku config:set API_KEY=your_secret

# Deploy
git push heroku main
```

#### Railway
```toml
# railway.toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile.backend"

[deploy]
healthcheckPath = "/api/health"
restartPolicyType = "on_failure"
```

#### DigitalOcean App Platform
```yaml
# .do/app.yaml
name: video-generator
services:
- name: backend
  source_dir: /
  dockerfile_path: Dockerfile.backend
  github:
    repo: your-username/your-repo
    branch: main
  envs:
  - key: PEXELS_API_KEY
    value: your_key
    type: SECRET
  instance_count: 1
  instance_size_slug: basic-s
  routes:
  - path: /api
- name: frontend
  source_dir: /
  dockerfile_path: Dockerfile.frontend
  github:
    repo: your-username/your-repo
    branch: main
  routes:
  - path: /
```

## Reverse Proxy Configuration

### Nginx

```nginx
# nginx.conf
upstream backend {
    server backend:8080;
}

upstream frontend {
    server frontend:80;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # API routes
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts for long video generation
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Traefik

```yaml
# docker-compose.yml with Traefik
version: '3.9'
services:
  traefik:
    image: traefik:v3.0
    command:
      - "--api.dashboard=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@yourdomain.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
      - "./letsencrypt:/letsencrypt"

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`yourdomain.com`) && PathPrefix(`/api`)"
      - "traefik.http.routers.backend.tls.certresolver=letsencrypt"

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`yourdomain.com`)"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
```

## Database Setup

### SQLite (Default)
No additional setup needed. Database file created automatically.

### PostgreSQL (Production)
```bash
# 1. Install PostgreSQL
apt update && apt install postgresql postgresql-contrib

# 2. Create database and user
sudo -u postgres createdb videogendb
sudo -u postgres createuser videouser
sudo -u postgres psql -c "ALTER USER videouser WITH PASSWORD 'securepassword';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE videogendb TO videouser;"

# 3. Set environment variable
DATABASE_URL=postgresql://videouser:securepassword@localhost:5432/videogendb
```

## Monitoring & Observability

### Health Checks
```bash
# Basic health check
curl http://localhost:8080/api/health

# With API key
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/ping
```

### Prometheus Metrics (Future Enhancement)
```yaml
# Add to docker-compose.yml
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### Log Aggregation
```yaml
# ELK Stack example
  elasticsearch:
    image: elasticsearch:8.8.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false

  logstash:
    image: logstash:8.8.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: kibana:8.8.0
    ports:
      - "5601:5601"
```

## Security Considerations

### API Security
- Always set `API_KEY` in production
- Use HTTPS only (`CORS_ALLOW_ORIGINS` without http://)
- Configure `TRUSTED_HOSTS` to your domain only
- Set up rate limiting (`RATE_LIMIT_PER_MINUTE`)

### System Security
```bash
# Firewall rules
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable

# Fail2ban for SSH protection
apt install fail2ban
systemctl enable fail2ban
```

### Container Security
```dockerfile
# Use non-root user in Dockerfile
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

## Performance Optimization

### Resource Limits
```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          memory: 1G
```

### Caching
```bash
# Redis for job queue (future enhancement)
REDIS_URL=redis://localhost:6379/0
```

### CDN Setup
Use a CDN for serving generated videos:
```bash
# AWS CloudFront example
aws cloudfront create-distribution \
  --distribution-config file://cloudfront-config.json
```

## Backup Strategy

### Database Backup
```bash
# SQLite
cp /app/data/jobs.db /backup/jobs-$(date +%Y%m%d).db

# PostgreSQL
pg_dump videogendb > /backup/videogendb-$(date +%Y%m%d).sql
```

### Video Files Backup
```bash
# Sync to cloud storage
rclone sync /app/storage/ s3:your-bucket/video-storage/
```

## Troubleshooting

### Common Issues
1. **Out of disk space**: Monitor `/app/storage` usage
2. **Memory issues**: Increase container memory limits
3. **FFmpeg errors**: Ensure FFmpeg is installed and accessible
4. **TTS issues**: Verify espeak-ng installation

### Debug Mode
```bash
# Enable debug logging
DEBUG=true
ENABLE_JSON_LOGGING=true

# View logs
docker compose logs -f backend
```

### Performance Monitoring
```bash
# Check job statistics
curl -H "X-API-Key: your-key" http://localhost:8080/api/jobs/stats

# Monitor system resources
docker stats
```

## Support

For issues and support:
1. Check the logs first: `docker compose logs`
2. Verify environment variables: `docker compose config`
3. Test connectivity: `curl http://localhost:8080/api/health`
4. Review this deployment guide
5. Open an issue in the repository with detailed logs and configuration
