# Video Processor Dockerfile - FastAPI Microservice (Multi-stage build)
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
  build-essential \
  gcc \
  python3-dev \
  git \
  && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies in a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies including ffmpeg and espeak-ng
RUN apt-get update && apt-get install -y \
  ffmpeg \
  espeak-ng \
  curl \
  wget \
  fonts-dejavu-core \
  libsndfile1 \
  && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy the application code
COPY . .

# Create non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Create necessary directories and set ownership for writable dirs
RUN mkdir -p output temp logs && chown -R appuser:appgroup output temp logs

# Copy entrypoint script (runs as root to fix volume permissions, then drops to appuser)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ESPEAK_PATH=/usr/bin/espeak-ng
ENV DATA_PATH=/usr/share/espeak-ng-data

# Expose port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8090/health || exit 1

# Entrypoint fixes volume permissions then drops to non-root user
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "main.py"]