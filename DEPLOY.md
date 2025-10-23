# Deploying VideoHelper to Coolify

This guide walks you through deploying VideoHelper to your self-hosted Coolify instance using Docker Compose with Cloudflare Tunnel.

## Prerequisites

- Self-hosted Coolify instance running
- Cloudflare Tunnel configured (SSL handled by Cloudflare)
- Git repository connected to Coolify
- Required API keys:
  - Pexels API key (for stock videos)
  - Google/Gemini API key (for AI script generation)

## Deployment Steps

### 1. Create New Project in Coolify

1. Log in to your Coolify dashboard
2. Click **"+ New Resource"**
3. Select **"Docker Compose"**
4. Choose your Git source (GitHub/GitLab)
5. Select this repository
6. Select the branch to deploy (e.g., `main`)

### 2. Configure Environment Variables

In Coolify's environment variables section, add the following:

#### Required Variables

```bash
# ============================================================================
# API Keys (REQUIRED)
# ============================================================================
PEXELS_API_KEY=your_pexels_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
# OR use Gemini API key
GEMINI_API_KEY=your_gemini_api_key_here

# ============================================================================
# Authentication (REQUIRED)
# ============================================================================
# Generate with: openssl rand -hex 32
JWT_SECRET_KEY=your-secure-random-jwt-secret-key-here

# Change these credentials for security
AUTH_USERNAME=admin
AUTH_PASSWORD=your-secure-password-here

# ============================================================================
# Database (REQUIRED)
# ============================================================================
# Use a strong password for production
POSTGRES_PASSWORD=your-secure-database-password-here

# ============================================================================
# CORS Configuration (for Cloudflare Tunnel)
# ============================================================================
# Allow all origins (since Cloudflare Tunnel handles SSL)
CORS_ALLOW_ORIGINS=*

# Or specify your Cloudflare domain
# CORS_ALLOW_ORIGINS=https://your-app.yourdomain.com
```

#### Optional Variables

```bash
# JWT Token Expiration (in minutes)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO
DEBUG_MODE=false

# Video Processing
MAX_CONCURRENT_JOBS=2

# Frontend Port (default: 80)
FRONTEND_PORT=80
```

### 3. Configure Persistent Volumes

Coolify automatically manages volumes defined in `docker-compose.yml`. The following volumes will be created:

- `postgres_data` - PostgreSQL database (critical - do not delete)
- `redis_data` - Redis cache
- `video_output` - Generated videos
- `video_temp` - Temporary processing files
- `video_cache` - Application cache
- `video_logs` - Application logs

**Important:** Make sure to back up the `postgres_data` and `video_output` volumes regularly.

### 4. Configure Cloudflare Tunnel

Since you're using Cloudflare Tunnel for SSL:

1. In Coolify, set the frontend service to expose port **80** (HTTP only)
2. Coolify will provide you with a URL like: `http://<your-app>.coolify.local`
3. In your Cloudflare Tunnel configuration:
   - Point your domain to the Coolify URL
   - Cloudflare will handle SSL/TLS termination
   - No need to configure SSL in the application

**Example Cloudflare Tunnel Config:**
```yaml
tunnel: <your-tunnel-id>
credentials-file: /path/to/credentials.json

ingress:
  - hostname: videohelper.yourdomain.com
    service: http://localhost:80  # or your Coolify proxy port
  - service: http_status:404
```

### 5. Build Configuration

Coolify will automatically detect the `docker-compose.yml` file and:

1. Build the backend from `backend/Dockerfile`
2. Build the frontend from `frontend/Dockerfile`
3. Build the video-processor from `video-processor/Dockerfile`
4. Pull PostgreSQL and Redis images

**Build time:** First deployment takes 5-10 minutes depending on your server specs.

### 6. Deploy the Application

1. Review your environment variables
2. Click **"Deploy"** in Coolify
3. Monitor the build logs
4. Wait for all services to become healthy

Health checks are configured for all services:
- `postgres` - Checks database availability
- `redis` - Checks cache availability
- `backend` - Checks `/api/health` endpoint
- `video-processor` - Checks `/health` endpoint
- `frontend` - Checks HTTP response on port 80

### 7. Verify Deployment

Once deployed, test the following:

#### Check Service Health
```bash
# Backend health check
curl http://your-app.yourdomain.com/api/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-10-23T...",
  "database": "connected",
  "redis": "connected"
}
```

#### Access the Frontend
Navigate to `https://your-app.yourdomain.com` (via Cloudflare Tunnel)

#### Login
Use the credentials you set in environment variables:
- Username: value of `AUTH_USERNAME`
- Password: value of `AUTH_PASSWORD`

#### Test Video Generation
1. Go to the MoneyPrinter or Brainrot tab
2. Submit a test video generation request
3. Monitor the job status in the Job Monitoring page

### 8. Post-Deployment Configuration

#### Enable Auto-Deploy (Recommended)
In Coolify:
1. Go to your project settings
2. Enable **"Auto Deploy"**
3. Select the branch to watch (e.g., `main`)
4. Coolify will automatically redeploy on git push

#### Configure Webhooks (Optional)
Set up GitHub/GitLab webhooks to trigger deployments on push.

