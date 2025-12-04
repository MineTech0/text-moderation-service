# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing pyc files to disc
# PYTHONUNBUFFERED: Prevents Python from buffering stdout and stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORDLIST_DIR=/app/data \
    HF_HOME=/app/model_cache

# Set work directory
WORKDIR /app

# Install system dependencies
# curl/wget might be needed for healthchecks or debugging, but keeping it slim.
# build-essential might be needed for some python packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

# Install python dependencies
COPY requirements.txt .
# Install torch CPU version specifically to save space
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Create directories for data and model cache with correct permissions
RUN mkdir -p /app/data /app/model_cache && \
    chown -R appuser:appgroup /app/data /app/model_cache

# Copy application code
COPY app /app/app

# Change ownership of the application code
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/healthz', timeout=5).raise_for_status()" || exit 1

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

