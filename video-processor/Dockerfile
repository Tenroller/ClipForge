# Video Processor Dockerfile - FastAPI Microservice
FROM python:3.11-slim

# Install system dependencies including espeak-ng for TTS
RUN apt-get update && apt-get install -y \
    ffmpeg \
    espeak-ng \
    curl \
    wget \
    git \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create necessary directories
RUN mkdir -p output temp logs

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

# Run the application
CMD ["python", "main.py"]