#### Set Up Monitoring (Optional)
Access Prometheus metrics at: `http://your-app.yourdomain.com/api/metrics`

#### Configure Backup Strategy
1. In Coolify, go to **Volumes**
2. Set up automated backups for:
   - `postgres_data` (critical)
   - `video_output` (important)

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│         Cloudflare Tunnel (SSL Termination)         │
└────────────────────┬────────────────────────────────┘
                     │ HTTPS
                     ↓
┌─────────────────────────────────────────────────────┐
│              Coolify Proxy (HTTP)                    │
└────────────────────┬────────────────────────────────┘
                     │ HTTP (port 80)
                     ↓
          ┌──────────────────────┐
          │   Frontend (Nginx)   │
          │   Port 80            │
          └──────────┬───────────┘
                     │ API Proxy (/api/*)
                     ↓
          ┌──────────────────────┐
          │   Backend (FastAPI)  │
          │   Port 9000          │
          └──────┬───────────────┘
                 │
      ┌──────────┼──────────┬──────────┐
      ↓          ↓          ↓          ↓
┌──────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
│PostgreSQL│ │ Redis  │ │  Video  │ │  Shared  │
│  Port    │ │ Port   │ │Processor│ │ Volumes  │
│  5432    │ │ 6379   │ │ Port    │ │          │
│          │ │        │ │ 8090    │ │          │
└──────────┘ └────────┘ └─────────┘ └──────────┘
```

## Troubleshooting

### Services Not Starting

Check logs in Coolify:
```bash
# View logs for specific service
docker compose logs -f backend
docker compose logs -f postgres
docker compose logs -f video-processor
```

### Database Connection Issues

Verify PostgreSQL is running:
```bash
docker compose exec postgres pg_isready -U videohelper_user
```

Check DATABASE_URL format:
```
postgresql://videohelper_user:YOUR_PASSWORD@postgres:5432/videohelper
```

### Frontend Not Loading

1. Check if frontend container is running
2. Verify Cloudflare Tunnel is pointing to correct port (80)
3. Check nginx logs: `docker compose logs -f frontend`

### Video Generation Failing

1. Check API keys are correctly set
2. Verify video-processor is running: `docker compose ps`
3. Check backend logs for errors: `docker compose logs -f backend`
4. Ensure volumes are mounted correctly

### CORS Errors

If you see CORS errors in browser console:
1. Set `CORS_ALLOW_ORIGINS` to your Cloudflare domain
2. Redeploy the application
3. Clear browser cache

### Performance Issues

If video generation is slow:
1. Increase `MAX_CONCURRENT_JOBS` (default: 2)
2. Allocate more CPU/RAM to Coolify server
3. Consider using cloud GPU acceleration (Modal integration)

## Updating the Application

### Manual Update
1. Push changes to your git repository
2. In Coolify, click **"Redeploy"**
3. Wait for build to complete

### Automatic Updates
With auto-deploy enabled, just push to your configured branch.

### Database Migrations
If there are database schema changes:
```bash
# SSH into your Coolify server
docker compose exec backend python -m backend.migrations.001_add_resume_columns
```

## Scaling Considerations

### Horizontal Scaling
To scale video processing:
1. Increase number of video-processor replicas in `docker-compose.yml`
2. Update `VIDEO_PROCESSOR_URLS` with multiple URLs

### Vertical Scaling
Increase Docker resource limits in Coolify settings:
- CPU: 4+ cores recommended for video processing
- RAM: 8GB+ recommended
- Storage: 50GB+ for video output

### Cloud GPU Integration
For faster video generation, consider Modal integration (see CLAUDE.md).

## Security Checklist

- ✅ Strong `JWT_SECRET_KEY` (32+ characters)
- ✅ Secure `AUTH_PASSWORD` (12+ characters)
- ✅ Strong `POSTGRES_PASSWORD`
- ✅ Specific `CORS_ALLOW_ORIGINS` (not `*`)
- ✅ Rate limiting enabled
- ✅ Regular backups configured
- ✅ Cloudflare Tunnel with SSL
- ✅ Environment variables not committed to git

## Support & Resources

- **CLAUDE.md** - Project architecture and development guide
- **README.md** - Project overview
- **Coolify Docs** - https://coolify.io/docs
- **Cloudflare Tunnel Docs** - https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/

## Getting API Keys

### Pexels API Key
1. Go to https://www.pexels.com/api/
2. Create free account
3. Generate API key (free tier: 200 requests/hour)

### Google/Gemini API Key
1. Go to https://ai.google.dev/
2. Create project
3. Enable Gemini API
4. Generate API key (free tier available)

## Backup & Recovery

### Manual Backup
```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U videohelper_user videohelper > backup.sql

# Backup videos
docker compose cp backend:/app/output ./backup_videos
```

### Restore from Backup
```bash
# Restore PostgreSQL
cat backup.sql | docker compose exec -T postgres psql -U videohelper_user videohelper

# Restore videos
docker compose cp ./backup_videos backend:/app/output
```

---

**Deployment Date:** 2025-10-23
**Last Updated:** 2025-10-23
**Coolify Version:** 4.x
**VideoHelper Version:** Latest
