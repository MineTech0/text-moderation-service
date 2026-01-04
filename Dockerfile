# =============================================================================
# Text Moderation Service - Production Dockerfile
# =============================================================================
# Multi-stage build for optimized production image

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production - Final slim image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS production

# Labels for container metadata
LABEL org.opencontainers.image.title="Text Moderation Service" \
      org.opencontainers.image.description="ML-powered text moderation with toxicity detection" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Moderation Service"

# Security: Don't run as root
# Create non-root user early
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    # App paths
    WORDLIST_DIR=/app/data \
    HF_HOME=/app/model_cache \
    # Production defaults
    DEBUG=false \
    LOG_FORMAT=json \
    LOG_LEVEL=INFO

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create necessary directories with correct permissions
RUN mkdir -p /app/data /app/model_cache && \
    chown -R appuser:appgroup /app

# Copy application code
COPY --chown=appuser:appgroup app /app/app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=5)" || exit 1

# Default command - production ready with proper settings
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--access-log", \
     "--no-server-header"]
