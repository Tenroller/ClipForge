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

# Pre-download models so they are baked into the image.
# Running as root in the builder stage, so /root/.cache is writable.
# These will be copied to the runtime stage via the venv copy, but HF hub
# caches to /root/.cache/huggingface which we explicitly copy below.

# spaCy model - misaki/Kokoro tries to pip-install this at runtime otherwise
RUN python -m spacy download en_core_web_sm

# Kokoro TTS model (hexgrad/Kokoro-82M) - downloads ~170MB to HF cache
RUN python -c "from kokoro import KPipeline; KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')"

# YOLOv8 nano model - used by Compilation crop detection at runtime
# Download directly; importing ultralytics in the builder fails due to missing libGL.
RUN python -c "import urllib.request; urllib.request.urlretrieve('https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt', 'yolov8n.pt')"

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

# Create non-root user for security (with a real home dir)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup --home /home/appuser appuser

# Create necessary directories and set ownership for writable dirs
RUN mkdir -p output temp logs /home/appuser/.config/matplotlib /home/appuser/.cache/fontconfig /home/appuser/.config/Ultralytics \
    && chown -R appuser:appgroup output temp logs /home/appuser

# Copy pre-downloaded HuggingFace model cache directly into appuser home (single layer, no duplication)
COPY --from=builder /root/.cache/huggingface /home/appuser/.cache/huggingface
RUN chown -R appuser:appgroup /home/appuser/.cache/huggingface

# Copy pre-downloaded YOLOv8n model into the app directory (appuser can read /app)
COPY --from=builder /app/yolov8n.pt /app/yolov8n.pt

# Copy entrypoint script (runs as root to fix volume permissions, then drops to appuser)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ESPEAK_PATH=/usr/bin/espeak-ng
ENV DATA_PATH=/usr/share/espeak-ng-data
ENV MPLCONFIGDIR=/home/appuser/.config/matplotlib
ENV FONTCONFIG_PATH=/home/appuser/.cache/fontconfig
ENV HF_HOME=/home/appuser/.cache/huggingface
ENV YOLO_CONFIG_DIR=/home/appuser/.config/Ultralytics

# Expose port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8090/health || exit 1

# Entrypoint fixes volume permissions then drops to non-root user
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "main.py"]