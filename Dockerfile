# syntax=docker/dockerfile:1.7

# Use a slim Python image
FROM python:3.11-slim

# Configure environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DJANGO_SETTINGS_MODULE=legalai.settings

# Create app directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first
COPY requirements.txt /app/

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app

# Create directories for static and media (if local storage)
RUN mkdir -p /app/staticfiles /app/media

# Create entrypoint script
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Cloud Run listens on PORT env (8080)
EXPOSE 8080

# Run as non-root for security
RUN useradd -m appuser
USER appuser

# Default chroma path can be overridden via env
ENV CHROMA_DB_PATH=/mnt/chroma

# Entrypoint starts gunicorn
ENTRYPOINT ["/entrypoint.sh"]
