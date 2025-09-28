# Python slim image suitable for Cloud Run
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    PATH="/home/app/.local/bin:$PATH"

# Install system dependencies (minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy project
COPY . .

# Ensure entrypoint is executable
RUN chmod +x scripts/entrypoint.sh

# Cloud Run expects to listen on $PORT
EXPOSE 8080

# Use the entrypoint script to run migrations, collectstatic, and start Gunicorn
CMD ["scripts/entrypoint.sh"]
